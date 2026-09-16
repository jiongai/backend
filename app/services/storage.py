"""Cloudflare R2 storage and strict public artifact URL handling."""

import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional, Set, Tuple
from urllib.parse import unquote, urlsplit

import boto3
import structlog
from botocore.exceptions import ClientError


logger = structlog.get_logger(__name__)

OBJECT_KEY_PATTERN = re.compile(
    r"^projects/"
    r"(?P<project_id>[A-Za-z0-9][A-Za-z0-9._-]{0,127})/"
    r"(?P<folder>temp|saved)/"
    r"(?P<filename>[A-Za-z0-9][A-Za-z0-9._-]{0,199})"
    r"(?P<extension>\.mp3|\.srt)$"
)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
ALLOWED_FOLDERS = {"temp", "saved"}


@dataclass(frozen=True)
class R2ObjectReference:
    """Validated identity extracted from an R2 public URL."""

    key: str
    project_id: str
    folder: str
    filename: str
    extension: str


class R2Storage:
    def __init__(self):
        self.endpoint_url = os.getenv("R2_ENDPOINT_URL")
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("R2_BUCKET_NAME")

        if not all([
            self.endpoint_url,
            self.access_key_id,
            self.secret_access_key,
            self.bucket_name,
        ]):
            logger.warning("R2 storage is not configured")
            self.s3_client = None
            return

        try:
            self.s3_client = boto3.client(
                service_name="s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=boto3.session.Config(signature_version="s3v4"),
            )
        except Exception as exc:
            logger.exception(
                "Failed to initialize R2 client",
                error_type=type(exc).__name__,
            )
            self.s3_client = None

    @staticmethod
    def _public_domain() -> str:
        public_domain = os.getenv("R2_PUBLIC_DOMAIN", "").strip().rstrip("/")
        parsed = urlsplit(public_domain)
        if (
            not public_domain
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError("R2_PUBLIC_DOMAIN must be an absolute HTTP(S) URL")
        return public_domain

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError(f"Invalid R2 {field_name}")
        return value

    def parse_public_url(
        self,
        source_url: str,
        *,
        expected_extension: Optional[str] = None,
        allowed_folders: Optional[Set[str]] = None,
    ) -> R2ObjectReference:
        """Parse only canonical artifact URLs belonging to the configured domain."""
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("R2 artifact URL is required")
        if any(ord(character) < 32 for character in source_url):
            raise ValueError("R2 artifact URL contains control characters")

        public_domain = self._public_domain()
        configured = urlsplit(public_domain)
        candidate = urlsplit(source_url)

        if candidate.scheme != configured.scheme or candidate.netloc != configured.netloc:
            raise ValueError("R2 artifact URL does not match the configured public domain")
        if candidate.username or candidate.password or candidate.query or candidate.fragment:
            raise ValueError("R2 artifact URL must not contain credentials, query, or fragment")
        if unquote(candidate.path) != candidate.path or "\\" in candidate.path:
            raise ValueError("R2 artifact URL must use an unencoded canonical path")

        base_path = configured.path.rstrip("/")
        expected_prefix = f"{base_path}/" if base_path else "/"
        if not candidate.path.startswith(expected_prefix):
            raise ValueError("R2 artifact URL is outside the configured public path")

        object_key = candidate.path[len(expected_prefix):]
        match = OBJECT_KEY_PATTERN.fullmatch(object_key)
        if not match:
            raise ValueError("R2 artifact URL has an invalid object key")

        extension = match.group("extension")
        folder = match.group("folder")
        if expected_extension and extension != expected_extension:
            raise ValueError(f"Expected an {expected_extension} R2 artifact URL")
        if allowed_folders is not None:
            invalid_folders = set(allowed_folders) - ALLOWED_FOLDERS
            if invalid_folders:
                raise ValueError("Invalid allowed R2 folder configuration")
            if folder not in allowed_folders:
                expected = ", ".join(sorted(allowed_folders))
                raise ValueError(f"R2 artifact must be in one of these folders: {expected}")

        return R2ObjectReference(
            key=object_key,
            project_id=match.group("project_id"),
            folder=folder,
            filename=match.group("filename"),
            extension=extension,
        )

    def validate_artifact_pair(
        self,
        audio_url: str,
        srt_url: str,
        *,
        allowed_folders: Set[str],
    ) -> Tuple[R2ObjectReference, R2ObjectReference]:
        """Validate an audio/subtitle pair before any storage mutation occurs."""
        audio = self.parse_public_url(
            audio_url,
            expected_extension=".mp3",
            allowed_folders=allowed_folders,
        )
        subtitles = self.parse_public_url(
            srt_url,
            expected_extension=".srt",
            allowed_folders=allowed_folders,
        )
        if audio.project_id != subtitles.project_id:
            raise ValueError("Audio and subtitle artifacts must belong to the same project")
        if audio.folder != subtitles.folder:
            raise ValueError("Audio and subtitle artifacts must be in the same folder")
        return audio, subtitles

    def build_public_url(self, object_key: str) -> str:
        if not OBJECT_KEY_PATTERN.fullmatch(object_key):
            raise ValueError("Invalid R2 object key")
        return f"{self._public_domain()}/{object_key}"

    def upload_file(
        self,
        file_path: str,
        project_id: str,
        chapter_id: str,
        content_type: str = "audio/mpeg",
        subfolder: str = "",
    ) -> str:
        """Upload a local MP3 or SRT artifact and return its object key."""
        if not self.s3_client:
            raise RuntimeError("R2 Client is not configured")

        project_id = self._validate_identifier(project_id, "project_id")
        chapter_id = self._validate_identifier(chapter_id, "chapter_id")
        if subfolder not in {"", *ALLOWED_FOLDERS}:
            raise ValueError("Invalid R2 subfolder")

        extension = ".srt" if file_path.lower().endswith(".srt") else ".mp3"
        subfolder_path = f"{subfolder}/" if subfolder else ""
        object_key = f"projects/{project_id}/{subfolder_path}{chapter_id}{extension}"

        try:
            self.s3_client.upload_file(
                Filename=file_path,
                Bucket=self.bucket_name,
                Key=object_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "CacheControl": "max-age=31536000",
                },
            )
            logger.info(
                "R2 upload completed",
                project_id=project_id,
                folder=subfolder or "root",
                extension=extension,
            )
            return object_key
        except ClientError as exc:
            logger.exception(
                "R2 upload failed",
                project_id=project_id,
                error_code=exc.response.get("Error", {}).get("Code"),
            )
            raise

    def save_file_as_new(self, source_url: str) -> str:
        """Move a temporary artifact into saved storage; saved URLs are idempotent."""
        if not self.s3_client:
            raise RuntimeError("R2 Client is not configured")

        source = self.parse_public_url(
            source_url,
            allowed_folders={"temp", "saved"},
        )
        if source.folder == "saved":
            logger.info(
                "R2 artifact already saved",
                project_id=source.project_id,
                extension=source.extension,
            )
            return self.build_public_url(source.key)

        destination_key = (
            f"projects/{source.project_id}/saved/{uuid.uuid4()}{source.extension}"
        )
        try:
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": source.key},
                Key=destination_key,
                ACL="public-read",
            )
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=source.key,
            )
            logger.info(
                "R2 artifact saved",
                project_id=source.project_id,
                extension=source.extension,
            )
            return self.build_public_url(destination_key)
        except ClientError as exc:
            logger.exception(
                "R2 save failed",
                project_id=source.project_id,
                error_code=exc.response.get("Error", {}).get("Code"),
            )
            raise

    def delete_file(self, file_url: str) -> bool:
        """Delete a validated temporary or saved artifact."""
        if not self.s3_client:
            raise RuntimeError("R2 Client is not configured")

        source = self.parse_public_url(
            file_url,
            allowed_folders={"temp", "saved"},
        )
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=source.key,
            )
            logger.info(
                "R2 artifact deleted",
                project_id=source.project_id,
                folder=source.folder,
                extension=source.extension,
            )
            return True
        except ClientError as exc:
            logger.exception(
                "R2 delete failed",
                project_id=source.project_id,
                error_code=exc.response.get("Error", {}).get("Code"),
            )
            raise

    def move_file_to_temp(self, source_url: str) -> str:
        """Move a validated saved artifact back into temporary storage."""
        if not self.s3_client:
            raise RuntimeError("R2 Client is not configured")

        source = self.parse_public_url(
            source_url,
            allowed_folders={"temp", "saved"},
        )
        if source.folder != "saved":
            raise ValueError("Source file is not in 'saved' folder")
        destination_key = (
            f"projects/{source.project_id}/temp/{uuid.uuid4()}{source.extension}"
        )
        try:
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": source.key},
                Key=destination_key,
                ACL="public-read",
            )
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=source.key,
            )
            logger.info(
                "R2 artifact moved to temp",
                project_id=source.project_id,
                extension=source.extension,
            )
            return self.build_public_url(destination_key)
        except ClientError as exc:
            logger.exception(
                "R2 move failed",
                project_id=source.project_id,
                error_code=exc.response.get("Error", {}).get("Code"),
            )
            raise


r2_storage = R2Storage()

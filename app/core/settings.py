"""Centralized, typed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

from dotenv import load_dotenv


# Deployment-provided values win; .env only supplies local defaults.
load_dotenv(override=False)


def _optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_bool(value: Optional[str]) -> Optional[bool]:
    normalized = _optional(value)
    if normalized is None:
        return None
    return normalized.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable snapshot of environment-backed application settings."""

    environment: str
    port: int
    api_access_secret: Optional[str]
    cors_allowed_origins: Tuple[str, ...]
    log_level: str
    log_format: Optional[str]
    log_include_stacktraces: Optional[bool]
    aws_lambda_function_name: Optional[str]

    azure_speech_key: Optional[str]
    azure_speech_region: Optional[str]
    google_credentials_json: Optional[str]
    google_credentials_path: Optional[str]
    openai_api_key: Optional[str]
    openrouter_api_key: Optional[str]
    elevenlabs_api_key: Optional[str]

    r2_endpoint_url: Optional[str]
    r2_access_key_id: Optional[str]
    r2_secret_access_key: Optional[str]
    r2_bucket_name: Optional[str]
    r2_public_domain: Optional[str]
    r2_project_id: str

    @property
    def is_production(self) -> bool:
        return self.environment in {"production", "prod"}

    @property
    def include_stacktraces(self) -> bool:
        if self.log_include_stacktraces is not None:
            return self.log_include_stacktraces
        return not self.is_production

    @property
    def use_json_logs(self) -> bool:
        if self.log_format:
            return self.log_format.lower() == "json"
        return self.is_production

    @property
    def sensitive_values(self) -> Tuple[str, ...]:
        return tuple(
            value
            for value in (
                self.api_access_secret,
                self.elevenlabs_api_key,
                self.google_credentials_json,
                self.openai_api_key,
                self.r2_access_key_id,
                self.r2_secret_access_key,
            )
            if value and len(value) >= 4
        )

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        configured_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
        if configured_origins.strip():
            origins = tuple(
                origin.strip()
                for origin in configured_origins.split(",")
                if origin.strip()
            )
        elif environment in {"production", "prod"}:
            origins = ()
        else:
            origins = (
                "http://localhost:3000",
                "http://localhost:5173",
            )

        try:
            port = int(os.getenv("PORT", "8000"))
        except ValueError:
            port = 8000

        return cls(
            environment=environment,
            port=port,
            api_access_secret=_optional(os.getenv("DARMAFLOW_API_ACCESS_SECRET")),
            cors_allowed_origins=origins,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            log_format=_optional(os.getenv("LOG_FORMAT")),
            log_include_stacktraces=_optional_bool(
                os.getenv("LOG_INCLUDE_STACKTRACES")
            ),
            aws_lambda_function_name=_optional(
                os.getenv("AWS_LAMBDA_FUNCTION_NAME")
            ),
            azure_speech_key=_optional(os.getenv("AZURE_SPEECH_KEY")),
            azure_speech_region=_optional(os.getenv("AZURE_SPEECH_REGION")),
            google_credentials_json=_optional(
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            ),
            google_credentials_path=_optional(
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            ),
            openai_api_key=_optional(os.getenv("OPENAI_API_KEY")),
            openrouter_api_key=_optional(os.getenv("OPENROUTER_API_KEY")),
            elevenlabs_api_key=_optional(os.getenv("ELEVENLABS_API_KEY")),
            r2_endpoint_url=_optional(os.getenv("R2_ENDPOINT_URL")),
            r2_access_key_id=_optional(os.getenv("R2_ACCESS_KEY_ID")),
            r2_secret_access_key=_optional(os.getenv("R2_SECRET_ACCESS_KEY")),
            r2_bucket_name=_optional(os.getenv("R2_BUCKET_NAME")),
            r2_public_domain=_optional(os.getenv("R2_PUBLIC_DOMAIN")),
            r2_project_id=os.getenv("R2_PROJECT_ID", "Railway").strip() or "Railway",
        )


def get_settings() -> Settings:
    """Return a fresh snapshot so tests and runtime env updates stay observable."""
    return Settings.from_env()

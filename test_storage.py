"""Unit tests for Cloudflare R2 object lifecycle operations."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from app.services.storage import R2Storage


class R2StorageTests(unittest.TestCase):
    def setUp(self):
        self.storage = R2Storage.__new__(R2Storage)
        self.storage.bucket_name = "test-bucket"
        self.storage.s3_client = MagicMock()
        self.environment = patch.dict(
            os.environ,
            {"R2_PUBLIC_DOMAIN": "https://cdn.example.test"},
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_upload_uses_expected_key_metadata_and_cache_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "subtitles.srt"
            source.write_text("subtitle", encoding="utf-8")

            key = self.storage.upload_file(
                file_path=str(source),
                project_id="DramaFlow",
                chapter_id="chapter-1",
                content_type="application/x-subrip",
                subfolder="temp",
            )

        self.assertEqual(key, "projects/DramaFlow/temp/chapter-1.srt")
        self.storage.s3_client.upload_file.assert_called_once_with(
            Filename=str(source),
            Bucket="test-bucket",
            Key="projects/DramaFlow/temp/chapter-1.srt",
            ExtraArgs={
                "ContentType": "application/x-subrip",
                "CacheControl": "max-age=31536000",
            },
        )

    def test_saving_temp_file_copies_then_deletes_source(self):
        with patch("uuid.uuid4", return_value="saved-id"):
            result = self.storage.save_file_as_new(
                "https://cdn.example.test/projects/DramaFlow/temp/source.mp3"
            )

        self.storage.s3_client.copy_object.assert_called_once_with(
            Bucket="test-bucket",
            CopySource={
                "Bucket": "test-bucket",
                "Key": "projects/DramaFlow/temp/source.mp3",
            },
            Key="projects/DramaFlow/saved/saved-id.mp3",
            ACL="public-read",
        )
        self.storage.s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="projects/DramaFlow/temp/source.mp3",
        )
        self.assertEqual(
            result,
            "https://cdn.example.test/projects/DramaFlow/saved/saved-id.mp3",
        )

    def test_saving_an_already_saved_file_is_idempotent(self):
        source = "https://cdn.example.test/projects/DramaFlow/saved/source.srt"

        result = self.storage.save_file_as_new(source)

        self.assertEqual(result, source)
        self.storage.s3_client.copy_object.assert_not_called()
        self.storage.s3_client.delete_object.assert_not_called()

    def test_move_saved_file_to_temp_copies_then_deletes_source(self):
        with patch("uuid.uuid4", return_value="temp-id"):
            result = self.storage.move_file_to_temp(
                "https://cdn.example.test/projects/DramaFlow/saved/source.srt"
            )

        self.assertEqual(
            self.storage.s3_client.method_calls,
            [
                call.copy_object(
                    Bucket="test-bucket",
                    CopySource={
                        "Bucket": "test-bucket",
                        "Key": "projects/DramaFlow/saved/source.srt",
                    },
                    Key="projects/DramaFlow/temp/temp-id.srt",
                    ACL="public-read",
                ),
                call.delete_object(
                    Bucket="test-bucket",
                    Key="projects/DramaFlow/saved/source.srt",
                ),
            ],
        )
        self.assertEqual(
            result,
            "https://cdn.example.test/projects/DramaFlow/temp/temp-id.srt",
        )

    def test_move_to_temp_rejects_non_saved_source(self):
        with self.assertRaisesRegex(ValueError, "not in 'saved'"):
            self.storage.move_file_to_temp(
                "https://cdn.example.test/projects/DramaFlow/temp/source.mp3"
            )
        self.storage.s3_client.copy_object.assert_not_called()

    def test_delete_uses_object_key_from_public_url(self):
        deleted = self.storage.delete_file(
            "https://cdn.example.test/projects/DramaFlow/temp/source.mp3"
        )

        self.assertTrue(deleted)
        self.storage.s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="projects/DramaFlow/temp/source.mp3",
        )

    def test_rejects_noncanonical_or_foreign_urls_before_mutation(self):
        invalid_urls = [
            "https://cdn.example.test.evil/projects/DramaFlow/temp/source.mp3",
            "http://cdn.example.test/projects/DramaFlow/temp/source.mp3",
            "https://cdn.example.test/projects/DramaFlow/temp/source.mp3?download=1",
            "https://cdn.example.test/projects/DramaFlow/temp/source.mp3#fragment",
            "https://cdn.example.test/projects/DramaFlow/temp/%2e%2e/source.mp3",
            "https://cdn.example.test/projects/DramaFlow/archive/source.mp3",
            "https://cdn.example.test/projects/DramaFlow/temp/source.wav",
            "https://cdn.example.test/projects/DramaFlow/temp//source.mp3",
        ]

        for invalid_url in invalid_urls:
            with self.subTest(invalid_url=invalid_url):
                with self.assertRaises(ValueError):
                    self.storage.delete_file(invalid_url)

        self.storage.s3_client.delete_object.assert_not_called()

    def test_validates_extension_and_artifact_pair_ownership(self):
        with self.assertRaisesRegex(ValueError, "Expected an .srt"):
            self.storage.parse_public_url(
                "https://cdn.example.test/projects/DramaFlow/temp/source.mp3",
                expected_extension=".srt",
            )

        with self.assertRaisesRegex(ValueError, "same project"):
            self.storage.validate_artifact_pair(
                "https://cdn.example.test/projects/ProjectA/temp/source.mp3",
                "https://cdn.example.test/projects/ProjectB/temp/source.srt",
                allowed_folders={"temp", "saved"},
            )

        with self.assertRaisesRegex(ValueError, "same folder"):
            self.storage.validate_artifact_pair(
                "https://cdn.example.test/projects/DramaFlow/temp/source.mp3",
                "https://cdn.example.test/projects/DramaFlow/saved/source.srt",
                allowed_folders={"temp", "saved"},
            )

    def test_configured_public_domain_may_include_a_base_path(self):
        with patch.dict(
            os.environ,
            {"R2_PUBLIC_DOMAIN": "https://cdn.example.test/assets"},
        ):
            reference = self.storage.parse_public_url(
                "https://cdn.example.test/assets/"
                "projects/DramaFlow/temp/source.mp3"
            )

        self.assertEqual(
            reference.key,
            "projects/DramaFlow/temp/source.mp3",
        )

    def test_unconfigured_storage_fails_before_network_access(self):
        self.storage.s3_client = None

        with self.assertRaisesRegex(RuntimeError, "not configured"):
            self.storage.upload_file(
                file_path="audio.mp3",
                project_id="DramaFlow",
                chapter_id="chapter-1",
            )


if __name__ == "__main__":
    unittest.main()

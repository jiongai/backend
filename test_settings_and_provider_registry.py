"""Tests for centralized settings and provider dependency injection."""

import os
import unittest
from unittest.mock import patch

from app.core.settings import get_settings
from app.services.audio_engine import TTSManager
from app.services.tts import build_tts_providers


class SettingsTests(unittest.TestCase):
    def test_explicit_cors_origins_are_normalized(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "CORS_ALLOWED_ORIGINS": (
                    "https://app.example.test, https://admin.example.test"
                ),
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertTrue(settings.is_production)
        self.assertEqual(
            settings.cors_allowed_origins,
            (
                "https://app.example.test",
                "https://admin.example.test",
            ),
        )

    def test_production_defaults_to_no_cors_origins(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            settings = get_settings()

        self.assertEqual(settings.cors_allowed_origins, ())
        self.assertFalse(settings.include_stacktraces)
        self.assertTrue(settings.use_json_logs)


class ProviderRegistryTests(unittest.TestCase):
    def test_registry_contains_every_supported_provider(self):
        providers = build_tts_providers()

        self.assertEqual(
            set(providers),
            {"azure", "google", "openai", "elevenlabs"},
        )

    def test_manager_accepts_an_injected_registry(self):
        manager = TTSManager(providers={})

        self.assertEqual(manager.providers, {})


if __name__ == "__main__":
    unittest.main()

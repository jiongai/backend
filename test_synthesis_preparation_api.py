"""API regression tests for voice preparation and credential checks."""

import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app.main as main_module
from app.services.audio_engine import tts_manager


class SynthesisPreparationApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main_module.app, raise_server_exceptions=False)
        self.headers = {
            "X-Access-Secret": os.getenv("DARMAFLOW_API_ACCESS_SECRET", "")
        }

    @patch("app.api.routes.synthesis.synthesize_drama", new_callable=AsyncMock)
    def test_empty_voice_is_prepared_before_synthesis(self, synthesize_mock):
        synthesize_mock.return_value = {
            "audio_url": "audio.mp3",
            "srt_url": "audio.srt",
            "timeline": [],
        }
        google = tts_manager.providers["google"]
        original_enabled = google._enabled
        try:
            google._enabled = True
            response = self.client.post(
                "/synthesize",
                headers=self.headers,
                json={
                    "script": [
                        {
                            "type": "narration",
                            "text": "A quiet night.",
                            "character": "Narrator",
                            "gender": "female",
                            "emotion": "neutral",
                            "pacing": 1.0,
                            "voice_id": "",
                        }
                    ]
                },
            )
        finally:
            google._enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        prepared = synthesize_mock.await_args.kwargs["script"]
        self.assertTrue(prepared[0]["voice_id"].startswith("google:"))
        self.assertEqual(prepared[0]["gender"], "neutral")

    @patch("app.api.routes.synthesis.synthesize_drama", new_callable=AsyncMock)
    def test_google_script_does_not_require_elevenlabs_key(self, synthesize_mock):
        synthesize_mock.return_value = {
            "audio_url": "audio.mp3",
            "srt_url": "audio.srt",
            "timeline": [],
        }
        google = tts_manager.providers["google"]
        original_enabled = google._enabled
        try:
            google._enabled = True
            with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}):
                response = self.client.post(
                    "/synthesize",
                    headers=self.headers,
                    json={
                        "script": [
                            {
                                "type": "dialogue",
                                "text": "Hello.",
                                "character": "Alice",
                                "gender": "female",
                                "emotion": "neutral",
                                "pacing": 1.0,
                                "voice_id": "google:en-US-Neural2-F",
                            }
                        ]
                    },
                )
        finally:
            google._enabled = original_enabled

        self.assertEqual(response.status_code, 200)
        synthesize_mock.assert_awaited_once()

    @patch("app.api.routes.synthesis.synthesize_drama", new_callable=AsyncMock)
    def test_elevenlabs_script_requires_elevenlabs_key(self, synthesize_mock):
        elevenlabs = tts_manager.providers["elevenlabs"]
        original_key = elevenlabs.default_key
        original_enabled = elevenlabs._enabled
        try:
            elevenlabs.default_key = None
            elevenlabs._enabled = True
            with patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}):
                response = self.client.post(
                    "/synthesize",
                    headers=self.headers,
                    json={
                        "script": [
                            {
                                "type": "dialogue",
                                "text": "Hello.",
                                "character": "Alice",
                                "gender": "female",
                                "emotion": "neutral",
                                "pacing": 1.0,
                                "voice_id": "elevenlabs:21m00Tcm4TlvDq8ikWAM",
                            }
                        ]
                    },
                )
        finally:
            elevenlabs.default_key = original_key
            elevenlabs._enabled = original_enabled

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["providers"],
            ["elevenlabs"],
        )
        synthesize_mock.assert_not_awaited()

    def test_limit_zero_skips_provider_checks(self):
        response = self.client.post(
            "/synthesize",
            headers=self.headers,
            json={
                "script": [
                    {
                        "type": "dialogue",
                        "text": "This segment must not reach a provider.",
                        "character": "Alice",
                        "gender": "female",
                        "emotion": "neutral",
                        "pacing": 1.0,
                        "voice_id": "elevenlabs:21m00Tcm4TlvDq8ikWAM",
                    }
                ],
                "limit": 0,
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_conflicting_narrator_voices_return_422(self):
        response = self.client.post(
            "/synthesize",
            headers=self.headers,
            json={
                "script": [
                    {
                        "type": "narration",
                        "text": "First.",
                        "character": "Narrator",
                        "gender": "male",
                        "voice_id": "openai:onyx",
                    },
                    {
                        "type": "narration",
                        "text": "Second.",
                        "character": "Narrator",
                        "gender": "female",
                        "voice_id": "openai:alloy",
                    },
                ]
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

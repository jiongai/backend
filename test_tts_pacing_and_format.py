"""Regression tests for provider-native pacing and MP3 output contracts."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pydub import AudioSegment
from pydantic import ValidationError

from app.main import ReviewRequest
from app.services.audio_engine import TTSManager
from app.services.post_production import merge_audio_and_generate_srt
from app.services.tts_providers import (
    AzureTTSProvider,
    ElevenLabsTTSProvider,
    GoogleTTSProvider,
    OpenAITTSProvider,
)


class ProviderPacingAndFormatTests(unittest.TestCase):
    def test_review_rejects_pacing_outside_supported_range(self):
        for pacing in (0.24, 4.01, None):
            with self.subTest(pacing=pacing):
                with self.assertRaises(ValidationError):
                    ReviewRequest(
                        text="Hello",
                        voice_id="google:en-US-Neural2-F",
                        pacing=pacing,
                    )

    def test_azure_uses_ssml_pacing_and_mp3_output(self):
        captured = {}

        class FakeSpeechConfig:
            def __init__(self, **kwargs):
                pass

            def set_speech_synthesis_output_format(self, output_format):
                captured["output_format"] = output_format

        class FakeSynthesizer:
            def __init__(self, **kwargs):
                pass

            def speak_ssml_async(self, ssml):
                captured["ssml"] = ssml
                return SimpleNamespace(
                    get=lambda: SimpleNamespace(reason="completed")
                )

        fake_sdk = SimpleNamespace(
            SpeechConfig=FakeSpeechConfig,
            SpeechSynthesisOutputFormat=SimpleNamespace(
                Audio48Khz192KBitRateMonoMp3="mp3-48khz-192k"
            ),
            SpeechSynthesizer=FakeSynthesizer,
            ResultReason=SimpleNamespace(Canceled="canceled"),
            audio=SimpleNamespace(AudioOutputConfig=lambda **kwargs: object()),
        )

        with patch("app.services.tts_providers.speechsdk", fake_sdk):
            provider = AzureTTSProvider()
            provider._enabled = True
            asyncio.run(provider.generate(
                "A < B & C",
                "unused.mp3",
                "en-US-BrianNeural",
                speed=1.25,
            ))

        self.assertEqual(captured["output_format"], "mp3-48khz-192k")
        self.assertIn('rate="+25%"', captured["ssml"])
        self.assertIn("A &lt; B &amp; C", captured["ssml"])

    def test_google_requests_mp3_and_native_speed(self):
        provider = GoogleTTSProvider()
        provider._enabled = True
        client = MagicMock()
        client.synthesize_speech.return_value = SimpleNamespace(audio_content=b"mp3")
        provider._client = client

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "google.mp3"
            asyncio.run(provider.generate(
                "Hello",
                str(output),
                "en-US-Neural2-F",
                speed=1.2,
            ))

        audio_config = client.synthesize_speech.call_args.kwargs["audio_config"]
        self.assertEqual(audio_config.audio_encoding, 2)  # Google MP3 enum value
        self.assertEqual(audio_config.speaking_rate, 1.2)

    def test_openai_explicitly_requests_mp3_and_speed(self):
        captured = {}

        class FakeResponse:
            def stream_to_file(self, output_file):
                Path(output_file).write_bytes(b"mp3")

        async def create(**kwargs):
            captured.update(kwargs)
            return FakeResponse()

        provider = OpenAITTSProvider()
        provider._enabled = True
        provider._client = SimpleNamespace(
            audio=SimpleNamespace(speech=SimpleNamespace(create=create))
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            asyncio.run(provider.generate(
                "Hello",
                str(Path(temp_dir) / "openai.mp3"),
                "alloy",
                speed=0.9,
            ))

        self.assertEqual(captured["response_format"], "mp3")
        self.assertEqual(captured["speed"], 0.9)

    def test_elevenlabs_requests_mp3_and_native_speed(self):
        captured = {}

        class FakeTextToSpeech:
            def convert(self, **kwargs):
                captured.update(kwargs)
                return iter([b"mp3"])

        class FakeClient:
            def __init__(self, api_key):
                self.text_to_speech = FakeTextToSpeech()

        with patch("app.services.tts_providers.ElevenLabs", FakeClient):
            provider = ElevenLabsTTSProvider()
            with tempfile.TemporaryDirectory() as temp_dir:
                asyncio.run(provider.generate(
                    "Hello",
                    str(Path(temp_dir) / "elevenlabs.mp3"),
                    "voice-id",
                    speed=1.1,
                    api_key="test-key",
                    settings={"stability": 0.5},
                ))

        self.assertEqual(captured["output_format"], "mp3_44100_128")
        self.assertEqual(captured["voice_settings"].speed, 1.1)

    def test_audio_engine_forwards_pacing_to_elevenlabs(self):
        manager = TTSManager()
        provider = SimpleNamespace(generate=MagicMock())

        async def generate(**kwargs):
            provider.generate(**kwargs)

        manager.providers["elevenlabs"] = SimpleNamespace(generate=generate)
        asyncio.run(manager.generate(
            {
                "type": "dialogue",
                "text": "Hello",
                "character": "Alice",
                "gender": "female",
                "emotion": "neutral",
                "pacing": 1.15,
                "voice_id": "elevenlabs:voice-id",
            },
            "unused.mp3",
            elevenlabs_key="test-key",
        ))

        self.assertEqual(provider.generate.call_args.kwargs["speed"], 1.15)

    def test_post_production_does_not_apply_pacing_again(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.mp3"
            AudioSegment.silent(duration=1000).export(source, format="mp3").close()
            final_audio, _, timeline = merge_audio_and_generate_srt(
                [{
                    "audio_file_path": str(source),
                    "text": "Already paced by provider.",
                    "character": "Narrator",
                    "pacing": 2.0,
                }],
                temp_dir,
            )

            duration = len(AudioSegment.from_file(final_audio))

        self.assertGreaterEqual(duration, 950)
        self.assertLessEqual(duration, 1050)
        self.assertGreaterEqual(timeline[0]["end"], 950)


if __name__ == "__main__":
    unittest.main()

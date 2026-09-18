"""Regression tests for the free editor's timing and server-metered previews."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from pydub import AudioSegment
from pydantic import ValidationError
from app.main import app
from app.models.script import ScriptSegment
from app.services.post_production import merge_audio_and_generate_srt


class FreeAudioTests(unittest.TestCase):
    def test_pause_changes_audio_and_subtitle_timeline(self):
        for pause in [0, 1200, 3000]:
            with self.subTest(pause=pause), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "source.wav"
                AudioSegment.silent(duration=500).export(source, format="wav").close()
                audio, subtitles, timeline = merge_audio_and_generate_srt([
                    {"audio_file_path": str(source), "text": "One", "pause_after_ms": pause},
                    {"audio_file_path": str(source), "text": "Two"},
                ], directory)
                self.assertEqual(timeline[1]["start"], 500 + pause)
                self.assertEqual(timeline[1]["end"], 1000 + pause)
                self.assertAlmostEqual(len(AudioSegment.from_file(audio)), 1000 + pause, delta=10)
                self.assertTrue(Path(subtitles).exists())

    def test_pause_validation(self):
        segment = {"type": "dialogue", "text": "Hi", "character": "Alice", "gender": "female"}
        self.assertEqual(ScriptSegment(**segment).pause_after_ms, 300)
        for pause in [-1, 3001]:
            with self.assertRaises(ValidationError):
                ScriptSegment(**segment, pause_after_ms=pause)

    def test_review_returns_actual_duration_header(self):
        async def generate(**kwargs):
            target = Path(kwargs["output_dir"]) / "preview.mp3"
            AudioSegment.silent(duration=650).export(target, format="mp3").close()
        with patch("app.api.routes.voices.generate_segment_audio", AsyncMock(side_effect=generate)), patch(
            "app.api.routes.voices.tts_manager.get_missing_provider_credentials", return_value=[]
        ):
            response = TestClient(app).post("/review", headers={"X-Access-Secret": os.getenv("DARMAFLOW_API_ACCESS_SECRET", "")},
                json={"text": "Hello", "voice_id": "google:en-US-Neural2-A"})
        self.assertEqual(response.status_code, 200)
        self.assertAlmostEqual(int(response.headers["x-audio-duration-ms"]), 650, delta=10)
        self.assertGreater(len(response.content), 0)


if __name__ == "__main__":
    unittest.main()

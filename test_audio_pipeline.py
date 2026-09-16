"""Unit tests for generated-file contracts and timeline production."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from pydub import AudioSegment

from app.services.audio_engine import generate_segment_audio
from app.services.post_production import (
    format_timestamp,
    merge_audio_and_generate_srt,
)


SEGMENT = {
    "type": "dialogue",
    "text": "Hello.",
    "character": "Alice",
    "gender": "female",
    "emotion": "neutral",
    "pacing": 1.0,
    "voice_id": "google:en-US-Neural2-F",
}


class GeneratedFileContractTests(unittest.TestCase):
    def test_generated_audio_must_exist_and_be_nonempty(self):
        for write_mode in ("missing", "empty"):
            with self.subTest(write_mode=write_mode):
                async def fake_generate(segment, output_file, **kwargs):
                    if write_mode == "empty":
                        Path(output_file).touch()

                with tempfile.TemporaryDirectory() as temp_dir:
                    with patch(
                        "app.services.audio_engine.tts_manager.generate",
                        AsyncMock(side_effect=fake_generate),
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "did not produce audio",
                        ):
                            asyncio.run(generate_segment_audio(
                                segment=dict(SEGMENT),
                                output_dir=temp_dir,
                            ))

    def test_generated_audio_path_is_returned_after_success(self):
        async def fake_generate(segment, output_file, **kwargs):
            Path(output_file).write_bytes(b"valid audio bytes")

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "app.services.audio_engine.tts_manager.generate",
                AsyncMock(side_effect=fake_generate),
            ):
                result = asyncio.run(generate_segment_audio(
                    segment=dict(SEGMENT),
                    output_dir=temp_dir,
                ))

            output = Path(result)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)
            self.assertEqual(output.suffix, ".mp3")


class PostProductionTimelineTests(unittest.TestCase):
    def test_two_segments_include_gap_and_character_in_subtitles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.wav"
            second = Path(temp_dir) / "second.wav"
            AudioSegment.silent(duration=500).export(first, format="wav").close()
            AudioSegment.silent(duration=700).export(second, format="wav").close()

            audio_path, srt_path, timeline = merge_audio_and_generate_srt(
                [
                    {
                        "audio_file_path": str(first),
                        "text": "The door opened.",
                        "character": "Narrator",
                    },
                    {
                        "audio_file_path": str(second),
                        "text": "Who's there?",
                        "character": "Alice",
                    },
                ],
                temp_dir,
            )

            srt = Path(srt_path).read_text(encoding="utf-8")
            duration = len(AudioSegment.from_file(audio_path))

        self.assertEqual(timeline, [
            {"index": 1, "start": 0, "end": 500},
            {"index": 2, "start": 800, "end": 1500},
        ])
        self.assertIn("00:00:00,000 --> 00:00:00,500", srt)
        self.assertIn("The door opened.", srt)
        self.assertIn("00:00:00,800 --> 00:00:01,500", srt)
        self.assertIn("[Alice] Who's there?", srt)
        self.assertGreaterEqual(duration, 1490)
        self.assertLessEqual(duration, 1510)

    def test_rejects_empty_segments_and_missing_audio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "No segments"):
                merge_audio_and_generate_srt([], temp_dir)

            with self.assertRaisesRegex(ValueError, "Audio file not found"):
                merge_audio_and_generate_srt(
                    [{
                        "audio_file_path": str(Path(temp_dir) / "missing.mp3"),
                        "text": "Missing.",
                    }],
                    temp_dir,
                )

    def test_timestamp_supports_hour_boundaries(self):
        self.assertEqual(format_timestamp(3_723_004), "01:02:03,004")


if __name__ == "__main__":
    unittest.main()

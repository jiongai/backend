"""Unit tests for the production synthesis orchestrator."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, call, patch

import app.services.synthesizer as synthesizer_module


def make_segment(segment_type, text, character, gender, voice_id):
    return {
        "type": segment_type,
        "text": text,
        "character": character,
        "gender": gender,
        "emotion": "neutral",
        "pacing": 1.0,
        "voice_id": voice_id,
    }


class SynthesizeDramaTests(unittest.TestCase):
    def test_full_pipeline_preserves_script_order_and_uploads_artifacts(self):
        script = [
            make_segment(
                "dialogue",
                "I speak first.",
                "Alice",
                "female",
                "google:en-US-Neural2-F",
            ),
            make_segment(
                "narration",
                "The room became quiet.",
                "Someone",
                "male",
                "google:en-US-Neural2-J",
            ),
            make_segment(
                "dialogue",
                "I speak last.",
                "Bob",
                "male",
                "google:en-US-Neural2-J",
            ),
        ]

        async def generate_audio(segment, output_dir, **kwargs):
            output = Path(output_dir) / f"{segment['character']}.mp3"
            output.write_bytes(b"audio")
            return str(output)

        with tempfile.TemporaryDirectory() as temp_dir:
            final_audio = Path(temp_dir) / "final.mp3"
            final_srt = Path(temp_dir) / "final.srt"
            final_audio.write_bytes(b"mixed audio")
            final_srt.write_text("subtitles", encoding="utf-8")
            timeline = [
                {"index": 1, "start": 0, "end": 100},
                {"index": 2, "start": 400, "end": 600},
                {"index": 3, "start": 900, "end": 1000},
            ]

            generate_mock = AsyncMock(side_effect=generate_audio)
            with (
                patch.object(
                    synthesizer_module,
                    "generate_segment_audio",
                    generate_mock,
                ),
                patch.object(
                    synthesizer_module,
                    "merge_audio_and_generate_srt",
                    return_value=(str(final_audio), str(final_srt), timeline),
                ) as merge_mock,
                patch.object(
                    synthesizer_module.r2_storage,
                    "upload_file",
                    side_effect=[
                        "projects/TestProject/temp/chapter.mp3",
                        "projects/TestProject/temp/chapter.srt",
                    ],
                ) as upload_mock,
                patch.object(
                    synthesizer_module,
                    "uuid4",
                    return_value="chapter-id",
                ),
                patch.dict(
                    os.environ,
                    {
                        "R2_PROJECT_ID": "TestProject",
                        "R2_PUBLIC_DOMAIN": "https://cdn.example.test/",
                    },
                ),
            ):
                result = asyncio.run(synthesizer_module.synthesize_drama(
                    script=script,
                    temp_dir=temp_dir,
                    elevenlabs_key=None,
                    user_tier="free",
                ))

            generated_characters = [
                awaited.kwargs["segment"]["character"]
                for awaited in generate_mock.await_args_list
            ]
            self.assertEqual(generated_characters, ["Narrator", "Alice", "Bob"])

            merged_segments = merge_mock.call_args.kwargs["segments"]
            self.assertEqual(
                [segment["text"] for segment in merged_segments],
                ["I speak first.", "The room became quiet.", "I speak last."],
            )
            self.assertEqual(
                [Path(segment["audio_file_path"]).name for segment in merged_segments],
                ["Alice.mp3", "Narrator.mp3", "Bob.mp3"],
            )

            self.assertEqual(upload_mock.call_count, 2)
            self.assertEqual(
                upload_mock.call_args_list,
                [
                    call(
                        file_path=str(final_audio),
                        project_id="TestProject",
                        chapter_id="chapter-id",
                        content_type="audio/mpeg",
                        subfolder="temp",
                    ),
                    call(
                        file_path=str(final_srt),
                        project_id="TestProject",
                        chapter_id="chapter-id",
                        content_type="application/x-subrip",
                        subfolder="temp",
                    ),
                ],
            )
            self.assertEqual(result, {
                "audio_url": (
                    "https://cdn.example.test/"
                    "projects/TestProject/temp/chapter.mp3"
                ),
                "srt_url": (
                    "https://cdn.example.test/"
                    "projects/TestProject/temp/chapter.srt"
                ),
                "timeline": timeline,
            })
            self.assertFalse(final_audio.exists())
            self.assertFalse(final_srt.exists())

        # Preparation must not mutate the request-owned script.
        self.assertNotIn("audio_file_path", script[0])
        self.assertEqual(script[1]["character"], "Someone")

    def test_generation_failure_is_identified_by_phase(self):
        script = [
            make_segment(
                "narration",
                "A quiet night.",
                "Narrator",
                "neutral",
                "google:en-US-Neural2-J",
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(
                synthesizer_module,
                "generate_segment_audio",
                AsyncMock(side_effect=RuntimeError("provider unavailable")),
            ):
                with self.assertRaisesRegex(
                    Exception,
                    "Narration generation failed: provider unavailable",
                ):
                    asyncio.run(synthesizer_module.synthesize_drama(
                        script=script,
                        temp_dir=temp_dir,
                        elevenlabs_key=None,
                    ))

    def test_post_production_failure_is_identified_by_phase(self):
        script = [
            make_segment(
                "dialogue",
                "Hello.",
                "Alice",
                "female",
                "google:en-US-Neural2-F",
            )
        ]

        async def generate_audio(segment, output_dir, **kwargs):
            output = Path(output_dir) / "segment.mp3"
            output.write_bytes(b"audio")
            return str(output)

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(
                    synthesizer_module,
                    "generate_segment_audio",
                    AsyncMock(side_effect=generate_audio),
                ),
                patch.object(
                    synthesizer_module,
                    "merge_audio_and_generate_srt",
                    side_effect=ValueError("bad audio"),
                ),
            ):
                with self.assertRaisesRegex(
                    Exception,
                    "Post-production failed: bad audio",
                ):
                    asyncio.run(synthesizer_module.synthesize_drama(
                        script=script,
                        temp_dir=temp_dir,
                        elevenlabs_key=None,
                    ))

    def test_dialogue_generation_is_limited_to_three_concurrent_calls(self):
        script = [
            make_segment(
                "dialogue",
                f"Line {index}.",
                f"Character{index}",
                "male",
                "elevenlabs:voice-id",
            )
            for index in range(6)
        ]
        active_calls = 0
        maximum_active_calls = 0

        async def generate_audio(segment, output_dir, **kwargs):
            nonlocal active_calls, maximum_active_calls
            active_calls += 1
            maximum_active_calls = max(maximum_active_calls, active_calls)
            try:
                await asyncio.sleep(0.01)
                output = Path(output_dir) / f"{segment['character']}.mp3"
                output.write_bytes(b"audio")
                return str(output)
            finally:
                active_calls -= 1

        with tempfile.TemporaryDirectory() as temp_dir:
            final_audio = Path(temp_dir) / "final.mp3"
            final_srt = Path(temp_dir) / "final.srt"
            final_audio.write_bytes(b"mixed audio")
            final_srt.write_text("subtitles", encoding="utf-8")

            with (
                patch.object(
                    synthesizer_module,
                    "generate_segment_audio",
                    AsyncMock(side_effect=generate_audio),
                ),
                patch.object(
                    synthesizer_module,
                    "merge_audio_and_generate_srt",
                    return_value=(str(final_audio), str(final_srt), []),
                ),
                patch.object(
                    synthesizer_module.r2_storage,
                    "upload_file",
                    side_effect=[
                        "projects/LocalHost8000/temp/audio.mp3",
                        "projects/LocalHost8000/temp/audio.srt",
                    ],
                ),
                patch.dict(
                    os.environ,
                    {"R2_PUBLIC_DOMAIN": "https://cdn.example.test"},
                ),
            ):
                asyncio.run(synthesizer_module.synthesize_drama(
                    script=script,
                    temp_dir=temp_dir,
                    elevenlabs_key="test-key",
                    user_tier="vip",
                ))

        self.assertEqual(maximum_active_calls, 3)


if __name__ == "__main__":
    unittest.main()

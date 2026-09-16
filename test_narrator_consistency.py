"""Regression tests for script preparation and narrator consistency."""

import unittest

from app.services.audio_engine import tts_manager


def segment(
    segment_type: str,
    text: str,
    character: str,
    gender: str,
    voice_id: str = "",
) -> dict:
    return {
        "type": segment_type,
        "text": text,
        "character": character,
        "gender": gender,
        "emotion": "neutral",
        "pacing": 1.0,
        "voice_id": voice_id,
    }


class ScriptPreparationTests(unittest.TestCase):
    def test_empty_voices_are_filled(self):
        script = [
            segment("narration", "A quiet night.", "Narrator", "female"),
            segment("dialogue", "Who is there?", "Alice", "female"),
        ]

        prepared = tts_manager.prepare_script(script, user_tier="free")

        self.assertTrue(all(item["voice_id"] for item in prepared))
        self.assertTrue(all(":" in item["voice_id"] for item in prepared))
        self.assertEqual(script[0]["voice_id"], "")
        self.assertEqual(script[1]["voice_id"], "")

    def test_narrator_voice_is_independent_of_segment_gender(self):
        script = [
            segment("narration", "First passage.", "Narrator", "male"),
            segment("narration", "Second passage.", "Someone Else", "female"),
            segment("narration", "Third passage.", "Narrator", "neutral"),
        ]

        prepared = tts_manager.prepare_script(script, user_tier="free")

        voices = {item["voice_id"] for item in prepared}
        self.assertEqual(len(voices), 1)
        self.assertTrue(all(item["character"] == "Narrator" for item in prepared))
        self.assertTrue(all(item["gender"] == "neutral" for item in prepared))

    def test_one_manual_narrator_voice_is_applied_to_all_narration(self):
        script = [
            segment(
                "narration",
                "First passage.",
                "Narrator",
                "male",
                "openai:onyx",
            ),
            segment("narration", "Second passage.", "Narrator", "female"),
        ]

        prepared = tts_manager.prepare_script(script, user_tier="free")

        self.assertEqual(
            [item["voice_id"] for item in prepared],
            ["openai:onyx", "openai:onyx"],
        )

    def test_conflicting_manual_narrator_voices_are_rejected(self):
        script = [
            segment(
                "narration",
                "First passage.",
                "Narrator",
                "neutral",
                "openai:onyx",
            ),
            segment(
                "narration",
                "Second passage.",
                "Narrator",
                "neutral",
                "openai:alloy",
            ),
        ]

        with self.assertRaisesRegex(ValueError, "same voice_id"):
            tts_manager.prepare_script(script, user_tier="free")

    def test_manual_dialogue_voice_is_preserved(self):
        script = [
            segment(
                "dialogue",
                "Leave now.",
                "Alice",
                "female",
                "elevenlabs:21m00Tcm4TlvDq8ikWAM",
            )
        ]

        prepared = tts_manager.prepare_script(script, user_tier="free")

        self.assertEqual(
            prepared[0]["voice_id"],
            "elevenlabs:21m00Tcm4TlvDq8ikWAM",
        )

    def test_required_providers_come_from_final_voice_ids(self):
        script = [
            segment(
                "dialogue",
                "Hello.",
                "Alice",
                "female",
                "google:en-US-Neural2-F",
            ),
            segment(
                "dialogue",
                "Welcome.",
                "Bob",
                "male",
                "openai:onyx",
            ),
        ]

        self.assertEqual(
            tts_manager.get_required_providers(script),
            {"google", "openai"},
        )

    def test_google_request_never_requires_elevenlabs_credentials(self):
        missing = tts_manager.get_missing_provider_credentials({"google"})
        self.assertNotIn("elevenlabs", missing)

    def test_elevenlabs_credential_is_checked_only_when_required(self):
        provider = tts_manager.providers["elevenlabs"]
        original_key = provider.default_key
        original_enabled = provider._enabled
        try:
            provider.default_key = None
            provider._enabled = True
            self.assertEqual(
                tts_manager.get_missing_provider_credentials({"elevenlabs"}),
                ["elevenlabs"],
            )
            self.assertEqual(
                tts_manager.get_missing_provider_credentials(
                    {"elevenlabs"},
                    elevenlabs_key="request-key",
                ),
                [],
            )
        finally:
            provider.default_key = original_key
            provider._enabled = original_enabled


if __name__ == "__main__":
    unittest.main()

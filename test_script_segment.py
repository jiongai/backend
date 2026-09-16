"""Unit tests for strict script segment validation."""

import unittest

from pydantic import ValidationError

from app.models import ScriptSegment


VALID_SEGMENT = {
    "type": "dialogue",
    "text": "Hello there.",
    "character": "Alice",
    "gender": "female",
    "emotion": "neutral",
    "pacing": 1.0,
    "voice_id": "google:en-US-Neural2-F",
}


class ScriptSegmentTests(unittest.TestCase):
    def test_accepts_valid_segment(self):
        segment = ScriptSegment.model_validate(VALID_SEGMENT)

        self.assertEqual(segment.type, "dialogue")
        self.assertEqual(segment.voice_id, "google:en-US-Neural2-F")

    def test_applies_optional_defaults(self):
        segment = ScriptSegment.model_validate({
            "type": "narration",
            "text": "A quiet night.",
            "character": "Narrator",
            "gender": "neutral",
        })

        self.assertEqual(segment.emotion, "neutral")
        self.assertEqual(segment.pacing, 1.0)
        self.assertEqual(segment.voice_id, "")

    def test_trims_string_fields(self):
        segment = ScriptSegment.model_validate({
            **VALID_SEGMENT,
            "text": "  Hello there.  ",
            "character": "  Alice  ",
        })

        self.assertEqual(segment.text, "Hello there.")
        self.assertEqual(segment.character, "Alice")

    def test_rejects_invalid_segments(self):
        invalid_segments = {
            "unknown field": {**VALID_SEGMENT, "unexpected": True},
            "unknown type": {**VALID_SEGMENT, "type": "sound_effect"},
            "blank text": {**VALID_SEGMENT, "text": "   "},
            "missing character": {
                key: value
                for key, value in VALID_SEGMENT.items()
                if key != "character"
            },
            "missing gender": {
                key: value
                for key, value in VALID_SEGMENT.items()
                if key != "gender"
            },
            "unknown emotion": {**VALID_SEGMENT, "emotion": "excited"},
            "pacing too slow": {**VALID_SEGMENT, "pacing": 0.24},
            "pacing too fast": {**VALID_SEGMENT, "pacing": 4.01},
            "unknown provider": {**VALID_SEGMENT, "voice_id": "other:voice"},
            "empty provider voice": {**VALID_SEGMENT, "voice_id": "google:"},
        }

        for name, payload in invalid_segments.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    ScriptSegment.model_validate(payload)


if __name__ == "__main__":
    unittest.main()

"""Validated script models shared by voice assignment and synthesis APIs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SegmentType = Literal["narration", "dialogue"]
Gender = Literal["male", "female", "neutral"]
Emotion = Literal[
    "neutral",
    "happy",
    "sad",
    "angry",
    "fearful",
    "surprised",
    "whispering",
    "shouting",
]
TTSProviderName = Literal["google", "azure", "openai", "elevenlabs"]

MAX_SEGMENT_TEXT_LENGTH = 5_000
MAX_CHARACTER_NAME_LENGTH = 100
MAX_VOICE_ID_LENGTH = 128


class ScriptSegment(BaseModel):
    """One fully validated narration or dialogue segment."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    type: SegmentType = Field(description="Whether the segment is narration or dialogue")
    text: str = Field(
        min_length=1,
        max_length=MAX_SEGMENT_TEXT_LENGTH,
        description="Text to synthesize",
    )
    character: str = Field(
        min_length=1,
        max_length=MAX_CHARACTER_NAME_LENGTH,
        description="Speaker name, or Narrator for narration",
    )
    gender: Gender = Field(description="Voice gender used during automatic assignment")
    emotion: Emotion = Field(
        default="neutral",
        description="Supported emotional delivery style",
    )
    pacing: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Speaking speed multiplier",
    )
    voice_id: str = Field(
        default="",
        max_length=MAX_VOICE_ID_LENGTH,
        description="Namespaced voice ID; an empty value requests automatic assignment",
    )
    provider: TTSProviderName | None = Field(
        default=None,
        description="Legacy provider hint for non-namespaced voice IDs",
    )

    @field_validator("voice_id")
    @classmethod
    def validate_voice_id(cls, voice_id: str) -> str:
        """Reject malformed namespaced IDs while retaining legacy raw IDs."""
        if not voice_id:
            return ""

        if any(ord(character) < 32 for character in voice_id):
            raise ValueError("voice_id cannot contain control characters")

        if ":" not in voice_id:
            return voice_id

        provider, raw_voice_id = voice_id.split(":", 1)
        supported_providers = {"google", "azure", "openai", "elevenlabs"}
        if provider not in supported_providers:
            raise ValueError(f"Unsupported TTS provider in voice_id: {provider}")
        if not raw_voice_id:
            raise ValueError("voice_id must include an identifier after the provider prefix")
        return voice_id

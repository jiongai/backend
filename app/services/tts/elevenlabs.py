"""ElevenLabs speech provider implementation."""

import asyncio
from typing import Any

import structlog

from app.core.settings import Settings, get_settings

from .base import TTSProvider


logger = structlog.get_logger(__name__)

try:
    from elevenlabs import VoiceSettings
    from elevenlabs.client import ElevenLabs
except ImportError:
    ElevenLabs = None
    VoiceSettings = None


class ElevenLabsTTSProvider(TTSProvider):
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.default_key = settings.elevenlabs_api_key
        self._enabled = bool(ElevenLabs)

    @property
    def name(self) -> str:
        return "ElevenLabs"

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def generate(
        self,
        text: str,
        output_file: str,
        voice: str,
        speed: float = 1.0,
        **kwargs: Any,
    ) -> None:
        if not self._enabled:
            raise RuntimeError("ElevenLabs library is not installed")

        api_key = kwargs.get("api_key") or self.default_key
        if not api_key:
            raise ValueError("ElevenLabs API key is required")
        settings_dict = kwargs.get("settings") or {}
        max_retries = kwargs.get("max_retries", 3)

        def synthesize_and_write():
            client = ElevenLabs(api_key=api_key)
            voice_settings = VoiceSettings(
                stability=settings_dict.get("stability", 0.5),
                similarity_boost=settings_dict.get("similarity_boost", 0.75),
                style=settings_dict.get("style", 0.0),
                use_speaker_boost=True,
                speed=speed,
            )
            audio_generator = client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id="eleven_turbo_v2_5",
                voice_settings=voice_settings,
                output_format="mp3_44100_128",
            )
            with open(output_file, "wb") as output:
                for chunk in audio_generator:
                    output.write(chunk)

        for attempt in range(max_retries):
            try:
                if attempt:
                    logger.warning(
                        "ElevenLabs retry attempt",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                    )
                await asyncio.to_thread(synthesize_and_write)
                return
            except Exception as exc:
                if attempt == max_retries - 1:
                    raise RuntimeError(
                        "ElevenLabs generation failed after "
                        f"{max_retries} attempts: {exc}"
                    ) from exc
                await asyncio.sleep(1)

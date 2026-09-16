"""OpenAI speech provider implementation."""

import asyncio
from typing import Any

from app.core.settings import Settings, get_settings

from .base import TTSProvider


try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


class OpenAITTSProvider(TTSProvider):
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.api_key = settings.openai_api_key
        self._enabled = bool(self.api_key and AsyncOpenAI)
        self._client = None

    @property
    def name(self) -> str:
        return "OpenAI"

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _get_client(self):
        if not self._client:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(
        self,
        text: str,
        output_file: str,
        voice: str,
        speed: float = 1.0,
        **kwargs: Any,
    ) -> None:
        if not self._enabled:
            raise RuntimeError(
                "OpenAI TTS is not configured or dependencies are missing"
            )

        model = "tts-1"
        voice_id = voice
        if "|" in voice:
            model, voice_id = voice.split("|", 1)
        response = await self._get_client().audio.speech.create(
            model=model,
            voice=voice_id,
            input=text,
            speed=speed,
            response_format="mp3",
        )
        await asyncio.to_thread(response.stream_to_file, output_file)

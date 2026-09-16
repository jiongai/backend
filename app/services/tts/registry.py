"""Construction of the provider registry used by the audio engine."""

from typing import Dict

from app.core.settings import Settings, get_settings

from .azure import AzureTTSProvider
from .base import TTSProvider
from .elevenlabs import ElevenLabsTTSProvider
from .google import GoogleTTSProvider
from .openai import OpenAITTSProvider


def build_tts_providers(
    settings: Settings | None = None,
) -> Dict[str, TTSProvider]:
    settings = settings or get_settings()
    return {
        "azure": AzureTTSProvider(settings),
        "google": GoogleTTSProvider(settings),
        "openai": OpenAITTSProvider(settings),
        "elevenlabs": ElevenLabsTTSProvider(settings),
    }

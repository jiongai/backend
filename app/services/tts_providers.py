"""Backward-compatible imports for the split TTS provider package.

New code should import from :mod:`app.services.tts`.
"""

from .tts import (
    AzureTTSProvider,
    ElevenLabsTTSProvider,
    GoogleTTSProvider,
    OpenAITTSProvider,
    TTSProvider,
    build_tts_providers,
)

__all__ = [
    "AzureTTSProvider",
    "ElevenLabsTTSProvider",
    "GoogleTTSProvider",
    "OpenAITTSProvider",
    "TTSProvider",
    "build_tts_providers",
]

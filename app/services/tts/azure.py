"""Azure Speech provider implementation."""

import asyncio
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from app.core.settings import Settings, get_settings

from .base import TTSProvider


try:
    import azure.cognitiveservices.speech as speechsdk
except (ImportError, OSError, Exception):
    speechsdk = None


class AzureTTSProvider(TTSProvider):
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.speech_key = settings.azure_speech_key
        self.service_region = settings.azure_speech_region
        self._enabled = bool(
            self.speech_key and self.service_region and speechsdk
        )

    @property
    def name(self) -> str:
        return "Azure"

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
            raise RuntimeError(
                "Azure TTS is not configured or dependencies are missing"
            )

        language_code = "-".join(voice.split("-")[:2]) if "-" in voice else "en-US"
        rate = f"{(speed - 1.0) * 100:+.0f}%"
        ssml = (
            '<speak version="1.0" '
            'xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang={quoteattr(language_code)}>'
            f'<voice name={quoteattr(voice)}>'
            f'<prosody rate={quoteattr(rate)}>{escape(text)}</prosody>'
            "</voice></speak>"
        )

        def synthesize():
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key,
                region=self.service_region,
            )
            speech_config.speech_synthesis_voice_name = voice
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3
            )
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=audio_config,
            )
            return synthesizer.speak_ssml_async(ssml).get()

        result = await asyncio.to_thread(synthesize)
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            raise RuntimeError(
                "Azure TTS canceled: "
                f"{details.reason}. Error details: {details.error_details}"
            )

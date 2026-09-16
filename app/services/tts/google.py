"""Google Cloud Text-to-Speech provider implementation."""

import asyncio
import json
import threading
from typing import Any

from app.core.settings import Settings, get_settings

from .base import TTSProvider


try:
    from google.cloud import texttospeech
    from google.oauth2 import service_account
except ImportError:
    texttospeech = None
    service_account = None


class GoogleTTSProvider(TTSProvider):
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.credentials_json = settings.google_credentials_json
        self.credentials_path = settings.google_credentials_path
        self._enabled = bool(
            (self.credentials_json or self.credentials_path) and texttospeech
        )
        self._client = None
        self._client_lock = threading.Lock()

    @property
    def name(self) -> str:
        return "Google"

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _get_client(self):
        if not self._client:
            with self._client_lock:
                if not self._client:
                    if self.credentials_json:
                        info = json.loads(self.credentials_json)
                        credentials = (
                            service_account.Credentials.from_service_account_info(
                                info
                            )
                        )
                        self._client = texttospeech.TextToSpeechClient(
                            credentials=credentials
                        )
                    elif self.credentials_path:
                        self._client = texttospeech.TextToSpeechClient()
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
                "Google TTS is not configured or dependencies are missing"
            )

        def synthesize_and_write():
            client = self._get_client()
            language_code = (
                "-".join(voice.split("-")[:2]) if "-" in voice else "en-US"
            )
            response = client.synthesize_speech(
                input=texttospeech.SynthesisInput(text=text),
                voice=texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=voice,
                ),
                audio_config=texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3,
                    speaking_rate=speed,
                ),
            )
            with open(output_file, "wb") as output:
                output.write(response.audio_content)

        try:
            await asyncio.to_thread(synthesize_and_write)
        except Exception:
            with self._client_lock:
                self._client = None
            raise

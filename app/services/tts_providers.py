
import os
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict

# Try imports, handle missing dependencies gracefully
try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None

try:
    from google.cloud import texttospeech
    from google.oauth2 import service_account
    import json
except ImportError:
    texttospeech = None

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

class TTSProvider(ABC):
    """Abstract base class for TTS providers."""
    
    @abstractmethod
    async def generate(self, text: str, output_file: str, voice: str) -> None:
        """Generate audio from text."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass


class AzureTTSProvider(TTSProvider):
    """Azure Cognitive Services Speech Provider."""
    
    def __init__(self):
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.service_region = os.getenv("AZURE_SPEECH_REGION")
        self._enabled = bool(self.speech_key and self.service_region and speechsdk)
        
    @property
    def name(self) -> str:
        return "Azure"
    
    @property
    def is_enabled(self) -> bool:
        return self._enabled
        
    async def generate(self, text: str, output_file: str, voice: str) -> None:
        if not self._enabled:
            raise Exception("Azure TTS is not configured or dependencies missing")
            
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key, 
            region=self.service_region
        )
        speech_config.speech_synthesis_voice_name = voice
        
        # Azure supports direct file output
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)
        
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        
        # Synthesize (blocking call, need to wrap in executor)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: synthesizer.speak_text_async(text).get()
        )
        
        if result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            raise Exception(f"Azure TTS canceled: {cancellation_details.reason}. Error details: {cancellation_details.error_details}")


class GoogleTTSProvider(TTSProvider):
    """Google Cloud Text-to-Speech Provider."""
    
    def __init__(self):
        self.credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._enabled = bool((self.credentials_json or self.credentials_path) and texttospeech)
        self._client = None
        
    @property
    def name(self) -> str:
        return "Google"
        
    @property
    def is_enabled(self) -> bool:
        return self._enabled
        
    def _get_client(self):
        if not self._client:
            if self.credentials_json:
                info = json.loads(self.credentials_json)
                credentials = service_account.Credentials.from_service_account_info(info)
                self._client = texttospeech.TextToSpeechClient(credentials=credentials)
            elif self.credentials_path:
                self._client = texttospeech.TextToSpeechClient()
        return self._client
        
    async def generate(self, text: str, output_file: str, voice: str) -> None:
        if not self._enabled:
            raise Exception("Google TTS is not configured or dependencies missing")
            
        client = self._get_client()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Parse voice params (expected format: "lang-code|voice-name" or just "voice-name")
        # Google needs language code (e.g. "en-US") separately
        lang_code = "-".join(voice.split("-")[:2]) if "-" in voice else "en-US"
        
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=lang_code,
            name=voice
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Async call wrapper
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.synthesize_speech(
                input=synthesis_input, 
                voice=voice_params, 
                audio_config=audio_config
            )
        )
        
        # Write to file
        with open(output_file, "wb") as out:
            out.write(response.audio_content)


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS Provider."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
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
        
    async def generate(self, text: str, output_file: str, voice: str) -> None:
        if not self._enabled:
            raise Exception("OpenAI TTS is not configured or dependencies missing")
            
        client = self._get_client()
        
        # voice can include model, e.g. "tts-1|alloy"
        model = "tts-1"
        voice_id = voice
        if "|" in voice:
            model, voice_id = voice.split("|")
            
        response = await client.audio.speech.create(
            model=model,
            voice=voice_id,
            input=text
        )
        
        response.stream_to_file(output_file)

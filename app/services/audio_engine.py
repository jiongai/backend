
"""
Audio Engine Service
Generates audio using Hybrid Routing Strategy (Azure -> Google -> OpenAI -> ElevenLabs).
"""

import os
import asyncio
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from .tts_providers import (
    AzureTTSProvider, 
    GoogleTTSProvider, 
    OpenAITTSProvider,
    TTSProvider
)
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

USAGE_FILE = "tts_usage.json"
AZURE_MONTHLY_LIMIT = 500000  # 500k characters

# Voice Mappings (Hybrid Strategy)
VOICE_MAP = {
    # Level 1: Azure (Top Quality Free/Standard)
    "azure": {
        "en": "en-US-BrianNeural",
        "zh": "zh-CN-YunxiNeural"
    },
    # Level 2: Google (Standard/Wavenet Fallback)
    "google": {
        # Defaults
        "en": {"male": "en-US-Neural2-J", "female": "en-US-Neural2-F"},
        "zh": {"male": "cmn-CN-Wavenet-C", "female": "cmn-CN-Wavenet-A"},
        
        # Extended Voice Pool
        "pool": {
            "zh": {
                "female": [
                    "cmn-CN-Wavenet-A", "cmn-CN-Wavenet-D", # Wavenet
                    "cmn-CN-Neural2-F", "cmn-TW-Wavenet-A"  # Neural2 / TW
                ],
                "male": [
                    "cmn-CN-Wavenet-C", "cmn-CN-Wavenet-B",
                    "cmn-CN-Neural2-C"
                ]
            },
            "en": {
                "female": [
                    "en-US-Neural2-C", "en-US-Neural2-E", "en-US-Neural2-F", "en-US-Neural2-G", "en-US-Neural2-H",
                    "en-US-Wavenet-C", "en-US-Wavenet-E", "en-US-Wavenet-F", "en-GB-Neural2-A", "en-GB-Neural2-C"
                ],
                "male": [
                    "en-US-Neural2-A", "en-US-Neural2-D", "en-US-Neural2-I", "en-US-Neural2-J",
                    "en-US-Wavenet-A", "en-US-Wavenet-B", "en-US-Wavenet-D", "en-GB-Neural2-B", "en-GB-Neural2-D"
                ]
            }
        }
    },
    # Level 3: OpenAI (VIP Narration)
    "openai": {
        "male": "onyx",
        "female": "alloy" # or shimmer
    },

    # Level 4: ElevenLabs (High Emotion Dialogue)
    "elevenlabs": {
        # Defaults
        "male": "pNInz6obpgDQGcFmaJgB",   # Adam (Default Male)
        "female": "21m00Tcm4TlvDq8ikWAM", # Rachel (Default Female)
        
        # Extended Voice Pool for Deterministic Assignment
        "pool": {
            "male": [
                "pNInz6obpgDQGcFmaJgB", # Adam
                "ErXwobaYiN019PkySvjV", # Antoni
                "VR6AewLTigWG4xSOukaG", # Arnold
                "N2lVS1w4EtoT3dr4eOWO", # Callum
                "IKne3meq5aSn9XLyUdCD", # Charlie
                "2EiwWnXFnvU5JabPnv8n", # Clyde
                "CYw3kZ02Hs0563khs1Fj", # Dave
                "D38z5RcWu1voky8WS1ja", # Fin
                "JBFqnCBsd6RMkjVDRZzb", # George
                "TxGEqnHWrfWFTfGW9XjX", # Josh
                "ODq5zmih8GrVes37Dizd", # Patrick
                "yoZ06aMxZJJ28mfd3POQ", # Sam
                "GBv7mTt0atIp3Br8iCZE", # Thomas
            ],
            "female": [
                "21m00Tcm4TlvDq8ikWAM", # Rachel
                "EXAVITQu4vr4xnSDxMaL", # Bella
                "XB0fDUnXU5powFXDhCwa", # Charlotte
                "AZnzlk1XvdvUeBnXmlld", # Domi
                "ThT5KcBeYPX3keUQqHPh", # Dorothy
                "MF3mGyEYCl7XYWbV9V6O", # Elli
                "LcfcDJNUP1GQjkzn1xUU", # Emily
                "jsCqWAovK2LkecY7zXl4", # Freya
                "jBpfuIE2acCO8z3wKNLl", # Gigi
                "z9fAnlkpzviPz146aGWa", # Glinda
                "oWAxZDx7w5VEj9dCyTzz", # Grace
                "cgSgspJ2msm6clMCkdW9", # Jessica
                "pFZP5JQG7iQjIQuC4Bku", # Lily
                "XrExE9yKIg1WjnnlVkGX", # Matilda
                "piTKgcLEGmPE4e6mEKli", # Nicole
            ]
        }
    }
}

# Emotion -> Voice Settings Mapping
# Stability: Low = more emotion/varaiance. High = stable/monotone.
# Similarity: High = clearer identity. Low = more fuzzy/creative.
# Style: High = exaggerated.
EMOTION_SETTINGS = {
    "neutral":    {"stability": 0.60, "similarity_boost": 0.75, "style": 0.0},
    "happy":      {"stability": 0.45, "similarity_boost": 0.80, "style": 0.3},
    "sad":        {"stability": 0.40, "similarity_boost": 0.70, "style": 0.2},
    "angry":      {"stability": 0.30, "similarity_boost": 0.80, "style": 0.6},
    "fearful":    {"stability": 0.30, "similarity_boost": 0.65, "style": 0.5},
    "surprised":  {"stability": 0.35, "similarity_boost": 0.75, "style": 0.4},
    "whispering": {"stability": 0.50, "similarity_boost": 0.50, "style": 0.0}, # Low similarity allows breathiness
    "shouting":   {"stability": 0.25, "similarity_boost": 0.80, "style": 0.7},
}

class TTSManager:
    def __init__(self):
        self.providers = {
            "azure": AzureTTSProvider(),
            "google": GoogleTTSProvider(),
            "openai": OpenAITTSProvider()
        }
    
    def _get_consistent_voice(self, character: str, gender: str, provider: str, lang: str = "en") -> str:
        """
        Get a consistent voice ID/name for a character based on their name hash.
        """
        if provider == "openai":
                return VOICE_MAP["openai"]["male"] if gender == "male" else VOICE_MAP["openai"]["female"]
        
        # Support both Google and ElevenLabs pools
        target_pool = None
        
        if provider == "elevenlabs":
            target_pool = VOICE_MAP["elevenlabs"]["pool"].get(gender, VOICE_MAP["elevenlabs"]["pool"]["male"])
        elif provider == "google":
            # Default to English if lang not in map (e.g. unknown)
            if lang not in VOICE_MAP["google"]["pool"]:
                lang = "en"
            
            # Google pool structure: pool -> lang -> gender
            lang_pool = VOICE_MAP["google"]["pool"].get(lang)
            if lang_pool:
                target_pool = lang_pool.get(gender, lang_pool.get("male"))

        if not target_pool:
            # Fallback for Azure or if pool not found
            # Azure logic is simple (one voice per lang)
            if provider == "azure":
                 # Azure mapping is direct in VOICE_MAP['azure'][lang]
                 # Not pool-based
                 return VOICE_MAP["azure"].get(lang, "en-US-BrianNeural")
            
            # Generic fallback
            return None

        # Deterministic Logic (Hash)
        import hashlib
        hash_obj = hashlib.md5(character.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        voice_index = hash_int % len(target_pool)
        selected_voice = target_pool[voice_index]
        print(f"   [Voice Assignment] '{character}' ({gender}) -> {provider.upper()}: {selected_voice} (Index: {voice_index})")
        return selected_voice
        
    def _get_monthly_usage(self) -> int:
        """Read current month's Azure usage from file."""
        if not os.path.exists(USAGE_FILE):
            return 0
        
        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            
            current_month = datetime.now().strftime("%Y-%m")
            if data.get("month") != current_month:
                return 0
            return data.get("azure_usage", 0)
        except Exception:
            return 0

    def _increment_usage(self, chars: int):
        """Update Azure usage stats."""
        try:
            current_usage = self._get_monthly_usage()
            new_usage = current_usage + chars
            
            data = {
                "month": datetime.now().strftime("%Y-%m"),
                "azure_usage": new_usage
            }
            
            with open(USAGE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Warning: Failed to update usage stats: {e}")

    def select_provider(self, segment_type: str, text: str, user_tier: str, emotion: str) -> str:
        """
        Determine which provider to use based on Hybrid Routing rules.
        
        Strategies:
        1. Dialogue:
           - VIP: ElevenLabs (High Emotion)
           - Free: Google (Standard)
        2. Narration:
           - VIP: OpenAI (High Quality)
           - Free: Azure (if quota) -> Google
        """
        chars = len(text)
        
        # Priority 1: Dialogue
        if segment_type == "dialogue":
            if user_tier == "vip":
                return "elevenlabs"
            else:
                # Free users get Google for dialogue
                return "google"

        # Priority 2: Narration
        if segment_type == "narration":
            # Level 3: VIP User -> OpenAI
            if user_tier == "vip":
                if self.providers["openai"].is_enabled:
                    return "openai"
            
            # Level 1: Azure (if quota allows)
            usage = self._get_monthly_usage()
            if usage + chars < AZURE_MONTHLY_LIMIT and self.providers["azure"].is_enabled:
                return "azure"
            
            # Level 2: Fallback to Google
            if self.providers["google"].is_enabled:
                return "google"
                
            # Fallback of Fallback
            if self.providers["openai"].is_enabled:
                return "openai"
                
        # Default fallback
        return "google"

    async def generate(self, segment: Dict, output_file: str, user_tier: str = "free", elevenlabs_key: str = None) -> None:
        text = segment["text"]
        character = segment.get("character", "Narrator")
        seg_type = segment["type"]
        emotion = segment.get("emotion", "neutral")
        gender = segment.get("gender", "male")
        
        # Detect language (needed for voice selection)
        import re
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        lang_key = "zh" if is_chinese else "en"
        
        provider_name = self.select_provider(seg_type, text, user_tier, emotion)
        
        # Calculate consistent voice
        specific_voice_id = self._get_consistent_voice(character, gender, provider_name, lang=lang_key)
        
        # Determine emotion settings (Only for ElevenLabs currently)
        settings = EMOTION_SETTINGS.get(emotion.lower(), EMOTION_SETTINGS["neutral"])
        
        print(f"   [TTS Manager] Routing '{text[:15]}...' -> {provider_name.upper()} (User: {user_tier}, Voice: {specific_voice_id or 'Default'})")
        
        # Execute based on provider
        if provider_name == "azure":
            # specific_voice_id from _get_consistent_voice might be None or correct
            # For Azure, let's trust _get_consistent_voice returned the map value
            if not specific_voice_id:
                 specific_voice_id = VOICE_MAP["azure"][lang_key]
            
            await self.providers["azure"].generate(text, output_file, specific_voice_id)
            self._increment_usage(len(text))
            
        elif provider_name == "google":
            # Ensure specific_voice_id is set (from pool)
            if not specific_voice_id:
                 # Fallback if hash failed
                 voice_dict = VOICE_MAP["google"][lang_key]
                 specific_voice_id = voice_dict.get(gender, list(voice_dict.values())[0])
            
            await self.providers["google"].generate(text, output_file, specific_voice_id)
            
        elif provider_name == "openai":
            # specific_voice_id should be 'onyx' or 'alloy'
            if not specific_voice_id:
                 specific_voice_id = VOICE_MAP["openai"]["male"] if gender == "male" else VOICE_MAP["openai"]["female"]
                 
            await self.providers["openai"].generate(text, output_file, specific_voice_id)
            
        elif provider_name == "elevenlabs":
            if not elevenlabs_key:
                raise ValueError("ElevenLabs API key required for ElevenLabs generation")
            await _generate_with_elevenlabs(
                text, 
                gender, 
                output_file, 
                elevenlabs_key, 
                voice_id_override=specific_voice_id,
                settings_dict=settings
            )
            
        else:
            raise Exception(f"Unknown or unsupported provider: {provider_name}")


# Singleton Manager
tts_manager = TTSManager()

# ============================================================================
# LEGACY / COMPATIBILITY WRAPPERS
# ============================================================================

async def generate_segment_audio(
    segment: Dict,
    output_dir: str,
    elevenlabs_api_key: str = None,
    narration_voice: str = None, # Deprecated but kept for signature compatibility
    user_tier: str = "free" # New optional param
) -> str:
    """
    Wrapper for TTSManager to maintain compatibility with main.py
    """
    segment_type = segment["type"]
    character = segment["character"]
    text = segment["text"]
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    import hashlib
    import time
    timestamp = int(time.time() * 1000)
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    filename = f"{segment_type}_{character}_{timestamp}_{text_hash}.mp3"
    output_file = output_path / filename
    
    # Use Manager
    await tts_manager.generate(
        segment=segment,
        output_file=str(output_file),
        user_tier=user_tier,
        elevenlabs_key=elevenlabs_api_key
    )
    
    return str(output_file)


async def _generate_with_elevenlabs(
    text: str,
    gender: str,
    output_file: str,
    api_key: str,
    max_retries: int = 3,
    voice_id_override: str = None,
    settings_dict: dict = None
) -> None:
    """
    Generate audio using ElevenLabs (paid) with retry mechanism.
    (Preserved from previous version)
    """
    client = ElevenLabs(api_key=api_key)
    
    if voice_id_override:
        voice_name = voice_id_override
    else:
        # Fallback to defaults if no override
        voice_name = VOICE_MAP["elevenlabs"].get(gender.lower(), VOICE_MAP["elevenlabs"]["male"])
    
    loop = asyncio.get_event_loop()
    
    for attempt in range(max_retries):
        try:
            print(f"   [ElevenLabs] Starting attempt {attempt+1}/{max_retries}...")
            
            def _call_elevenlabs():
                # Prepare settings if provided
                v_settings = None
                if settings_dict:
                    v_settings = VoiceSettings(
                        stability=settings_dict.get("stability", 0.5),
                        similarity_boost=settings_dict.get("similarity_boost", 0.75),
                        style=settings_dict.get("style", 0.0),
                        use_speaker_boost=True
                    )

                return client.text_to_speech.convert(
                    voice_id=voice_name,
                    text=text,
                    model_id="eleven_turbo_v2_5",
                    voice_settings=v_settings
                )

            # 60s timeout
            audio_generator = await asyncio.wait_for(
                 loop.run_in_executor(None, _call_elevenlabs),
                 timeout=60.0
            )
            
            await loop.run_in_executor(None, lambda: _save_audio_bytes(audio_generator, output_file))
            return
            
        except Exception as e:
            print(f"   [ElevenLabs] ⚠️ Failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            raise

def _save_audio_bytes(audio_generator, output_file: str) -> None:
    with open(output_file, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)


async def generate_script_audio(
    script: list,
    output_dir: str,
    elevenlabs_api_key: str = None,
    user_tier: str = "free"
) -> list:
    """
    Generate audio for all segments in a script.
    
    Args:
        script: List of script segments
        output_dir: Directory to save audio files
        elevenlabs_api_key: ElevenLabs API key (required if script contains dialogue)
        user_tier: User tier ("free" or "vip")
        
    Returns:
        list: List of paths to generated audio files (in same order as script)
    """
    tasks = []
    for segment in script:
        task = generate_segment_audio(
            segment=segment, 
            output_dir=output_dir, 
            elevenlabs_api_key=elevenlabs_api_key,
            user_tier=user_tier
        )
        tasks.append(task)
    
    # Generate all audio files concurrently
    audio_paths = await asyncio.gather(*tasks)
    
    return audio_paths

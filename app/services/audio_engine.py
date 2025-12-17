
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
    ElevenLabsTTSProvider,
    TTSProvider
)

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
                    "cmn-TW-Wavenet-A"  # TW Wavenet
                ],
                "male": [
                    "cmn-CN-Wavenet-C", "cmn-CN-Wavenet-B",
                    "cmn-TW-Wavenet-B", "cmn-TW-Wavenet-C"
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

# Voice Samples (URLs)
VOICE_SAMPLES = {
    "openai": {
        "alloy": "https://cdn.openai.com/API/docs/audio/alloy.wav",
        "echo": "https://cdn.openai.com/API/docs/audio/echo.wav",
        "fable": "https://cdn.openai.com/API/docs/audio/fable.wav",
        "onyx": "https://cdn.openai.com/API/docs/audio/onyx.wav",
        "nova": "https://cdn.openai.com/API/docs/audio/nova.wav",
        "shimmer": "https://cdn.openai.com/API/docs/audio/shimmer.wav"
    }
}

# Voice Labels (ID -> Name Map)
VOICE_LABELS = {
    # Azure
    "en-US-BrianNeural": "Brian (Narrator)",
    "zh-CN-YunxiNeural": "Yunxi (Narrator)",
    
    # Google (English)
    "en-US-Neural2-A": "Steven (Classic)",
    "en-US-Neural2-C": "Sarah (Bright)",
    "en-US-Neural2-D": "Robert (Deep)",
    "en-US-Neural2-E": "Emily (Soft)",
    "en-US-Neural2-F": "Jennifer (Warm)",
    "en-US-Neural2-G": "Female G (Neural2)", # Kept generic if no mapping decided
    "en-US-Neural2-H": "Helen (Mature)",
    "en-US-Neural2-I": "David (Strong)",
    "en-US-Neural2-J": "Michael (Energetic)",
    "en-US-Wavenet-A": "James (Standard)",
    "en-US-Wavenet-B": "John (Formal)",
    "en-US-Wavenet-C": "Mary (Sweet)",
    "en-US-Wavenet-D": "William (Deep)",
    "en-US-Wavenet-E": "Patricia (Soft)",
    "en-US-Wavenet-F": "Linda (Warm)",
    "en-GB-Neural2-A": "Female A (UK Neural2)",
    "en-GB-Neural2-B": "Male B (UK Neural2)",
    "en-GB-Neural2-C": "Female C (UK Neural2)",
    "en-GB-Neural2-D": "Male D (UK Neural2)",

    # Google (Chinese)
    "cmn-CN-Wavenet-A": "小燕 (甜美)", # Xiaoyan
    "cmn-CN-Wavenet-B": "云扬 (播音)", # Yunyang
    "cmn-CN-Wavenet-C": "云希 (故事)", # Yunxi (Story)
    "cmn-CN-Wavenet-D": "晓晓 (亲切)", # Xiaoxiao
    "cmn-TW-Wavenet-A": "Female A (TW Wavenet)",
    "cmn-TW-Wavenet-B": "Male B (TW Wavenet)",
    "cmn-TW-Wavenet-C": "Male C (TW Wavenet)",


    # OpenAI
    "onyx": "Onyx (Deep Male)",
    "alloy": "Alloy (Clear Female)",
    "echo": "Echo (Narrator)",
    "fable": "Fable (Expressive)",
    "nova": "Nova (Energetic)",
    "shimmer": "Shimmer (Soft)",

    # ElevenLabs
    "pNInz6obpgDQGcFmaJgB": "Adam (Deep)",
    "21m00Tcm4TlvDq8ikWAM": "Rachel (Warm)",
    "ErXwobaYiN019PkySvjV": "Antoni (Young)",
    "VR6AewLTigWG4xSOukaG": "Arnold (Strong)",
    "N2lVS1w4EtoT3dr4eOWO": "Callum (Calm)",
    "IKne3meq5aSn9XLyUdCD": "Charlie (Friendly)",
    "2EiwWnXFnvU5JabPnv8n": "Clyde (Warm)",
    "CYw3kZ02Hs0563khs1Fj": "Dave (Young UK)",
    "D38z5RcWu1voky8WS1ja": "Fin (Irish)",
    "JBFqnCBsd6RMkjVDRZzb": "George (Formal UK)",
    "TxGEqnHWrfWFTfGW9XjX": "Josh (News)",
    "ODq5zmih8GrVes37Dizd": "Patrick (Authoritative)",
    "yoZ06aMxZJJ28mfd3POQ": "Sam (Lively)",
    "GBv7mTt0atIp3Br8iCZE": "Thomas (Gentle)",
    "EXAVITQu4vr4xnSDxMaL": "Bella (Soft)",
    "XB0fDUnXU5powFXDhCwa": "Charlotte (Elegant)",
    "AZnzlk1XvdvUeBnXmlld": "Domi (Energetic)",
    "ThT5KcBeYPX3keUQqHPh": "Dorothy (Wise)",
    "MF3mGyEYCl7XYWbV9V6O": "Elli (Lively)",
    "LcfcDJNUP1GQjkzn1xUU": "Emily (Calm)",
    "jsCqWAovK2LkecY7zXl4": "Freya (Young US)",
    "jBpfuIE2acCO8z3wKNLl": "Gigi (Enthusiastic)",
    "z9fAnlkpzviPz146aGWa": "Glinda (Mysterious)",
    "oWAxZDx7w5VEj9dCyTzz": "Grace (Southern)",
    "cgSgspJ2msm6clMCkdW9": "Jessica (Professional)",
    "pFZP5JQG7iQjIQuC4Bku": "Lily (Young UK)",
    "XrExE9yKIg1WjnnlVkGX": "Matilda (Narrative)",
    "piTKgcLEGmPE4e6mEKli": "Nicole (Energetic)"
}

def get_enriched_voice_map() -> Dict:
    """
    Return a copy of VOICE_MAP where every voice ID is 
    replaced with {"id": "...", "name": "...", "provider": "..."}.
    """
    import copy
    
    def enrich_node(node, provider_name):
        if isinstance(node, str):
            # It's a voice ID (leaf)
            return {
                "id": f"{provider_name}:{node}", # Keep namespacing!
                "name": VOICE_LABELS.get(node, node) # Fallback to ID if no name found
                # "provider": provider_name # Removed as per request
            }
        elif isinstance(node, dict):
            return {k: enrich_node(v, provider_name) for k, v in node.items()}
        elif isinstance(node, list):
            return [enrich_node(item, provider_name) for item in node]
        return node

    # Deep copy to avoid mutating the original CONFIGURATION
    raw_map = copy.deepcopy(VOICE_MAP)
    
    enriched_map = {}
    for provider, data in raw_map.items():
        enriched_map[provider] = enrich_node(data, provider)
        
    return enriched_map

def get_public_voice_groups() -> Dict:
    """
    Get the structured public voice groups (Basic/Advance).
    Deduplicates voices that appear in both 'defaults' and 'pool'.
    """
    full_map = get_enriched_voice_map()
    
    # Deduplicate Google Listing
    if "google" in full_map and "pool" in full_map["google"]:
        g_defaults = full_map["google"]
        g_pool = full_map["google"]["pool"]
        
        for lang in g_pool:
            if lang in g_defaults: # e.g. "en", "zh"
                # Check Male
                def_male = g_defaults[lang].get("male")
                if def_male and isinstance(def_male, dict) and "id" in def_male:
                    target_id = def_male["id"]
                    if "male" in g_pool[lang]:
                        g_pool[lang]["male"] = [v for v in g_pool[lang]["male"] if v["id"] != target_id]
                        
                # Check Female
                def_female = g_defaults[lang].get("female")
                if def_female and isinstance(def_female, dict) and "id" in def_female:
                    target_id = def_female["id"]
                    if "female" in g_pool[lang]:
                        g_pool[lang]["female"] = [v for v in g_pool[lang]["female"] if v["id"] != target_id]

    # Deduplicate ElevenLabs Listing
    if "elevenlabs" in full_map and "pool" in full_map["elevenlabs"]:
        el_defaults = full_map["elevenlabs"]
        el_pool = full_map["elevenlabs"]["pool"]
        
        for gender in ["male", "female"]:
            def_voice = el_defaults.get(gender)
            if def_voice and isinstance(def_voice, dict) and "id" in def_voice:
                target_id = def_voice["id"]
                if gender in el_pool:
                     el_pool[gender] = [v for v in el_pool[gender] if v["id"] != target_id]

    return {
        "Basic": full_map.get("google"),
        "Advance": full_map.get("elevenlabs")
    }


def generate_cast_metadata(script: list, user_tier: str = "free") -> list:
    """
    Generate metadata about the cast and voices used in the script.
    Includes DIALOGUE characters AND Narrator.
    """
    cast_map = {} # character -> {voice_info}
    import re
    
    # Pre-check for Narration
    has_narration = any(s["type"] == "narration" for s in script)
    narration_voice_info = None
    
    if has_narration:
        # Determine Narrator Voice
        # 1. Find the first narration segment to detect language
        first_narration = next((s for s in script if s["type"] == "narration"), None)
        text_sample = first_narration["text"] if first_narration else ""
        
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text_sample))
        lang_key = "zh" if is_chinese else "en"
        
        # Check for Manual Voice Override (Narrator)
        manual_voice = first_narration.get("voice_id") # Changed from 'voice'
        is_override = False
        
        if manual_voice and manual_voice != "pending" and isinstance(manual_voice, str) and manual_voice.strip():
             is_override = True
             voice_id = manual_voice.strip()


             
             # Resolve Provider from ID (Simplified heuristic)
             if voice_id in list(VOICE_MAP["openai"].values()):
                 narration_provider = "openai"
             elif voice_id in list(VOICE_MAP["azure"].values()) or voice_id in ["en-US-BrianNeural", "zh-CN-YunxiNeural"]:
                 narration_provider = "azure"
             elif "Neural2" in voice_id or "Wavenet" in voice_id:
                 narration_provider = "google"
             elif len(voice_id) > 15:
                 narration_provider = "elevenlabs"
             else:
                 narration_provider = "unknown"
                 
        else:
            # Default Logic
            # 2. Determine provider based on Tier (Narrator Logic) with Availability Check
            
            voice_id = None
            
            if user_tier == "vip":
                # VIP Logic: Try OpenAI first
                 narration_provider = "openai"
                 voice_id = VOICE_MAP["openai"]["male"] # Onyx
            else:
                # Free Logic: Try Azure first, fallback to Google
                if tts_manager.providers["azure"].is_enabled:
                    narration_provider = "azure"
                    voice_id = VOICE_MAP["azure"].get(lang_key, "en-US-BrianNeural")
                else:
                    # Fallback to Google
                    narration_provider = "google"
                    if lang_key == "zh":
                        # cmn-CN-Wavenet-C (Yunxi Story)
                        voice_id = VOICE_MAP["google"]["zh"]["male"] 
                    else:
                        # Michael (Energetic)
                         voice_id = "en-US-Neural2-J"

                         
        # Manual Override Check for Narrator could be here if supported, but simpler for now.
        
        cast_map["Narrator"] = {
            "character": "Narrator",
            "gender": "neutral", # Narrator is abstract
            "voice_provider": narration_provider,
            "voice_id": voice_id,

            "voice_name": VOICE_LABELS.get(voice_id, voice_id)
        }
    
    for segment in script:
        if segment["type"] != "dialogue":
            continue
            
        character = segment.get("character")
        if not character or character in cast_map:
            continue
            
        # Determine gender
        gender = segment.get("gender", "male")
        
        # Check for Manual Voice Override
        manual_voice = segment.get("voice_id") # Changed from 'voice'
        is_override = False
        
        if manual_voice and manual_voice != "pending" and isinstance(manual_voice, str) and manual_voice.strip():
             is_override = True
             voice_id = manual_voice.strip()


             
             # Resolve Provider from ID (Simplified heuristic)
             if voice_id in list(VOICE_MAP["openai"].values()):
                 provider = "openai"
             elif voice_id in list(VOICE_MAP["azure"].values()) or voice_id in ["en-US-BrianNeural", "zh-CN-YunxiNeural"]:
                 provider = "azure"
             elif "Neural2" in voice_id or "Wavenet" in voice_id:
                 provider = "google"
             elif len(voice_id) > 15:
                 provider = "elevenlabs"
             else:
                 provider = "unknown"
                 
        else:
            # Default Logic
            # Determine provider (assuming dialogue logic from select_provider)
            # VIP -> ElevenLabs, Free -> Google
            provider = "elevenlabs" if user_tier == "vip" else "google"
            
            # Detect language (simplified per segment)
            is_chinese = bool(re.search(r'[\u4e00-\u9fff]', segment["text"]))
            lang_key = "zh" if is_chinese else "en"
            
            # Get voice ID using the singleton manager's logic
            voice_id = tts_manager._get_consistent_voice(character, gender, provider, lang=lang_key)
        
        # Get voice Name

        
        # Get voice Name
        voice_name = VOICE_LABELS.get(voice_id, voice_id)
        
        cast_map[character] = {
            "character": character,
            "gender": gender,
            "voice_provider": provider,
            "voice_id": voice_id,
            "voice_name": voice_name
        }
        
    return list(cast_map.values())

        
    return list(cast_map.values())


class TTSManager:

    def __init__(self):
        self.providers = {
            "azure": AzureTTSProvider(),
            "google": GoogleTTSProvider(),
            "openai": OpenAITTSProvider(),
            "elevenlabs": ElevenLabsTTSProvider()
        }
    
    def _get_consistent_voice(self, character: str, gender: str, provider: str, lang: str = "en") -> str:
        """
        Get a consistent voice ID/name for a character based on their name hash.
        """
        if provider == "openai":
            return f"openai:{VOICE_MAP['openai']['male']}" if gender == "male" else f"openai:{VOICE_MAP['openai']['female']}"
        
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
                 voice_id = VOICE_MAP["azure"].get(lang, "en-US-BrianNeural")
                 return f"azure:{voice_id}"
            
            # Generic fallback
            return None

        # Deterministic Logic (Hash)
        import hashlib
        hash_obj = hashlib.md5(character.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        
        voice_index = hash_int % len(target_pool)
        selected_voice = target_pool[voice_index]
        print(f"   [Voice Assignment] '{character}' ({gender}) -> {provider.upper()}: {selected_voice} (Index: {voice_index})")
        return f"{provider}:{selected_voice}"
        
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

    def assign_voices_to_script(self, script: list, user_tier: str = "free") -> list:
        """
        Enrich the script by pre-calculating and assigning voices and providers.
        This allows the frontend to see and edit the voice assignments.
        """
        for segment in script:
            text = segment["text"]
            character = segment.get("character", "Narrator")
            seg_type = segment["type"]
            emotion = segment.get("emotion", "neutral")
            gender = segment.get("gender", "male")
            
            # Detect language (needed for voice selection)
            import re
            is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
            lang_key = "zh" if is_chinese else "en"
            
            # 1. Determine Provider
            provider_name = self.select_provider(seg_type, text, user_tier, emotion)
            
            # 2. Determine Voice ID
            specific_voice_id = self._get_consistent_voice(character, gender, provider_name, lang=lang_key)
            
            # Fallback for Google/Azure if specific_voice_id is None
            if not specific_voice_id:
                if provider_name == "google":
                    voice_dict = VOICE_MAP["google"][lang_key]
                    raw_id = voice_dict.get(gender, list(voice_dict.values())[0])
                    specific_voice_id = f"google:{raw_id}"
                elif provider_name == "azure":
                    raw_id = VOICE_MAP["azure"][lang_key]
                    specific_voice_id = f"azure:{raw_id}"
                elif provider_name == "openai":
                    specific_voice_id = VOICE_MAP["openai"]["male"] if gender == "male" else VOICE_MAP["openai"]["female"]

            # 3. Write to Segment
            # segment["provider"] = provider_name # Replaced by namespaced ID
            segment["voice_id"] = specific_voice_id
            
        return script

    async def generate(self, segment: Dict, output_file: str, user_tier: str = "free", elevenlabs_key: str = None) -> None:
        text = segment["text"]
        character = segment.get("character", "Narrator")
        emotion = segment.get("emotion", "neutral")
        gender = segment.get("gender", "male")
        pacing = float(segment.get("pacing", 1.0))
        
        # 1. Try to get pre-assigned provider/voice (WYSIWYG)
        provider_name = segment.get("provider")
        specific_voice_id = segment.get("voice_id")
        
        # New: Parse namespaced ID (e.g. google:en-US-Neural2-A)
        # This takes precedence over separate fields
        if specific_voice_id and ":" in specific_voice_id and not provider_name:
            p_candidate, v_candidate = specific_voice_id.split(":", 1)
            # Basic validation to ensure it looks like a provider
            if p_candidate in ["google", "azure", "openai", "elevenlabs"]:
                provider_name = p_candidate
                specific_voice_id = v_candidate
        
        # 2. If missing or empty, calculate them (Legacy Path / Fallback)
        # Empty string means the frontend passed the script back without assigning a specific voice,
        # so we must calculate a deterministic voice on the fly.
        # 2. If missing or empty, calculate them (Legacy Path / Fallback)
        # Empty string means the frontend passed the script back without assigning a specific voice,
        # so we must calculate a deterministic voice on the fly.
        if not provider_name or not specific_voice_id:
             # Case 2a: Have voice_id but no provider (e.g. Manual Override / Review)
             if specific_voice_id and not provider_name:
                 # Infer provider from voice ID pattern
                 if "Neural2" in specific_voice_id or "Wavenet" in specific_voice_id:
                     provider_name = "google"
                 elif "Neural" in specific_voice_id: # Azure usually ends in Neural
                     provider_name = "azure"
                 elif specific_voice_id in ["onyx", "alloy", "shimmer", "echo", "fable", "nova"]:
                     provider_name = "openai"
                 elif len(specific_voice_id) > 15: # ElevenLabs IDs are ~20 chars
                     provider_name = "elevenlabs"
                 else:
                     # Fallback to default calculation if unknown
                     pass

             # Case 2b: Still missing provider or voice_id -> Calculate from scratch (Auto-Assignment)
             if not provider_name or not specific_voice_id:
                 import re
                 is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
                 lang_key = "zh" if is_chinese else "en"
                 
                 seg_type = segment.get("type", "narration")
                 provider_name = self.select_provider(seg_type, text, user_tier, emotion)
                 specific_voice_id = self._get_consistent_voice(character, gender, provider_name, lang=lang_key)
        
        # Determine emotion settings
        settings = EMOTION_SETTINGS.get(emotion.lower(), EMOTION_SETTINGS["neutral"])
        
        print(f"   [TTS Manager] Routing '{text[:15]}...' -> {provider_name.upper()} (User: {user_tier}, Voice: {specific_voice_id or 'Default'}, Settings: {settings}, Speed: {pacing})")
        
        # Execute based on provider
        if provider_name == "azure":
            # specific_voice_id from _get_consistent_voice might be None or correct
            # For Azure, let's trust _get_consistent_voice returned the map value
            if not specific_voice_id:
                 specific_voice_id = VOICE_MAP["azure"][lang_key]
            
            await self.providers["azure"].generate(text, output_file, specific_voice_id, speed=pacing)
            self._increment_usage(len(text))
            
        elif provider_name == "google":
            # Ensure specific_voice_id is set (from pool)
            if not specific_voice_id:
                 # Fallback if hash failed
                 voice_dict = VOICE_MAP["google"][lang_key]
                 specific_voice_id = voice_dict.get(gender, list(voice_dict.values())[0])
            
            await self.providers["google"].generate(text, output_file, specific_voice_id, speed=pacing)
            
        elif provider_name == "openai":
            # specific_voice_id should be 'onyx' or 'alloy'
            if not specific_voice_id:
                 specific_voice_id = VOICE_MAP["openai"]["male"] if gender == "male" else VOICE_MAP["openai"]["female"]
                 
            await self.providers["openai"].generate(text, output_file, specific_voice_id, speed=pacing)
            
        elif provider_name == "elevenlabs":
            await self.providers["elevenlabs"].generate(
                text=text,
                output_file=output_file,
                voice=specific_voice_id,
                api_key=elevenlabs_key,
                settings=settings
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

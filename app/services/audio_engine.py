
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
import structlog

logger = structlog.get_logger(__name__)

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

# Load Configuration
def load_voice_config():
    config_path = Path(__file__).parent.parent / "config" / "voices.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load voice config", error=str(e))
        # Return empty defaults to avoid crash, but system will be degraded
        return {
            "VOICE_MAP": {},
            "EMOTION_SETTINGS": {},
            "VOICE_SAMPLES": {},
            "VOICE_LABELS": {},
            "AZURE_MONTHLY_LIMIT": 500000
        }

_CONFIG = load_voice_config()

VOICE_MAP = _CONFIG.get("VOICE_MAP", {})
EMOTION_SETTINGS = _CONFIG.get("EMOTION_SETTINGS", {})
VOICE_SAMPLES = _CONFIG.get("VOICE_SAMPLES", {})
VOICE_LABELS = _CONFIG.get("VOICE_LABELS", {})
AZURE_MONTHLY_LIMIT = _CONFIG.get("AZURE_MONTHLY_LIMIT", 500000)
USAGE_FILE = Path(__file__).resolve().parent.parent.parent / "tts_usage.json"

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
        
        if manual_voice and manual_voice != "" and isinstance(manual_voice, str) and manual_voice.strip():
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
        
        if manual_voice and manual_voice != "" and isinstance(manual_voice, str) and manual_voice.strip():
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
        logger.info("Voice assigned", character=character, gender=gender, provider=provider, voice=selected_voice, index=voice_index)
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
            logger.warn("Failed to update usage stats", error=str(e))

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
            
            # Check for Manual Voice Override
            manual_voice = segment.get("voice_id")
            if manual_voice and manual_voice != "" and isinstance(manual_voice, str) and manual_voice.strip():
                 # 1.1 If manual voice exists and is valid, preserve it!
                 # Still might need to set provider for metadata if missing
                 # But we don't overwrite it with auto-assignment.
                 pass 
            else:
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

             # Case 2b: Still missing provider or voice_id
             if not provider_name or not specific_voice_id:
                 logger.warn("Skipping generation: No voice assigned", segment_text=text[:20])
                 return

        # Determine emotion settings
        
        # Determine emotion settings
        settings = EMOTION_SETTINGS.get(emotion.lower(), EMOTION_SETTINGS["neutral"])
        
        logger.info("Routing TTS request", 
            text_snippet=text[:15], 
            provider=provider_name, 
            user_tier=user_tier, 
            voice=specific_voice_id or 'Default', 
            settings=settings, 
            pacing=pacing
        )
        
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

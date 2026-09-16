
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

from .tts import TTSProvider, build_tts_providers

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
        logger.error("Failed to load voice config", error_type=type(e).__name__)
        # Return empty defaults to avoid crash, but system will be degraded
        return {
            "VOICE_MAP": {},
            "EMOTION_SETTINGS": {},
            "VOICE_SAMPLES": {},
            "VOICE_LABELS": {},
            "AZURE_MONTHLY_LIMIT": 500000
        }

def load_avatar_map():
    map_path = Path(__file__).parent.parent / "config" / "avatar_map.json"
    try:
        if map_path.exists():
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Failed to load avatar map", error_type=type(e).__name__)
    return {}

_AVATAR_MAP = load_avatar_map()

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
                "name": VOICE_LABELS.get(node, node), # Fallback to ID if no name found
                "avatar_url": _AVATAR_MAP.get(node) # Inject Avatar URL
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

def get_public_voice_groups(languages: list = None) -> Dict:
    """
    Get the structured public voice groups (Basic/Advance).
    Deduplicates voices that appear in both 'defaults' and 'pool'.
    
    Args:
        languages: List of language codes to filter by (e.g. ["en", "zh"]). 
                  If None, returns all (or default behavior).
                  The caller handles default fallback.
    """
    full_map = get_enriched_voice_map()
    
    # Filter function for Google (Basic)
    def filter_basic(basic_map, langs):
        if not basic_map:
            return {}
        if not langs:
            return basic_map
            
        filtered = {}
        # 1. Filter top-level defaults
        for lang in langs:
             if lang in basic_map:
                 filtered[lang] = basic_map[lang]
        
        # 2. Filter pool
        if "pool" in basic_map:
            pool_filtered = {}
            for lang in langs:
                if lang in basic_map["pool"]:
                    pool_filtered[lang] = basic_map["pool"][lang]
            if pool_filtered:
                filtered["pool"] = pool_filtered
                
        return filtered

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

    # Apply Code Filtering
    basic_voices = full_map.get("google")
    advance_voices = full_map.get("elevenlabs")
    
    if languages:
        basic_voices = filter_basic(basic_voices, languages)
        
        # For Advance (ElevenLabs), since they are not language-keyed in config,
        # we treat them as compatible with EN and ZH.
        # If the user requests ONLY 'jp', we exclude them to follow "if we don't have it return empty" rule
        # (assuming we don't officially claim JP support in this system yet).
        supported_advance = {"en", "zh"}
        # If any requested language is in supported_advance, include Advance voices
        if not any(l in supported_advance for l in languages):
            advance_voices = {}

    return {
        "Basic": basic_voices,
        "Advance": advance_voices
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


class TTSManager:

    def __init__(self, providers: Optional[Dict[str, TTSProvider]] = None):
        self.providers = (
            providers if providers is not None else build_tts_providers()
        )
    
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
        logger.info(
            "Voice assigned",
            gender=gender,
            provider=provider,
            voice=selected_voice,
            index=voice_index,
        )
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
            logger.warning("Failed to update usage stats", error_type=type(e).__name__)

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

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect the supported language family used for voice selection."""
        import re
        return "zh" if re.search(r'[\u4e00-\u9fff]', text or "") else "en"

    @staticmethod
    def _apply_language_filter(lang: str, allowed_languages: list = None) -> str:
        """Keep language selection inside the caller's allowed language set."""
        if not allowed_languages or lang in allowed_languages:
            return lang
        if "en" in allowed_languages:
            return "en"
        return allowed_languages[0]

    def _get_narrator_voice(self, provider: str, lang: str) -> str:
        """Return one canonical, gender-independent narrator voice."""
        if provider == "azure":
            return f"azure:{VOICE_MAP['azure'][lang]}"
        if provider == "google":
            return f"google:{VOICE_MAP['google'][lang]['male']}"
        if provider == "openai":
            return f"openai:{VOICE_MAP['openai']['male']}"
        raise ValueError(f"Unsupported narrator provider: {provider}")

    def _assign_narrator_voice(
        self,
        script: list,
        user_tier: str,
        allowed_languages: list = None
    ) -> None:
        """Resolve the narrator once and apply that voice to every narration segment."""
        narration_segments = [
            segment for segment in script
            if segment.get("type") == "narration"
        ]
        if not narration_segments:
            return

        manual_voices = {
            segment["voice_id"].strip()
            for segment in narration_segments
            if isinstance(segment.get("voice_id"), str)
            and segment["voice_id"].strip()
        }
        if len(manual_voices) > 1:
            raise ValueError("All narration segments must use the same voice_id")

        if manual_voices:
            narrator_voice_id = next(iter(manual_voices))
        else:
            narration_text = " ".join(
                segment.get("text", "") for segment in narration_segments
            )
            lang = self._apply_language_filter(
                self._detect_language(narration_text),
                allowed_languages
            )
            provider = self.select_provider(
                segment_type="narration",
                text=narration_text,
                user_tier=user_tier,
                emotion="neutral"
            )
            narrator_voice_id = self._get_narrator_voice(provider, lang)

        for segment in narration_segments:
            segment["voice_id"] = narrator_voice_id
            segment["character"] = "Narrator"
            segment["gender"] = "neutral"

    def _assign_dialogue_voice(
        self,
        segment: Dict,
        user_tier: str,
        allowed_languages: list = None
    ) -> str:
        """Assign one deterministic voice to a dialogue segment."""
        text = segment["text"]
        character = segment.get("character", "Unknown")
        emotion = segment.get("emotion", "neutral")
        gender = segment.get("gender", "male")
        lang = self._apply_language_filter(
            self._detect_language(text),
            allowed_languages
        )
        provider = self.select_provider(
            segment_type="dialogue",
            text=text,
            user_tier=user_tier,
            emotion=emotion
        )
        voice_id = self._get_consistent_voice(
            character,
            gender,
            provider,
            lang=lang
        )
        if voice_id:
            return voice_id

        if provider == "google":
            voices = VOICE_MAP["google"][lang]
            raw_id = voices.get(gender, voices["male"])
            return f"google:{raw_id}"
        if provider == "azure":
            return f"azure:{VOICE_MAP['azure'][lang]}"
        if provider == "openai":
            raw_id = VOICE_MAP["openai"]["male" if gender == "male" else "female"]
            return f"openai:{raw_id}"
        raise ValueError(
            f"Could not assign a voice for character {character!r} using {provider}"
        )

    def prepare_script(
        self,
        script: list,
        user_tier: str = "free",
        allowed_languages: list = None
    ) -> list:
        """Copy and fully resolve a script before synthesis."""
        prepared = [dict(segment) for segment in script]
        self._assign_narrator_voice(prepared, user_tier, allowed_languages)

        for segment in prepared:
            if segment.get("type") == "narration":
                continue
            voice_id = segment.get("voice_id")
            if isinstance(voice_id, str) and voice_id.strip():
                continue
            segment["voice_id"] = self._assign_dialogue_voice(
                segment,
                user_tier,
                allowed_languages
            )

        unresolved = [
            index for index, segment in enumerate(prepared)
            if not isinstance(segment.get("voice_id"), str)
            or not segment["voice_id"].strip()
        ]
        if unresolved:
            raise ValueError(f"Voice assignment failed for segments: {unresolved}")
        return prepared

    def resolve_voice(self, segment: Dict) -> tuple[str, str]:
        """Resolve a segment voice to a provider and raw provider voice ID."""
        voice_id = str(segment.get("voice_id") or "").strip()
        provider_hint = str(segment.get("provider") or "").strip().lower()
        supported = {"google", "azure", "openai", "elevenlabs"}

        if not voice_id:
            raise ValueError(
                f"No voice assigned for character: {segment.get('character', 'unknown')}"
            )

        if ":" in voice_id:
            provider, raw_voice_id = voice_id.split(":", 1)
            provider = provider.lower()
            if provider not in supported:
                raise ValueError(f"Unsupported TTS provider: {provider}")
            if not raw_voice_id:
                raise ValueError("Voice ID cannot be empty")
            return provider, raw_voice_id

        # Backward compatibility for older clients that send raw voice IDs.
        if provider_hint in supported:
            return provider_hint, voice_id
        if "Neural2" in voice_id or "Wavenet" in voice_id:
            return "google", voice_id
        if voice_id.endswith("Neural"):
            return "azure", voice_id
        if voice_id in {"onyx", "alloy", "shimmer", "echo", "fable", "nova"}:
            return "openai", voice_id
        if len(voice_id) > 15:
            return "elevenlabs", voice_id
        raise ValueError(f"Could not determine provider for voice_id: {voice_id}")

    def get_required_providers(self, script: list) -> set[str]:
        """Return the providers actually referenced by the prepared script."""
        return {self.resolve_voice(segment)[0] for segment in script}

    def get_missing_provider_credentials(
        self,
        required_providers: set[str],
        elevenlabs_key: str = None
    ) -> list[str]:
        """Return only the providers required by this request that are unavailable."""
        missing = []
        for provider_name in sorted(required_providers):
            provider = self.providers[provider_name]
            if provider_name == "elevenlabs":
                effective_key = elevenlabs_key or provider.default_key
                if not provider.is_enabled or not effective_key:
                    missing.append(provider_name)
            elif not provider.is_enabled:
                missing.append(provider_name)
        return missing

    def assign_voices_to_script(self, script: list, user_tier: str = "free", allowed_languages: list = None) -> list:
        """
        Enrich the script by pre-calculating and assigning voices and providers.
        This allows the frontend to see and edit the voice assignments.
        """
        return self.prepare_script(script, user_tier, allowed_languages)

    async def generate(self, segment: Dict, output_file: str, user_tier: str = "free", elevenlabs_key: str = None) -> None:
        text = segment["text"]
        emotion = segment.get("emotion", "neutral")
        gender = segment.get("gender", "male")
        pacing = float(segment.get("pacing", 1.0))
        
        # Synthesis only accepts voices resolved during the preparation phase.
        provider_name, specific_voice_id = self.resolve_voice(segment)

        # Determine emotion settings
        settings = EMOTION_SETTINGS.get(emotion.lower(), EMOTION_SETTINGS["neutral"])
        
        logger.info("Routing TTS request", 
            text_characters=len(text),
            provider=provider_name, 
            user_tier=user_tier, 
            voice=specific_voice_id or 'Default', 
            settings=settings, 
            pacing=pacing
        )
        
        # Detect language
        import re
        is_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        lang_key = "zh" if is_chinese else "en"

        try:
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
                    speed=pacing,
                    api_key=elevenlabs_key,
                    settings=settings
                )

            else:
                raise Exception(f"Unknown or unsupported provider: {provider_name}")
        except Exception as e:
            logger.exception(
                "TTS provider generation failed",
                provider=provider_name,
                voice=specific_voice_id,
                segment_type=segment.get("type"),
                text_characters=len(text),
                error_type=type(e).__name__,
            )
            raise


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

    if not output_file.exists() or output_file.stat().st_size == 0:
        raise RuntimeError(
            f"TTS provider did not produce audio for character {character!r}"
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

"""
Services module for DramaFlow
Contains business logic for text analysis and audio generation
"""


from .audio_engine import generate_segment_audio, generate_script_audio, VOICE_MAP, EMOTION_SETTINGS, VOICE_SAMPLES, get_enriched_voice_map, get_public_voice_groups, generate_cast_metadata





from .post_production import merge_audio_and_generate_srt, add_background_music, get_audio_duration
from .synthesizer import synthesize_drama

__all__ = [
    "generate_segment_audio",
    "generate_script_audio",
    "merge_audio_and_generate_srt",
    "add_background_music",
    "get_audio_duration",
    "synthesize_drama",
    "VOICE_MAP",
    "EMOTION_SETTINGS",
    "VOICE_SAMPLES",
    "get_enriched_voice_map",
    "get_public_voice_groups",
    "generate_cast_metadata"
]







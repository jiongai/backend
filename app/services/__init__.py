"""
Services module for DramaFlow
Contains business logic for text analysis and audio generation
"""

from .analyzer import analyze_text
from .audio_engine import generate_segment_audio, generate_script_audio
from .post_production import merge_audio_and_generate_srt, add_background_music, get_audio_duration
from .synthesizer import synthesize_drama

__all__ = [
    "analyze_text",
    "generate_segment_audio",
    "generate_script_audio",
    "merge_audio_and_generate_srt",
    "add_background_music",
    "get_audio_duration",
    "synthesize_drama"
]


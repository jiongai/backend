"""
Audio Engine Service - Free Version (Edge TTS Only)
仅使用免费的 Edge TTS 进行测试，不需要 ElevenLabs API
"""

import os
import asyncio
from pathlib import Path
from typing import Dict
import edge_tts


# Voice mappings - 使用 Edge TTS 的不同声音
NARRATION_VOICES = {
    "male": "en-US-BrianNeural",
    "female": "en-GB-SoniaNeural"
}

DIALOGUE_VOICES = {
    "male": "en-US-GuyNeural",      # 对话使用不同的声音
    "female": "en-US-JennyNeural"   # 对话使用不同的声音
}


async def generate_segment_audio(
    segment: Dict,
    output_dir: str,
    elevenlabs_api_key: str = None  # 保持接口一致，但不使用
) -> str:
    """
    Generate audio for a single script segment using Edge TTS only.
    
    Args:
        segment: Script segment dict with keys: type, text, character, gender, emotion, pacing
        output_dir: Directory to save the generated audio file
        elevenlabs_api_key: Not used in free version
        
    Returns:
        str: Path to the generated audio file
    """
    # Validate segment structure
    required_keys = ["type", "text", "character", "gender"]
    for key in required_keys:
        if key not in segment:
            raise ValueError(f"Segment missing required key: {key}")
    
    segment_type = segment["type"]
    text = segment["text"]
    gender = segment["gender"]
    character = segment["character"]
    
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
    
    # 使用 Edge TTS 生成所有音频
    if segment_type == "narration":
        voice = NARRATION_VOICES.get(gender.lower(), NARRATION_VOICES["male"])
    else:  # dialogue
        voice = DIALOGUE_VOICES.get(gender.lower(), DIALOGUE_VOICES["male"])
    
    # Generate audio with Edge TTS
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_file))
    
    return str(output_file)


async def generate_script_audio(
    script: list,
    output_dir: str,
    elevenlabs_api_key: str = None  # 保持接口一致
) -> list:
    """
    Generate audio for all segments in a script using Edge TTS only.
    
    Args:
        script: List of script segments
        output_dir: Directory to save audio files
        elevenlabs_api_key: Not used in free version
        
    Returns:
        list: List of paths to generated audio files (in same order as script)
    """
    tasks = []
    for segment in script:
        task = generate_segment_audio(segment, output_dir, elevenlabs_api_key)
        tasks.append(task)
    
    # Generate all audio files concurrently
    audio_paths = await asyncio.gather(*tasks)
    
    return audio_paths


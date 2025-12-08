"""
Audio Engine Service
Generates audio for narration (Edge TTS) and dialogue (ElevenLabs) segments.
"""

import os
import asyncio
from pathlib import Path
from typing import Dict
import edge_tts
from elevenlabs.client import ElevenLabs


# Voice mappings

# NARRATION: Use a SINGLE consistent voice for all narration
# This ensures narrator consistency throughout the entire audio drama
NARRATION_VOICE_EN = "en-US-BrianNeural"  # English: Professional male narrator
NARRATION_VOICE_ZH = "zh-CN-YunxiNeural"  # Chinese: Professional male narrator
# Alternative Chinese narrator: "zh-CN-XiaoxiaoNeural" (Female)

# DIALOGUE: Different voices for different genders
DIALOGUE_VOICES = {
    "male": "pNInz6obpgDQGcFmaJgB",      # Adam - Deep, mature voice
    "female": "21m00Tcm4TlvDq8ikWAM"    # Rachel - Warm, friendly voice
}


async def generate_segment_audio(
    segment: Dict,
    output_dir: str,
    elevenlabs_api_key: str = None,
    narration_voice: str = None
) -> str:
    """
    Generate audio for a single script segment.
    
    Args:
        segment: Script segment dict with keys: type, text, character, gender, emotion, pacing
        output_dir: Directory to save the generated audio file
        elevenlabs_api_key: ElevenLabs API key (required for dialogue segments)
        narration_voice: Fixed narrator voice ID to use for all narration (ensures consistency)
        
    Returns:
        str: Path to the generated audio file
        
    Raises:
        ValueError: If required keys are missing or invalid values provided
        Exception: If audio generation fails
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
    
    if segment_type == "narration":
        # Use Edge TTS for narration (free)
        # NOTE: For narration, we IGNORE gender and use the consistent narrator voice
        # passed from the main script (determined once for the entire audio drama)
        await _generate_with_edge_tts(text, None, str(output_file), narration_voice)
    elif segment_type == "dialogue":
        # Use ElevenLabs for dialogue (paid)
        if not elevenlabs_api_key:
            raise ValueError("ElevenLabs API key is required for dialogue segments")
        # For dialogue, we DO use gender to select appropriate voice
        await _generate_with_elevenlabs(text, gender, str(output_file), elevenlabs_api_key)
    else:
        raise ValueError(f"Invalid segment type: {segment_type}. Must be 'narration' or 'dialogue'")
    
    return str(output_file)


async def _generate_with_edge_tts(
    text: str, 
    gender: str, 
    output_file: str,
    fixed_voice: str = None
) -> None:
    """
    Generate audio using Edge TTS (free).
    
    Args:
        text: Text to convert to speech
        gender: Gender for voice selection (only used if fixed_voice is None)
        fixed_voice: If provided, use this specific voice ID (for consistent narration)
    """
    # If a fixed voice is provided (for narration consistency), use it
    if fixed_voice:
        voice = fixed_voice
        print(f"   Using consistent narrator voice: {voice}")
    elif gender is None:
        # Fallback: use default English narrator
        voice = NARRATION_VOICE_EN
    else:
        # This shouldn't happen for narration, but kept for backwards compatibility
        voice = NARRATION_VOICE_EN
    print(f"   [EdgeTTS] Starting generation for: {text[:20]}...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Create TTS communication
            communicate = edge_tts.Communicate(text, voice)
            
            # Generate and save audio with timeout
            # Edge TTS should be fast, 30s is plenty
            await asyncio.wait_for(communicate.save(output_file), timeout=30.0)
            print(f"   [EdgeTTS] ✅ Completed: {output_file}")
            return
            
        except asyncio.TimeoutError:
            print(f"   [EdgeTTS] ⚠️ Timeout after 30s (attempt {attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                raise Exception("EdgeTTS generation timed out after retries")
        except Exception as e:
            print(f"   [EdgeTTS] ⚠️ Failed: {e} (attempt {attempt+1}/{max_retries})")
            if "No audio was received" in str(e) and attempt < max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))  # Backoff
                continue
            if attempt == max_retries - 1:
                raise


async def _generate_with_elevenlabs(
    text: str,
    gender: str,
    output_file: str,
    api_key: str,
    max_retries: int = 3
) -> None:
    """
    Generate audio using ElevenLabs (paid) with retry mechanism.
    
    Args:
        text: Text to convert to speech
        gender: Gender for voice selection (male/female)
        output_file: Path to save the audio file
        api_key: ElevenLabs API key
        max_retries: Maximum number of retry attempts (default: 3)
    """
    # Initialize ElevenLabs client
    client = ElevenLabs(api_key=api_key)
    
    # Select voice based on gender
    voice_name = DIALOGUE_VOICES.get(gender.lower(), DIALOGUE_VOICES["male"])
    
    loop = asyncio.get_event_loop()
    last_error = None
    
    # Retry mechanism for SSL/network errors
    for attempt in range(max_retries):
        try:
            print(f"   [ElevenLabs] Starting attempt {attempt+1}/{max_retries} for: {text[:20]}...")
            
            # Use the new API: text_to_speech.convert()
            # Using eleven_turbo_v2_5 - the latest free tier model
            # Wrap in wait_for to enforce timeout
            audio_generator = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.text_to_speech.convert(
                        voice_id=voice_name,
                        text=text,
                        model_id="eleven_turbo_v2_5"
                    )
                ),
                timeout=60.0
            )
            
            # Save the audio - write bytes to file
            await loop.run_in_executor(
                None,
                lambda: _save_audio_bytes(audio_generator, output_file)
            )
            
            # Success! Exit the retry loop
            if attempt > 0:
                print(f"✅ ElevenLabs API succeeded after {attempt + 1} attempts")
            return
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # Check if it's a retryable error (SSL, network, timeout)
            is_retryable = any(keyword in error_msg.lower() for keyword in [
                'ssl', 'eof', 'timeout', 'connection', 'network'
            ])
            
            if is_retryable and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                print(f"⚠️  ElevenLabs API error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                print(f"   Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                # Non-retryable error or max retries reached
                raise
    
    # If we get here, all retries failed
    raise Exception(f"ElevenLabs API failed after {max_retries} attempts: {last_error}")


def _save_audio_bytes(audio_generator, output_file: str) -> None:
    """Helper function to save audio bytes to file."""
    with open(output_file, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)


async def generate_script_audio(
    script: list,
    output_dir: str,
    elevenlabs_api_key: str = None
) -> list:
    """
    Generate audio for all segments in a script.
    
    Args:
        script: List of script segments
        output_dir: Directory to save audio files
        elevenlabs_api_key: ElevenLabs API key (required if script contains dialogue)
        
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


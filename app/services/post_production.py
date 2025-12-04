"""
Post-Production Service
Merges audio segments and generates SRT subtitles for the audio drama.
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple
from pydub import AudioSegment

# ========================================
# Configure ffmpeg for Vercel/Serverless
# ========================================
# Check if ffmpeg was configured by main.py
ffmpeg_binary = os.getenv('FFMPEG_BINARY')
if ffmpeg_binary:
    print(f"✅ [post_production] Using FFMPEG_BINARY from environment: {ffmpeg_binary}")
    # Verify it's configured in AudioSegment
    print(f"✅ [post_production] AudioSegment.converter = {AudioSegment.converter}")
    print(f"✅ [post_production] AudioSegment.ffmpeg = {AudioSegment.ffmpeg}")
else:
    print("ℹ️  [post_production] No FFMPEG_BINARY set, using system ffmpeg")
# ========================================


def format_timestamp(milliseconds: int) -> str:
    """
    Convert milliseconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        milliseconds: Time in milliseconds
        
    Returns:
        str: Formatted timestamp (e.g., "00:01:23,456")
    """
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def generate_srt_entry(index: int, start_ms: int, end_ms: int, text: str) -> str:
    """
    Generate a single SRT subtitle entry.
    
    Args:
        index: Subtitle index (1-based)
        start_ms: Start time in milliseconds
        end_ms: End time in milliseconds
        text: Subtitle text
        
    Returns:
        str: Formatted SRT entry
    """
    start_timestamp = format_timestamp(start_ms)
    end_timestamp = format_timestamp(end_ms)
    
    return f"{index}\n{start_timestamp} --> {end_timestamp}\n{text}\n"


def apply_pacing(audio: AudioSegment, pacing: float) -> AudioSegment:
    """
    Apply pacing adjustment to audio segment.
    
    Args:
        audio: Audio segment to adjust
        pacing: Pacing multiplier (0.8 = slow, 1.0 = normal, 1.2 = fast)
        
    Returns:
        AudioSegment: Adjusted audio
    """
    if pacing == 1.0:
        return audio
    
    # Speed up or slow down using frame rate manipulation
    # For pacing > 1.0: speed up (faster)
    # For pacing < 1.0: slow down (slower)
    # This preserves pitch by changing playback speed
    new_sample_rate = int(audio.frame_rate * pacing)
    
    # Change frame rate, then set it back to original to maintain compatibility
    adjusted_audio = audio._spawn(audio.raw_data, overrides={
        "frame_rate": new_sample_rate
    })
    
    # Reset to standard frame rate for compatibility
    return adjusted_audio.set_frame_rate(audio.frame_rate)


def merge_audio_and_generate_srt(segments: List[Dict], temp_dir: str) -> Tuple[str, str]:
    """
    Merge all audio segments into a single file and generate SRT subtitles.
    
    Args:
        segments: List of script segments with 'audio_file_path', 'text', and 'pacing' keys
        temp_dir: Directory to save output files
        
    Returns:
        Tuple[str, str]: Paths to (final_audio.mp3, final_subtitles.srt)
        
    Raises:
        ValueError: If segments are invalid or audio files are missing
        Exception: If audio processing fails
    """
    if not segments:
        raise ValueError("No segments provided for merging")
    
    # Ensure output directory exists
    output_path = Path(temp_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize empty audio track and subtitle list
    final_audio = AudioSegment.empty()
    srt_entries = []
    
    # Silence gap between segments (300ms)
    silence_gap = AudioSegment.silent(duration=300)
    
    # Track current position in the timeline
    current_time_ms = 0
    
    # Process each segment
    for idx, segment in enumerate(segments, start=1):
        # Validate segment
        if "audio_file_path" not in segment:
            raise ValueError(f"Segment {idx} missing 'audio_file_path'")
        if "text" not in segment:
            raise ValueError(f"Segment {idx} missing 'text'")
        
        audio_file_path = segment["audio_file_path"]
        text = segment["text"]
        pacing = segment.get("pacing", 1.0)
        
        # Check if audio file exists
        if not os.path.exists(audio_file_path):
            raise ValueError(f"Audio file not found: {audio_file_path}")
        
        # Load the audio segment
        try:
            print(f"🔍 Loading audio file: {audio_file_path}")
            print(f"🔍 AudioSegment.converter: {AudioSegment.converter}")
            print(f"🔍 AudioSegment.ffmpeg: {AudioSegment.ffmpeg}")
            audio_segment = AudioSegment.from_file(audio_file_path)
            print(f"✅ Loaded audio file: duration={len(audio_segment)}ms")
        except Exception as e:
            print(f"❌ Failed to load audio file: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to load audio file {audio_file_path}: {str(e)}")
        
        # Apply pacing adjustment if specified
        if pacing != 1.0:
            try:
                audio_segment = apply_pacing(audio_segment, pacing)
            except Exception as e:
                # If pacing fails, log warning and continue with original audio
                print(f"Warning: Failed to apply pacing {pacing} to segment {idx}: {e}")
        
        # Add silence gap before this segment (except for the first segment)
        if idx > 1:
            final_audio += silence_gap
            current_time_ms += len(silence_gap)
        
        # Record start time for SRT
        start_time_ms = current_time_ms
        
        # Append audio to the main track
        final_audio += audio_segment
        
        # Calculate end time
        end_time_ms = current_time_ms + len(audio_segment)
        current_time_ms = end_time_ms
        
        # Create SRT entry with character name if available
        character = segment.get("character", "")
        if character and character != "Narrator":
            subtitle_text = f"[{character}] {text}"
        else:
            subtitle_text = text
        
        srt_entry = generate_srt_entry(idx, start_time_ms, end_time_ms, subtitle_text)
        srt_entries.append(srt_entry)
    
    # Export final audio
    final_audio_path = output_path / "final.mp3"
    try:
        print(f"🔍 Exporting final audio to: {final_audio_path}")
        print(f"🔍 Total duration: {len(final_audio)}ms")
        print(f"🔍 AudioSegment.converter: {AudioSegment.converter}")
        
        # Test if ffmpeg is executable
        import subprocess
        try:
            result = subprocess.run([AudioSegment.converter, '-version'], 
                                  capture_output=True, timeout=5)
            print(f"✅ ffmpeg test: {result.returncode}, output: {result.stdout[:100]}")
        except Exception as ffmpeg_test_error:
            print(f"⚠️  ffmpeg test failed: {ffmpeg_test_error}")
        
        final_audio.export(
            final_audio_path,
            format="mp3",
            bitrate="192k",
            tags={
                "title": "Audio Drama",
                "artist": "DramaFlow",
                "genre": "Audio Drama"
            }
        )
        print(f"✅ Exported final audio successfully")
    except Exception as e:
        print(f"❌ Failed to export final audio: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to export final audio: {str(e)}")
    
    # Export SRT subtitles
    final_srt_path = output_path / "final.srt"
    try:
        with open(final_srt_path, "w", encoding="utf-8") as srt_file:
            for entry in srt_entries:
                srt_file.write(entry)
                srt_file.write("\n")  # Blank line between entries
    except Exception as e:
        raise Exception(f"Failed to export SRT file: {str(e)}")
    
    return str(final_audio_path), str(final_srt_path)


def get_audio_duration(audio_file_path: str) -> int:
    """
    Get the duration of an audio file in milliseconds.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        int: Duration in milliseconds
    """
    audio = AudioSegment.from_file(audio_file_path)
    return len(audio)


def add_background_music(
    main_audio_path: str,
    music_path: str,
    output_path: str,
    music_volume: int = -20
) -> str:
    """
    Add background music to the main audio track.
    
    Args:
        main_audio_path: Path to the main audio file
        music_path: Path to the background music file
        output_path: Path to save the output file
        music_volume: Volume adjustment for music in dB (negative = quieter, e.g., -20)
        
    Returns:
        str: Path to the output file
    """
    # Load audio files
    main_audio = AudioSegment.from_file(main_audio_path)
    background_music = AudioSegment.from_file(music_path)
    
    # Adjust music volume
    background_music = background_music + music_volume
    
    # Loop or trim music to match main audio duration
    if len(background_music) < len(main_audio):
        # Loop the music
        repeats = (len(main_audio) // len(background_music)) + 1
        background_music = background_music * repeats
    
    # Trim music to exact duration
    background_music = background_music[:len(main_audio)]
    
    # Overlay music onto main audio
    final_audio = main_audio.overlay(background_music)
    
    # Export
    final_audio.export(output_path, format="mp3", bitrate="192k")
    
    return output_path


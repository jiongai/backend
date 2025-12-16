import os
import asyncio
import zipfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re
import json


from .audio_engine import generate_segment_audio, generate_cast_metadata

from .post_production import merge_audio_and_generate_srt

async def synthesize_drama(
    script: List[Dict],
    temp_dir: str,
    openrouter_key: str,
    elevenlabs_key: str,
    user_tier: str = "free"
) -> str:
    """
    Orchestrate the synthesis of an audio drama from a script.
    
    Args:
        script: List of script segments (dicts)
        temp_dir: Temporary directory to store artifacts
        openrouter_key: API key for OpenRouter (not strictly used here but kept for context if needed)
        elevenlabs_key: API key for ElevenLabs
        user_tier: User tier ("free" or "vip")
        
    Returns:
        str: Path to the generated ZIP package
    """
    audio_dir = os.path.join(temp_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Extract full text for language detection (rough approximation from script)
    full_text = " ".join([s["text"] for s in script])
    
    # Step 0: Detect language for narrator
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', full_text))
    if has_chinese:
        narrator_voice = "zh-CN-YunxiNeural"
        print(f"   [Synthesizer] Detected Chinese contents. Using narrator: {narrator_voice}")
    else:
        narrator_voice = "en-US-BrianNeural"
        print(f"   [Synthesizer] Detected English contents. Using narrator: {narrator_voice}")

    # Step 1: Generate Narration (Phase 1)
    print("   [Synthesizer] Phase 1: Generating Narration...")
    
    script_with_indices = list(enumerate(script))
    narration_items = [(i, seg) for i, seg in script_with_indices if seg["type"] == "narration"]
    dialogue_items = [(i, seg) for i, seg in script_with_indices if seg["type"] == "dialogue"]
    
    narration_tasks = [
        generate_segment_audio(
            segment=seg,
            output_dir=audio_dir,
            elevenlabs_api_key=elevenlabs_key,
            narration_voice=narrator_voice,
            user_tier=user_tier
        ) for _, seg in narration_items
    ]
    
    if narration_tasks:
        try:
            narration_paths = await asyncio.gather(*narration_tasks)
            # Assign paths back to script
            for (idx, _), path in zip(narration_items, narration_paths):
                script[idx]["audio_file_path"] = path
            print(f"   [Synthesizer] ✅ Generated {len(narration_paths)} narration segments")
        except Exception as e:
            raise Exception(f"Narration generation failed: {str(e)}")

    # Step 2: Generate Dialogue (Phase 2)
    print("   [Synthesizer] Phase 2: Generating Dialogue (ElevenLabs)...")
    
    if dialogue_items:
        # ElevenLabs concurrency limit
        semaphore = asyncio.Semaphore(3)
        
        async def generate_dialogue_with_limit(segment):
            async with semaphore:
                return await generate_segment_audio(
                    segment=segment,
                    output_dir=audio_dir,
                    elevenlabs_api_key=elevenlabs_key,
                    narration_voice=narrator_voice,
                    user_tier=user_tier
                )
        
        dialogue_tasks = [
            generate_dialogue_with_limit(seg) for _, seg in dialogue_items
        ]
        
        try:
            dialogue_paths = await asyncio.gather(*dialogue_tasks)
            # Assign paths back to script
            for (idx, _), path in zip(dialogue_items, dialogue_paths):
                script[idx]["audio_file_path"] = path
            print(f"   [Synthesizer] ✅ Generated {len(dialogue_paths)} dialogue segments")
        except Exception as e:
            raise Exception(f"Dialogue generation failed: {str(e)}")
            
    # Step 3: Merge and SRT
    print("   [Synthesizer] Merging audio and generating subtitles...")
    try:
        final_audio_path, final_srt_path = merge_audio_and_generate_srt(
            segments=script,
            temp_dir=temp_dir
        )
    except Exception as e:
        raise Exception(f"Post-production failed: {str(e)}")
        
    # Step 4: Zip Package
    zip_path = os.path.join(temp_dir, "drama_package.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(final_audio_path, arcname="drama.mp3")
        zipf.write(final_srt_path, arcname="drama.srt")

    
    print(f"   [Synthesizer] Created package: {zip_path}")
    return zip_path

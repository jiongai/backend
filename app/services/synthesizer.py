import os
import asyncio
import zipfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import re
import json
import structlog

logger = structlog.get_logger(__name__)


from .audio_engine import generate_segment_audio, generate_cast_metadata

from uuid import uuid4
from .post_production import merge_audio_and_generate_srt
from .storage import r2_storage

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
        logger.info("Detected Chinese contents", voice=narrator_voice)
    else:
        narrator_voice = "en-US-BrianNeural"
        logger.info("Detected English contents", voice=narrator_voice)

    # Step 0.5: Enforce Voice Assignment (Double Insurance)
    # Ensure all segments have a valid voice_id assigned before processing.
    # This covers cases where frontend sends raw chunks.
    from .audio_engine import tts_manager
    script = tts_manager.assign_voices_to_script(script, user_tier=user_tier)

    # Step 1: Generate Narration (Phase 1)
    logger.info("Starting Phase 1: Narration")
    
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
            logger.info("Generated narration segments", count=len(narration_paths))
        except Exception as e:
            raise Exception(f"Narration generation failed: {str(e)}")

    # Step 2: Generate Dialogue (Phase 2)
    logger.info("Starting Phase 2: Dialogue", provider="ElevenLabs")
    
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
            logger.info("Generated dialogue segments", count=len(dialogue_paths))
        except Exception as e:
            raise Exception(f"Dialogue generation failed: {str(e)}")
            
    # Step 3: Merge and SRT
    logger.info("Merging audio and generating subtitles")
    try:
        final_audio_path, final_srt_path, timeline_data = merge_audio_and_generate_srt(
            segments=script,
            temp_dir=temp_dir
        )
    except Exception as e:
        raise Exception(f"Post-production failed: {str(e)}")
        
    # Step 4: Upload to Cloudflare R2
    logger.info("Uploading artifacts to R2")
    
    # Generate IDs
    # In a real app, project_id might come from the request. 
    # For now, we put everything in a 'demos' folder or similar.
    project_id = "demos"
    chapter_id = str(uuid4())
    
    try:
        # Upload Audio
        audio_key = r2_storage.upload_file(
            file_path=final_audio_path,
            project_id=project_id,
            chapter_id=chapter_id,
            content_type="audio/mpeg"
        )
        
        # Upload SRT
        srt_key = r2_storage.upload_file(
            file_path=final_srt_path,
            project_id=project_id,
            chapter_id=chapter_id,
            content_type="application/x-subrip" # Standard for SRT
        )
        
        # Construct Public URLs
        # Assuming the bucket is public or has a custom domain.
        # R2 public buckets usually look like: https://pub-<hash>.r2.dev/<key>
        # OR user must provide a public domain base.
        # Let's assume we pull a public domain env var or fall back to constructing it.
        # But for now, returning the Key might be safer if the frontend constructs the URL, 
        # or we return a presigned URL?
        # User request said: "interface directly return 2 file's url".
        # Let's assume we use a configured public domain.
        
        public_domain = os.getenv("R2_PUBLIC_DOMAIN")
        if not public_domain:
            # Fallback to just the key if domain not set, or warn
            logger.warn("R2_PUBLIC_DOMAIN not set", action="returning_keys_only")
            audio_url = audio_key
            srt_url = srt_key
        else:
            # Ensure domain doesn't have trailing slash
            public_domain = public_domain.rstrip("/")
            audio_url = f"{public_domain}/{audio_key}"
            srt_url = f"{public_domain}/{srt_key}"
            
        logger.info("Upload Complete", audio=audio_url, srt=srt_url)
        
        # Remove temp files immediately (as requested)
        # We are inside a temp_dir managed by the caller (synthesize_drama's temp_dir arg),
        # but cleanup is often done by the caller (BackgroundTasks).
        # However, user said "upload complete delete temp files".
        # The temp_dir is passed in. If we delete contents here, the caller's cleanup might fail or be redundant.
        # Safe strategy: We can delete the specific files we created.
        if os.path.exists(final_audio_path):
            os.remove(final_audio_path)
        if os.path.exists(final_srt_path):
            os.remove(final_srt_path)
            
        return {
            "audio_url": audio_url,
            "srt_url": srt_url,
            "timeline": timeline_data
        }

    except Exception as e:
        raise Exception(f"Upload failed: {str(e)}")


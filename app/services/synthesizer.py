import os
import asyncio
from typing import List, Dict
import structlog

logger = structlog.get_logger(__name__)


from .audio_engine import generate_segment_audio, tts_manager

from uuid import uuid4
from .post_production import merge_audio_and_generate_srt
from .storage import r2_storage

async def synthesize_drama(
    script: List[Dict],
    temp_dir: str,
    elevenlabs_key: str,
    user_tier: str = "free"
) -> Dict:
    """
    Orchestrate the synthesis of an audio drama from a script.
    
    Args:
        script: List of script segments (dicts)
        temp_dir: Temporary directory to store artifacts
        elevenlabs_key: API key for ElevenLabs
        user_tier: User tier ("free" or "vip")
        
    Returns:
        dict: Public artifact URLs and timeline data
    """
    audio_dir = os.path.join(temp_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # The API normally prepares the script before credential validation. Do it
    # again here so direct service callers receive the same safe behavior.
    script = tts_manager.prepare_script(script, user_tier=user_tier)

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
            logger.exception(
                "Phase 1: Narration generation failed",
                count=len(narration_items),
                error_type=type(e).__name__,
            )
            raise Exception(f"Narration generation failed: {str(e)}")

    # Step 2: Generate Dialogue (Phase 2)
    logger.info("Starting Phase 2: Dialogue", count=len(dialogue_items))
    
    if dialogue_items:
        # ElevenLabs concurrency limit
        semaphore = asyncio.Semaphore(3)
        
        async def generate_dialogue_with_limit(segment):
            async with semaphore:
                return await generate_segment_audio(
                    segment=segment,
                    output_dir=audio_dir,
                    elevenlabs_api_key=elevenlabs_key,
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
            logger.exception(
                "Phase 2: Dialogue generation failed",
                count=len(dialogue_items),
                error_type=type(e).__name__,
            )
            raise Exception(f"Dialogue generation failed: {str(e)}")
            
    # Step 3: Merge and SRT
    logger.info("Merging audio and generating subtitles", segments_count=len(script))
    try:
        final_audio_path, final_srt_path, timeline_data = merge_audio_and_generate_srt(
            segments=script,
            temp_dir=temp_dir
        )
    except Exception as e:
        logger.exception(
            "Phase 3: Audio merge and SRT generation failed",
            error_type=type(e).__name__,
        )
        raise Exception(f"Post-production failed: {str(e)}")
        
    # Step 4: Upload to Cloudflare R2
    logger.info("Uploading artifacts to R2")
    
    # Generate IDs
    # In a real app, project_id might come from the request. 
    # For now, we put everything in a 'demos' folder or similar.
    project_id = os.getenv("R2_PROJECT_ID", "Railway") # Updated to use Env Var
    chapter_id = str(uuid4())
    
    try:
        # Upload Audio
        audio_key = r2_storage.upload_file(
            file_path=final_audio_path,
            project_id=project_id,
            chapter_id=chapter_id,
            content_type="audio/mpeg",
            subfolder="temp"
        )
        
        # Upload SRT
        srt_key = r2_storage.upload_file(
            file_path=final_srt_path,
            project_id=project_id,
            chapter_id=chapter_id,
            content_type="application/x-subrip", # Standard for SRT
            subfolder="temp"
        )
        
        audio_url = r2_storage.build_public_url(audio_key)
        srt_url = r2_storage.build_public_url(srt_key)
            
        logger.info("Upload complete", project_id=project_id, chapter_id=chapter_id)
        
        # Remove temp files immediately (as requested)
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
        logger.exception(
            "Phase 4: R2 upload failed",
            project_id=project_id,
            chapter_id=chapter_id,
            error_type=type(e).__name__,
        )
        raise Exception(f"Upload failed: {str(e)}")

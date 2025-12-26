"""
DramaFlow - Audio Drama Generation API
Main FastAPI application
"""

import os
import shutil
import asyncio
import tempfile
import zipfile
import json
from pathlib import Path

from typing import List, Dict, Optional, Any
import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from app.core.logging import configure_logging

# Configure logging immediately
configure_logging()
logger = structlog.get_logger()

# ========================================
# Configure ffmpeg for Serverless
# ========================================
# CRITICAL: Must set environment variables BEFORE importing pydub
if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    # Try root vendor (local)
    root_vendor_dir = Path(__file__).parent.parent / "vendor"
    
    ffmpeg_path = None
    if (root_vendor_dir / "ffmpeg").exists():
        ffmpeg_path = str(root_vendor_dir / "ffmpeg")
    
    if ffmpeg_path:
        # Set environment variables BEFORE importing pydub
        # This way pydub will find ffmpeg during initialization
        os.environ['FFMPEG_BINARY'] = ffmpeg_path
        os.environ['FFPROBE_BINARY'] = ffmpeg_path
        logger.info("Set FFMPEG_BINARY", path=ffmpeg_path)
        
        # Also configure AudioSegment after import (belt and suspenders)
        from pydub import AudioSegment
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg_path
        AudioSegment.ffprobe = ffmpeg_path
        logger.info("Configured AudioSegment")
    else:
        logger.warn("ffmpeg not found in vendor directory")
else:
    logger.info("Running locally or on Railway, using system ffmpeg")
# ========================================

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Header, Query, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator, Field
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv(override=True)

from app.services.synthesizer import synthesize_drama
from app.services.audio_engine import (
    generate_cast_metadata,
    tts_manager,
    generate_segment_audio,
    VOICE_MAP,
    EMOTION_SETTINGS,
    VOICE_SAMPLES,
    get_enriched_voice_map,
    get_public_voice_groups
)
from app.services.post_production import merge_audio_and_generate_srt





# Initialize FastAPI app
app = FastAPI(
    title="DramaFlow API",
    description="Convert novel text into immersive audio dramas with AI",
    version="1.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Request ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# ========================================
# Security Dependency
# ========================================
api_key_header = APIKeyHeader(name="X-Access-Secret", auto_error=False)

async def verify_secret_key(header_secret: str = Security(api_key_header)):
    """
    Verify the access secret provided in headers.
    """
    correct_secret = os.getenv("DARMAFLOW_API_ACCESS_SECRET")
    
    # If no secret is set in env, allow open access (or default to secure, depending on policy)
    # Here we allow open access if variable is missing to prevent breaking local setups immediately
    # unless user explicitly sets it.
    if not correct_secret:
        return header_secret
        
    if header_secret != correct_secret:
        raise HTTPException(
            status_code=403,
            detail="Access Denied: Invalid Security Key"
        )
    return header_secret



# Request Models
class SynthesizeRequest(BaseModel):
    """Request model for synthesis from existing script."""
    script: list = Field(
        ...,
        description="Structured script segments to synthesize"
    )
    limit: Optional[int] = Field(
        None,
        description="Number of segments to generate. 0 = none. None = all."
    )



class DramaResponse(BaseModel):
    """Response model for audio drama generation."""
    message: str
    segments_count: int
    audio_duration_ms: Optional[int] = None
    audio_url: Optional[str] = None
    srt_url: Optional[str] = None
    timeline: Optional[List[Dict[str, Any]]] = None

class ReviewRequest(BaseModel):
    """Request model for voice preview/review."""
    text: str = Field(..., description="Text to speak", max_length=100)
    voice_id: str = Field(..., description="Voice ID to test")
    pacing: Optional[float] = Field(1.0, description="Speaking speed (0.25-4.0)")
    emotion: Optional[str] = Field("neutral", description="Emotion style")
    
class SaveFilesRequest(BaseModel):
    """Request model for saving/copying files."""
    audio_url: str = Field(..., description="Current URL of the audio file")
    srt_url: str = Field(..., description="Current URL of the SRT file")

class DeleteFilesRequest(BaseModel):
    """Request model for deleting files."""
    audio_url: Optional[str] = Field(None, description="URL of the audio file to delete")
    srt_url: Optional[str] = Field(None, description="URL of the SRT file to delete")

class MoveFilesToTempRequest(BaseModel):
    """Request model for moving files back to temp."""
    audio_url: str = Field(..., description="Current URL of the audio file (must be in 'saved')")
    srt_url: str = Field(..., description="Current URL of the SRT file (must be in 'saved')")




# Helper function for cleanup
def cleanup_temp_directory(directory: str):
    """
    Remove temporary directory and all its contents.
    
    Args:
        directory: Path to the directory to remove
    """
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            logger.info("Cleaned up temp directory", directory=directory)
    except Exception as e:
        logger.warn("Failed to cleanup temp directory", directory=directory, error=str(e))


# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "DramaFlow API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check with API key validation."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    
    return {
        "status": "healthy",
        "openrouter_configured": bool(openrouter_key),
        "elevenlabs_configured": bool(elevenlabs_key)
    }


@app.post("/assign_voices", response_model=Dict[str, Any], dependencies=[Depends(verify_secret_key)])
async def assign_voices(
    request: SynthesizeRequest,
    languages: Optional[List[str]] = Query(None),
    user_tier: str = Header("free", alias="X-User-Tier")
):
    """
    Assign voices to a script without generating audio.
    Useful for frontend 'Magic Fill' or pre-synthesis configuration.
    """
    try:
        logger.info("Assign voices request received", user_tier=user_tier, languages=languages)
        logger.info("Assign voices parameters", script=request.script)

        # Normalize languages
        normalized_langs = None
        if languages:
            normalized_langs = []
            for l in languages:
                l_lower = l.lower()
                if l_lower in ["cn", "zh-cn", "zh-tw"]:
                    normalized_langs.append("zh")
                elif l_lower.startswith("en"):
                    normalized_langs.append("en")
                else:
                    normalized_langs.append(l_lower)
            normalized_langs = list(set(normalized_langs)) # Dedup
        else:
            # Default to English if no language filter provided
            normalized_langs = ["en"]

        # Auto-assign voices
        enriched_script = tts_manager.assign_voices_to_script(
            request.script, 
            user_tier=user_tier,
            allowed_languages=normalized_langs
        )
        
        response_data = {
            "message": "Voices assigned successfully",
            "script": enriched_script,
            "metadata": {
                "segments_count": len(enriched_script),
                "characters": list(set(s.get("character", "") for s in enriched_script if s.get("character")))
            }
        }
        
        logger.info("Assign voices response", response=response_data)
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/synthesize", response_model=DramaResponse, dependencies=[Depends(verify_secret_key)])
async def synthesize_audio_drama(
    request: SynthesizeRequest,
    background_tasks: BackgroundTasks,
    openrouter_api_key: Optional[str] = Header(None, alias="X-OpenRouter-API-Key"),
    elevenlabs_api_key: Optional[str] = Header(None, alias="X-ElevenLabs-API-Key"),
    user_tier: str = Header("free", alias="X-User-Tier")
):
    """
    Synthesize audio from a provided JSON script.
    """
    # Get API keys
    openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    elevenlabs_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
    
    if not elevenlabs_key:
        raise HTTPException(
            status_code=400,
            detail="ElevenLabs API key is required."
        )

    # Create temp dir
    temp_dir = tempfile.mkdtemp(prefix="dramaflow_synth_")
    
    try:
        logger.info("Synthesize request received", user_tier=user_tier, script_segments=len(request.script))
        logger.info("Request parameters", limit=request.limit, script=request.script)

        
        if request.limit is not None:
            if request.limit == 0:
                logger.info("Limit=0, skipping synthesis")
                return DramaResponse(
                    message="Synthesis skipped (limit=0)",
                    segments_count=0,
                    audio_url=None,
                    srt_url=None,
                    timeline=None
                )
            elif request.limit > 0:
                logger.info("Limiting synthesis", limit=request.limit)
                request.script = request.script[:request.limit]

        # Result is now a dict with URLs
        result = await synthesize_drama(
            script=request.script,
            temp_dir=temp_dir,
            openrouter_key=openrouter_key,
            elevenlabs_key=elevenlabs_key,
            user_tier=user_tier
        )
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_directory, temp_dir)
        
        return DramaResponse(
            message="Synthesis successful",
            segments_count=len(request.script),
            audio_url=result["audio_url"],
            srt_url=result["srt_url"],
            timeline=result.get("timeline")
        )
        
    except Exception as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))




@app.post("/review", response_class=FileResponse, dependencies=[Depends(verify_secret_key)])
async def review_voice(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    elevenlabs_api_key: Optional[str] = Header(None, alias="X-ElevenLabs-API-Key"),
    user_tier: str = Header("free", alias="X-User-Tier")
):
    """
    Generate a single audio clip for previewing a voice.
    """
    elevenlabs_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
    
    # Create temp dir
    temp_dir = tempfile.mkdtemp(prefix="dramaflow_review_")
    output_file = Path(temp_dir) / "preview.mp3"
    
    
    try:
        logger.info("Review request", text=request.text, voice=request.voice_id)
        # Construct a temporary segment forcing the voice
        # Truncate text to first 30 chars for preview
        truncated_text = request.text[:30]
        
        segment = {
            "type": "dialogue", 
            "text": truncated_text,
            "character": "Preview",
            "voice_id": request.voice_id,
            # "provider": request.provider, # Removed: Parsing from voice_id in audio_engine
            "pacing": request.pacing,    
            "emotion": request.emotion   
        }

        
        # We use generate_segment_audio's logic but direct via tts_manager is better controlled
        # But wait, tts_manager.generate() is what we want because it handles the 'voice' logic we just added.
        # We need to access the singleton tts_manager used inside services.
        # It's not directly imported here, but `generate_segment_audio` is a wrapper around it.
        # Let's use `generate_segment_audio` as it exposes `user_tier` and `elevenlabs_api_key`
        
        await generate_segment_audio(
            segment=segment,
            output_dir=temp_dir,
            elevenlabs_api_key=elevenlabs_key,
            user_tier=user_tier
        )
        
        # Find the generated file (name is hashed)
        files = list(Path(temp_dir).glob("*.mp3"))
        if not files:
            raise Exception("Audio generation failed (no file produced)")
            
        generated_file = files[0]
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_directory, temp_dir)
        
        return FileResponse(
            path=generated_file,
            media_type="audio/mpeg",
            filename="preview.mp3"
        )

    except Exception as e:
        cleanup_temp_directory(temp_dir)
        logger.error("Review generation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))



        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save_files", response_model=Dict[str, str], dependencies=[Depends(verify_secret_key)])
async def save_files(request: SaveFilesRequest):
    """
    Save generated files (from temp or saved) as NEW standalone copies.
    Returns the new URLs.
    """
    from app.services.storage import r2_storage
    
    try:
        logger.info("Save files request", audio=request.audio_url, srt=request.srt_url)
        
        # Save Audio (Copy to New UUID)
        new_audio_url = r2_storage.save_file_as_new(request.audio_url)
        
        # Save SRT (Copy to New UUID)
        new_srt_url = r2_storage.save_file_as_new(request.srt_url)
        
        logger.info("Files saved and isolated", audio=new_audio_url, srt=new_srt_url)
        
        return {
            "audio_url": new_audio_url,
            "srt_url": new_srt_url
        }
    except ValueError as ve:
        logger.warn("Save files validation failed", error=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Save files failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/del_files", dependencies=[Depends(verify_secret_key)])
async def delete_files(request: DeleteFilesRequest):
    """
    Delete audio and/or SRT files from storage.
    """
    from app.services.storage import r2_storage
    
    results = {}
    try:
        if request.audio_url:
            results["audio"] = r2_storage.delete_file(request.audio_url)
        
        if request.srt_url:
            results["srt"] = r2_storage.delete_file(request.srt_url)
            
        logger.info("Delete files request processed", results=results)
        return {
            "message": "Files deletion processed",
            "details": results
        }
    except Exception as e:
        logger.error("Delete files failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/move_files_to_temp", response_model=Dict[str, str], dependencies=[Depends(verify_secret_key)])
async def move_files_to_temp(request: MoveFilesToTempRequest):
    """
    Move files from 'saved' folder back to 'temp' folder.
    Returns the new URLs.
    """
    from app.services.storage import r2_storage
    
    try:
        logger.info("Move files to temp request", audio=request.audio_url, srt=request.srt_url)
        
        # Move Audio
        new_audio_url = r2_storage.move_file_to_temp(request.audio_url)
        
        # Move SRT
        new_srt_url = r2_storage.move_file_to_temp(request.srt_url)
        
        logger.info("Files moved to temp", audio=new_audio_url, srt=new_srt_url)
        
        return {
            "audio_url": new_audio_url,
            "srt_url": new_srt_url
        }
    except ValueError as ve:
        logger.warn("Move files validation failed", error=str(ve))
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Move files failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices", response_model=dict, dependencies=[Depends(verify_secret_key)])
async def get_available_voices(languages: Optional[List[str]] = Query(None)):
    """
    Get configuration of available voices and settings.
    Optional languages filter (e.g. ?languages=en&languages=zh)
    Returns:
    - voice_map: { "Basic": <Google>, "Advance": <ElevenLabs> }
    - emotion_settings: Emotion parameters
    - samples: Voice sample URLs
    """
    # Normalize languages
    normalized_langs = None
    if languages:
        normalized_langs = []
        for l in languages:
            l_lower = l.lower()
            if l_lower in ["cn", "zh-cn", "zh-tw"]:
                normalized_langs.append("zh")
            elif l_lower.startswith("en"):
                normalized_langs.append("en")
            else:
                normalized_langs.append(l_lower)
        normalized_langs = list(set(normalized_langs)) # Dedup
    else:
        # Default behavior: if not filled, default is English ('en')
        normalized_langs = ["en"]

    return {
        "voice_map": get_public_voice_groups(languages=normalized_langs),
        "emotion_settings": EMOTION_SETTINGS,
        "samples": VOICE_SAMPLES
    }






# Run the app
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )


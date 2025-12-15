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

from typing import Optional

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
        print(f"✅ [main] Set FFMPEG_BINARY: {ffmpeg_path}")
        
        # Also configure AudioSegment after import (belt and suspenders)
        from pydub import AudioSegment
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg_path
        AudioSegment.ffprobe = ffmpeg_path
        print(f"✅ [main] Configured AudioSegment")
    else:
        print(f"⚠️  [main] ffmpeg not found")
else:
    print("ℹ️  [main] Running locally or on Railway, using system ffmpeg")
# ========================================

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from app.services.analyzer import analyze_text, analyze_text_doubao
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


# Request Models
class DramaRequest(BaseModel):
    """Request model for audio drama generation."""
    text: str = Field(
        ...,
        description="Novel text to convert into audio drama",
        min_length=10,
        max_length=10000
    )

class SynthesizeRequest(BaseModel):
    """Request model for synthesis from existing script."""
    script: list = Field(
        ...,
        description="Structured script segments to synthesize"
    )

class DramaRequest(BaseModel):
    """Request model for audio drama generation."""
    text: str = Field(
        ...,
        description="Novel text to convert into audio drama",
        min_length=10,
        max_length=10000
    )

class DramaResponse(BaseModel):
    """Response model for audio drama generation."""
    message: str
    segments_count: int
class DramaResponse(BaseModel):
    """Response model for audio drama generation."""
    message: str
    segments_count: int
    audio_duration_ms: Optional[int] = None

class ReviewRequest(BaseModel):
    """Request model for voice preview/review."""
    text: str = Field(..., description="Text to speak", max_length=100)
    voice_id: str = Field(..., description="Voice ID to test")




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
            print(f"Cleaned up temp directory: {directory}")
    except Exception as e:
        print(f"Warning: Failed to cleanup temp directory {directory}: {e}")


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


@app.post("/synthesize", response_model=DramaResponse)
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
        print(f"   [DEBUG] /synthesize params - User Tier: {user_tier}")
        print(f"   [DEBUG] /synthesize params - Script:\n{json.dumps(request.script, ensure_ascii=False, indent=2)}")
        print(f"Synthesizing from provided script ({len(request.script)} segments)...")

        
        zip_path = await synthesize_drama(
            script=request.script,
            temp_dir=temp_dir,
            openrouter_key=openrouter_key,
            elevenlabs_key=elevenlabs_key,
            user_tier=user_tier
        )
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_directory, temp_dir)
        
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename="drama_package.zip",
            headers={
                "X-Segments-Count": str(len(request.script)),
                "X-Package-Contents": "drama.mp3,drama.srt"
            }
        )
        
    except Exception as e:
        cleanup_temp_directory(temp_dir)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate", response_model=DramaResponse)
async def generate_audio_drama(
    request: DramaRequest,
    background_tasks: BackgroundTasks,
    openrouter_api_key: Optional[str] = Header(None, alias="X-OpenRouter-API-Key"),
    elevenlabs_api_key: Optional[str] = Header(None, alias="X-ElevenLabs-API-Key"),
    user_tier: str = Header("free", alias="X-User-Tier")  # "free" or "vip"
):
    """
    Full pipeline: Analyze -> Synthesize.
    """
    # Get API keys
    openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    elevenlabs_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
    
    if not openrouter_key or not elevenlabs_key:
        raise HTTPException(status_code=400, detail="API keys required")
    
    # Create unique temporary directory for analysis intermediate artifacts if needed,
    # but synthesize_drama creates its own.
    # However, analyze_text is pure logic.
    
    try:
        # Step 1: Analyze
        print(f"Analyzing text ({len(request.text)} characters)...")
        try:
            analysis_result = await analyze_text(request.text, openrouter_key)
        except Exception as e:
             raise HTTPException(status_code=504, detail=f"Analysis failed: {str(e)}")

        script = analysis_result.get("script")
        if not script:
             raise HTTPException(status_code=500, detail="No script generated")
             
        # Step 2: Synthesize (calling the service directly, not the endpoint)
        # We need a temp dir for synthesis
        temp_dir = tempfile.mkdtemp(prefix="dramaflow_gen_")
        
        try:
            zip_path = await synthesize_drama(
                script=script,
                temp_dir=temp_dir,
                openrouter_key=openrouter_key,
                elevenlabs_key=elevenlabs_key,
                user_tier=user_tier
            )
            
            background_tasks.add_task(cleanup_temp_directory, temp_dir)
            
            return FileResponse(
                path=zip_path,
                media_type="application/zip",
                filename="drama_package.zip",
                headers={
                    "X-Segments-Count": str(len(script)),
                    "X-Package-Contents": "drama.mp3,drama.srt"
                }
            )
        except Exception as e:
            cleanup_temp_directory(temp_dir)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating audio drama: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate audio drama: {str(e)}"
        )

@app.post("/review", response_class=FileResponse)
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
        # Construct a temporary segment forcing the voice
        # Truncate text to first 30 chars for preview
        truncated_text = request.text[:30]
        
        segment = {
            "type": "dialogue", # Broadest compatibility
            "text": truncated_text,
            "character": "Preview",
            "voice": request.voice_id, # Manually override
            "pacing": 1.0,
            "emotion": "neutral" 
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
        print(f"Review generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze", response_model=dict)
async def analyze_only(
    request: DramaRequest,
    openrouter_api_key: Optional[str] = Header(None, alias="X-OpenRouter-API-Key")
):
    """
    Analyze text and return the structured script without generating audio.
    Useful for previewing the script before full generation.
    """
    # Get API key
    openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    
    if not openrouter_key:
        raise HTTPException(
            status_code=400,
            detail="OpenRouter API key is required"
        )
    
    try:
        # Analyze text
        result = await analyze_text(request.text, openrouter_key)
        
        # Add metadata
        if "script" in result:
            result["metadata"] = {
                "segments_count": len(result["script"]),
                "narration_count": sum(1 for s in result["script"] if s.get("type") == "narration"),
                "dialogue_count": sum(1 for s in result["script"] if s.get("type") == "dialogue"),
                "characters": list(set(s.get("character", "") for s in result["script"] if s.get("character")))
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze text: {str(e)}"
        )

@app.post("/analyze_lite", response_model=dict)
async def analyze_lite(
    request: DramaRequest,
    ark_api_key: Optional[str] = Header(None, alias="X-Ark-API-Key")
):
    """
    Analyze text using Doubao (Volcengine Ark).
    Same input/output format as /analyze.
    """
    # Get API key
    ark_key = ark_api_key or os.getenv("ARK_API_KEY")
    
    if not ark_key:
        raise HTTPException(
            status_code=400,
            detail="Ark API key is required (X-Ark-API-Key header or ARK_API_KEY env)"
        )
    
    try:
        # Analyze text using Doubao
        result = await analyze_text_doubao(request.text, ark_key)
        
        # Add metadata (Same logic as standard analyze)
        if "script" in result:
            result["metadata"] = {
                "segments_count": len(result["script"]),
                "narration_count": sum(1 for s in result["script"] if s.get("type") == "narration"),
                "dialogue_count": sum(1 for s in result["script"] if s.get("type") == "dialogue"),
                "characters": list(set(s.get("character", "") for s in result["script"] if s.get("character")))
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze text (Lite): {str(e)}"
        )



@app.get("/voices", response_model=dict)
async def get_available_voices():
    """
    Get configuration of available voices and settings.
    Returns:
    - voice_map: { "Basic": <Google>, "Advance": <ElevenLabs> }
    - emotion_settings: Emotion parameters
    - samples: Voice sample URLs
    """
    return {
        "voice_map": get_public_voice_groups(),
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


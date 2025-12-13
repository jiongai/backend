"""
DramaFlow - Audio Drama Generation API
Main FastAPI application
"""

import os
import shutil
import asyncio
import tempfile
import zipfile
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

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from app.services import (
    analyze_text,
    generate_segment_audio,
    analyze_text,
    generate_segment_audio,
    merge_audio_and_generate_srt,
    synthesize_drama
)

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
    audio_duration_ms: Optional[int] = None


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


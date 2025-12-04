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
# Configure ffmpeg for Vercel/Serverless
# ========================================
# Note: Main configuration is in post_production.py
# This is kept as backup/fallback
if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    # Try api/vendor first (Vercel), then root vendor (local)
    api_vendor_dir = Path(__file__).parent.parent / "api" / "vendor"
    root_vendor_dir = Path(__file__).parent.parent / "vendor"
    
    ffmpeg_path = None
    if (api_vendor_dir / "ffmpeg").exists():
        ffmpeg_path = api_vendor_dir / "ffmpeg"
        print(f"✅ [main] Found ffmpeg in api/vendor: {ffmpeg_path}")
    elif (root_vendor_dir / "ffmpeg").exists():
        ffmpeg_path = root_vendor_dir / "ffmpeg"
        print(f"✅ [main] Found ffmpeg in root vendor: {ffmpeg_path}")
    else:
        print(f"⚠️  [main] ffmpeg not found in {api_vendor_dir} or {root_vendor_dir}")
else:
    print("ℹ️  [main] Running locally, using system ffmpeg")
# ========================================

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.services import (
    analyze_text,
    generate_segment_audio,
    merge_audio_and_generate_srt
)

# Load environment variables
load_dotenv()

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


@app.post("/generate", response_model=DramaResponse)
async def generate_audio_drama(
    request: DramaRequest,
    background_tasks: BackgroundTasks,
    openrouter_api_key: Optional[str] = Header(None, alias="X-OpenRouter-API-Key"),
    elevenlabs_api_key: Optional[str] = Header(None, alias="X-ElevenLabs-API-Key")
):
    """
    Generate an audio drama from novel text.
    
    This endpoint:
    1. Analyzes the text and converts it to a structured script
    2. Generates audio for each segment (narration and dialogue)
    3. Merges all audio segments with proper timing
    4. Generates synchronized SRT subtitles
    5. Returns the final audio file
    
    API keys can be provided via headers or environment variables.
    """
    # Get API keys from headers or environment variables
    openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    elevenlabs_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
    
    # Validate API keys
    if not openrouter_key:
        raise HTTPException(
            status_code=400,
            detail="OpenRouter API key is required. Set OPENROUTER_API_KEY env var or pass X-OpenRouter-API-Key header."
        )
    
    if not elevenlabs_key:
        raise HTTPException(
            status_code=400,
            detail="ElevenLabs API key is required. Set ELEVENLABS_API_KEY env var or pass X-ElevenLabs-API-Key header."
        )
    
    # Create unique temporary directory for this request
    temp_dir = tempfile.mkdtemp(prefix="dramaflow_")
    audio_dir = os.path.join(temp_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    try:
        # Step 1: Analyze text and convert to script
        print(f"Analyzing text ({len(request.text)} characters)...")
        analysis_result = await analyze_text(request.text, openrouter_key)
        
        if "script" not in analysis_result:
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze text: Invalid response format"
            )
        
        script = analysis_result["script"]
        
        if not script:
            raise HTTPException(
                status_code=400,
                detail="No script segments generated from the provided text"
            )
        
        print(f"Generated script with {len(script)} segments")
        
        # Step 1.5: Detect language and determine consistent narrator voice
        # This ensures ALL narration uses the SAME voice throughout the entire drama
        import re
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', request.text))
        
        # Choose ONE narrator voice for the entire script
        if has_chinese:
            narrator_voice = "zh-CN-YunxiNeural"  # Chinese male narrator
            print(f"Detected Chinese text. Using narrator: zh-CN-YunxiNeural")
        else:
            narrator_voice = "en-US-BrianNeural"  # English male narrator
            print(f"Detected English text. Using narrator: en-US-BrianNeural")
        
        # Step 2: Generate audio for all segments with controlled concurrency
        print("Generating audio for segments...")
        
        # Limit concurrent requests to avoid API rate limits
        # ElevenLabs free tier: max 4 concurrent requests
        # Use 3 to be safe
        semaphore = asyncio.Semaphore(3)
        
        async def generate_with_limit(segment):
            async with semaphore:
                return await generate_segment_audio(
                    segment=segment,
                    output_dir=audio_dir,
                    elevenlabs_api_key=elevenlabs_key,
                    narration_voice=narrator_voice  # Pass the fixed narrator voice
                )
        
        # Create tasks with concurrency control
        audio_generation_tasks = [
            generate_with_limit(segment) for segment in script
        ]
        
        # Execute all audio generation tasks with controlled concurrency
        audio_paths = await asyncio.gather(*audio_generation_tasks)
        
        # Add audio file paths back to segments
        for segment, audio_path in zip(script, audio_paths):
            segment["audio_file_path"] = audio_path
        
        print(f"Generated {len(audio_paths)} audio files")
        
        # Step 3: Merge audio and generate SRT
        print("Merging audio and generating subtitles...")
        final_audio_path, final_srt_path = merge_audio_and_generate_srt(
            segments=script,
            temp_dir=temp_dir
        )
        
        print(f"Final audio: {final_audio_path}")
        print(f"Final SRT: {final_srt_path}")
        
        # Step 4: Create a ZIP file containing both MP3 and SRT
        zip_path = os.path.join(temp_dir, "drama_package.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add MP3 file
            zipf.write(final_audio_path, arcname="drama.mp3")
            # Add SRT file
            zipf.write(final_srt_path, arcname="drama.srt")
        
        print(f"Created package: {zip_path}")
        
        # Schedule cleanup after response is sent
        background_tasks.add_task(cleanup_temp_directory, temp_dir)
        
        # Return the ZIP file containing both audio and subtitles
        return FileResponse(
            path=zip_path,
            media_type="application/zip",
            filename="drama_package.zip",
            headers={
                "X-Segments-Count": str(len(script)),
                "X-Package-Contents": "drama.mp3,drama.srt"
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        cleanup_temp_directory(temp_dir)
        raise
        
    except Exception as e:
        # Clean up on error
        cleanup_temp_directory(temp_dir)
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


"""Voice catalog, assignment, and preview routes."""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.dependencies import normalize_languages, verify_secret_key
from app.api.errors import internal_error
from app.api.schemas import ReviewRequest, SynthesizeRequest
from app.api.utils import cleanup_temp_directory
from app.core.settings import get_settings
from app.services.audio_engine import (
    EMOTION_SETTINGS,
    VOICE_SAMPLES,
    generate_segment_audio,
    get_public_voice_groups,
    tts_manager,
)


logger = structlog.get_logger(__name__)
router = APIRouter(
    tags=["voices"],
    dependencies=[Depends(verify_secret_key)],
)


@router.post("/assign_voices", response_model=Dict[str, Any])
async def assign_voices(
    request: SynthesizeRequest,
    languages: Optional[List[str]] = Query(None),
    user_tier: Literal["free", "vip"] = Header("free", alias="X-User-Tier"),
):
    try:
        logger.info(
            "Assign voices request received",
            user_tier=user_tier,
            languages=languages,
            script_segments=len(request.script),
            text_characters=sum(len(segment.text) for segment in request.script),
        )
        script = [
            segment.model_dump(exclude_none=True)
            for segment in request.script
        ]
        enriched_script = tts_manager.assign_voices_to_script(
            script,
            user_tier=user_tier,
            allowed_languages=normalize_languages(languages),
        )
        characters = list({
            segment.get("character", "")
            for segment in enriched_script
            if segment.get("character")
        })
        logger.info(
            "Voices assigned",
            script_segments=len(enriched_script),
            characters_count=len(characters),
        )
        return {
            "message": "Voices assigned successfully",
            "script": enriched_script,
            "metadata": {
                "segments_count": len(enriched_script),
                "characters": characters,
            },
        }
    except ValueError as exc:
        logger.warning("Voice assignment validation failed", error=str(exc))
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Voice assignment failed",
            error_type=type(exc).__name__,
        )
        raise internal_error("voice_assignment_failed") from exc


@router.post("/review", response_class=FileResponse)
async def review_voice(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    elevenlabs_api_key: Optional[str] = Header(
        None,
        alias="X-ElevenLabs-API-Key",
    ),
    user_tier: Literal["free", "vip"] = Header("free", alias="X-User-Tier"),
):
    elevenlabs_key = (
        elevenlabs_api_key or get_settings().elevenlabs_api_key
    )
    try:
        provider_name, _ = tts_manager.resolve_voice(
            {"voice_id": request.voice_id}
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    missing_providers = tts_manager.get_missing_provider_credentials(
        {provider_name},
        elevenlabs_key=elevenlabs_key,
    )
    if missing_providers:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "tts_provider_not_configured",
                "providers": missing_providers,
            },
        )

    temp_dir = tempfile.mkdtemp(prefix="dramaflow_review_")
    try:
        logger.info(
            "Review request",
            text_characters=len(request.text),
            voice=request.voice_id,
            provider=provider_name,
        )
        segment = {
            "type": "dialogue",
            "text": request.text[:30],
            "character": "Preview",
            "voice_id": request.voice_id,
            "pacing": request.pacing,
            "emotion": request.emotion,
        }
        await generate_segment_audio(
            segment=segment,
            output_dir=temp_dir,
            elevenlabs_api_key=elevenlabs_key,
            user_tier=user_tier,
        )
        files = list(Path(temp_dir).glob("*.mp3"))
        if not files:
            raise RuntimeError("Audio generation failed (no file produced)")

        background_tasks.add_task(cleanup_temp_directory, temp_dir)
        return FileResponse(
            path=files[0],
            media_type="audio/mpeg",
            filename="preview.mp3",
        )
    except HTTPException:
        cleanup_temp_directory(temp_dir)
        raise
    except Exception as exc:
        cleanup_temp_directory(temp_dir)
        logger.exception(
            "Review voice generation failed",
            voice=request.voice_id,
            provider=provider_name,
            error_type=type(exc).__name__,
        )
        raise internal_error("voice_review_failed") from exc


@router.get("/voices", response_model=dict)
async def get_available_voices(
    languages: Optional[List[str]] = Query(None),
):
    normalized_languages = normalize_languages(languages)
    return {
        "voice_map": get_public_voice_groups(languages=normalized_languages),
        "emotion_settings": EMOTION_SETTINGS,
        "samples": VOICE_SAMPLES,
    }

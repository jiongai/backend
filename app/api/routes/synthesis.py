"""Full audio-drama synthesis route."""

import tempfile
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from app.api.dependencies import verify_secret_key
from app.api.errors import internal_error
from app.api.schemas import DramaResponse, SynthesizeRequest
from app.api.utils import cleanup_temp_directory
from app.core.settings import get_settings
from app.services.audio_engine import tts_manager
from app.services.synthesizer import synthesize_drama


logger = structlog.get_logger(__name__)
router = APIRouter(
    tags=["synthesis"],
    dependencies=[Depends(verify_secret_key)],
)


@router.post("/synthesize", response_model=DramaResponse)
async def synthesize_audio_drama(
    request: SynthesizeRequest,
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
    script = [
        segment.model_dump(exclude_none=True)
        for segment in request.script
    ]

    if request.limit == 0:
        logger.info("Limit=0, skipping synthesis")
        return DramaResponse(
            message="Synthesis skipped (limit=0)",
            segments_count=0,
            audio_url=None,
            srt_url=None,
            timeline=None,
        )
    if request.limit is not None:
        script = script[:request.limit]

    try:
        prepared_script = tts_manager.prepare_script(
            script,
            user_tier=user_tier,
        )
        required_providers = tts_manager.get_required_providers(prepared_script)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    missing_providers = tts_manager.get_missing_provider_credentials(
        required_providers,
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

    temp_dir = tempfile.mkdtemp(prefix="dramaflow_synth_")
    try:
        logger.info(
            "Synthesize request received",
            user_tier=user_tier,
            script_segments=len(prepared_script),
            providers=sorted(required_providers),
        )
        result = await synthesize_drama(
            script=prepared_script,
            temp_dir=temp_dir,
            elevenlabs_key=elevenlabs_key,
            user_tier=user_tier,
        )
        background_tasks.add_task(cleanup_temp_directory, temp_dir)
        return DramaResponse(
            message="Synthesis successful",
            segments_count=len(prepared_script),
            audio_url=result["audio_url"],
            srt_url=result["srt_url"],
            timeline=result.get("timeline"),
        )
    except HTTPException:
        cleanup_temp_directory(temp_dir)
        raise
    except Exception as exc:
        cleanup_temp_directory(temp_dir)
        logger.exception(
            "Synthesize audio drama failed",
            user_tier=user_tier,
            script_segments=len(prepared_script),
            error_type=type(exc).__name__,
        )
        raise internal_error("synthesis_failed") from exc

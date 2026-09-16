"""Cloud artifact lifecycle routes."""

import asyncio
from typing import Dict

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import verify_secret_key
from app.api.errors import internal_error
from app.api.schemas import (
    DeleteFilesRequest,
    MoveFilesToTempRequest,
    SaveFilesRequest,
)
from app.services.storage import r2_storage


logger = structlog.get_logger(__name__)
router = APIRouter(
    tags=["storage"],
    dependencies=[Depends(verify_secret_key)],
)


@router.post("/save_files", response_model=Dict[str, str])
async def save_files(request: SaveFilesRequest):
    try:
        r2_storage.validate_artifact_pair(
            request.audio_url,
            request.srt_url,
            allowed_folders={"temp", "saved"},
        )
        new_audio_url = await asyncio.to_thread(
            r2_storage.save_file_as_new,
            request.audio_url,
        )
        new_srt_url = await asyncio.to_thread(
            r2_storage.save_file_as_new,
            request.srt_url,
        )
        logger.info("Files saved and isolated")
        return {"audio_url": new_audio_url, "srt_url": new_srt_url}
    except ValueError as exc:
        logger.warning("Save files validation failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Save files failed", error_type=type(exc).__name__)
        raise internal_error("save_files_failed") from exc


@router.post("/del_files")
async def delete_files(request: DeleteFilesRequest):
    results = {}
    try:
        if request.audio_url and request.srt_url:
            r2_storage.validate_artifact_pair(
                request.audio_url,
                request.srt_url,
                allowed_folders={"temp", "saved"},
            )
        elif request.audio_url:
            r2_storage.parse_public_url(
                request.audio_url,
                expected_extension=".mp3",
                allowed_folders={"temp", "saved"},
            )
        elif request.srt_url:
            r2_storage.parse_public_url(
                request.srt_url,
                expected_extension=".srt",
                allowed_folders={"temp", "saved"},
            )
        else:
            raise ValueError("At least one artifact URL is required")

        if request.audio_url:
            results["audio"] = await asyncio.to_thread(
                r2_storage.delete_file,
                request.audio_url,
            )
        if request.srt_url:
            results["srt"] = await asyncio.to_thread(
                r2_storage.delete_file,
                request.srt_url,
            )
        logger.info("Delete files request processed", results=results)
        return {"message": "Files deletion processed", "details": results}
    except ValueError as exc:
        logger.warning("Delete files validation failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Delete files failed", error_type=type(exc).__name__)
        raise internal_error("delete_files_failed") from exc


@router.post("/move_files_to_temp", response_model=Dict[str, str])
async def move_files_to_temp(request: MoveFilesToTempRequest):
    try:
        r2_storage.validate_artifact_pair(
            request.audio_url,
            request.srt_url,
            allowed_folders={"saved"},
        )
        new_audio_url = await asyncio.to_thread(
            r2_storage.move_file_to_temp,
            request.audio_url,
        )
        new_srt_url = await asyncio.to_thread(
            r2_storage.move_file_to_temp,
            request.srt_url,
        )
        logger.info("Files moved to temp")
        return {"audio_url": new_audio_url, "srt_url": new_srt_url}
    except ValueError as exc:
        logger.warning("Move files validation failed", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Move files failed", error_type=type(exc).__name__)
        raise internal_error("move_files_failed") from exc

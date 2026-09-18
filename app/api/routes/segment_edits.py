"""Signed-in account edit operations. Account identity is supplied by the authenticated gateway."""
import asyncio
import tempfile
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.dependencies import verify_secret_key
from app.api.errors import internal_error
from app.api.schemas import EditableDramaResponse
from app.models import ScriptSegment
from app.services import segment_edits

router = APIRouter(tags=["synthesis"], dependencies=[Depends(verify_secret_key)])


def owner_id(x_user_id: UUID = Header()):
    return str(x_user_id)


class RegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edit_id: UUID
    segment_id: UUID
    segment: ScriptSegment


class AcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edit_id: UUID
    candidate_id: UUID


@router.post("/plan_segment_edit")
async def plan(request: RegenerateRequest, owner: str = Depends(owner_id), x_character_limit: int = Header(2000, ge=1, le=100_000),
               x_user_tier: Literal["free", "vip"] = Header("free")):
    try:
        _, _, requires_generation = await segment_edits.prepare_regeneration(owner, str(request.edit_id), str(request.segment_id),
            request.segment.model_dump(exclude_none=True), x_character_limit, x_user_tier)
        return {"requires_generation": requires_generation}
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_error("segment_planning_failed") from exc


@router.post("/regenerate_segment")
async def regenerate(request: RegenerateRequest, owner: str = Depends(owner_id), x_character_limit: int = Header(2000, ge=1, le=100_000),
                     x_user_tier: Literal["free", "vip"] = Header("free"), x_audio_generation_reserved: bool = Header(False)):
    try:
        with tempfile.TemporaryDirectory(prefix="dramaflow_edit_") as directory:
            return await segment_edits.regenerate(owner, str(request.edit_id), str(request.segment_id),
                                                   request.segment.model_dump(exclude_none=True), directory, x_character_limit, x_user_tier, x_audio_generation_reserved)
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_error("segment_regeneration_failed") from exc


@router.post("/accept_segment", response_model=EditableDramaResponse)
async def accept(request: AcceptRequest, owner: str = Depends(owner_id)):
    try:
        with tempfile.TemporaryDirectory(prefix="dramaflow_merge_") as directory:
            return await asyncio.to_thread(segment_edits.accept, owner, str(request.edit_id), str(request.candidate_id), directory)
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_error("segment_merge_failed") from exc

"""Pro-only edit operations. Account identity is supplied by the authenticated gateway."""
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


def owner_id(x_user_id: UUID = Header(), x_user_tier: Literal["free", "vip"] = Header("free")):
    if x_user_tier != "vip":
        raise HTTPException(403, "Dialogue regeneration requires Pro or Max")
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


@router.post("/regenerate_segment")
async def regenerate(request: RegenerateRequest, owner: str = Depends(owner_id), x_character_limit: int = Header(2000, ge=1, le=100_000)):
    try:
        with tempfile.TemporaryDirectory(prefix="dramaflow_edit_") as directory:
            return await segment_edits.regenerate(owner, str(request.edit_id), str(request.segment_id),
                                                   request.segment.model_dump(exclude_none=True), directory, x_character_limit)
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

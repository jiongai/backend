"""Request and response models shared by API routers."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ScriptSegment


class SynthesizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    script: List[ScriptSegment] = Field(
        ...,
        min_length=1,
        max_length=1_000,
        description="Structured script segments to synthesize",
    )
    limit: Optional[int] = Field(
        None,
        ge=0,
        description="Number of segments to generate. 0 = none. None = all.",
    )


class DramaResponse(BaseModel):
    message: str
    segments_count: int
    audio_duration_ms: Optional[int] = None
    audio_url: Optional[str] = None
    srt_url: Optional[str] = None
    timeline: Optional[List[Dict[str, Any]]] = None


class EditableDramaResponse(DramaResponse):
    edit_id: str
    segment_ids: List[str]


class ReviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=100)
    voice_id: str = Field(..., min_length=1)
    pacing: float = Field(1.0, ge=0.25, le=4.0)
    emotion: str = Field("neutral", min_length=1)


class SaveFilesRequest(BaseModel):
    audio_url: str
    srt_url: str


class DeleteFilesRequest(BaseModel):
    audio_url: Optional[str] = None
    srt_url: Optional[str] = None


class MoveFilesToTempRequest(BaseModel):
    audio_url: str
    srt_url: str

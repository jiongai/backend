"""Application router composition."""

from fastapi import APIRouter

from app.api.routes import storage, synthesis, system, voices, segment_edits


api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(voices.router)
api_router.include_router(synthesis.router)
api_router.include_router(storage.router)

api_router.include_router(segment_edits.router)

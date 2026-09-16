"""Service metadata and health routes."""

from fastapi import APIRouter

from app.core.settings import get_settings


router = APIRouter(tags=["system"])


@router.get("/")
async def root():
    return {
        "service": "DramaFlow API",
        "status": "running",
        "version": "1.0.0",
    }


@router.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "openrouter_configured": bool(settings.openrouter_api_key),
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
    }

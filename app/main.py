"""DramaFlow FastAPI application factory and compatibility exports."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from asgi_correlation_id import CorrelationIdMiddleware

from app.core.logging import configure_logging
from app.core.runtime import configure_ffmpeg
from app.core.settings import get_settings


# Bootstrap before importing routers, which initialize provider singletons and
# import pydub through the post-production service.
configure_logging()
configure_ffmpeg()

from app.api.dependencies import verify_secret_key
from app.api.errors import internal_error, unhandled_exception_handler
from app.api.router import api_router
from app.api.schemas import (
    DeleteFilesRequest,
    DramaResponse,
    MoveFilesToTempRequest,
    ReviewRequest,
    SaveFilesRequest,
    SynthesizeRequest,
)
from app.api.utils import cleanup_temp_directory
from app.services.synthesizer import synthesize_drama


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="DramaFlow API",
        description="Convert structured scripts into immersive audio dramas",
        version="1.0.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(CorrelationIdMiddleware)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.include_router(api_router)
    return application


app = create_app()


__all__ = [
    "DeleteFilesRequest",
    "DramaResponse",
    "MoveFilesToTempRequest",
    "ReviewRequest",
    "SaveFilesRequest",
    "SynthesizeRequest",
    "app",
    "cleanup_temp_directory",
    "create_app",
    "internal_error",
    "synthesize_drama",
    "unhandled_exception_handler",
    "verify_secret_key",
]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=get_settings().port,
        reload=True,
    )

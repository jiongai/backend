"""Runtime bootstrap helpers that must run before service imports."""

import os
from pathlib import Path

import structlog

from app.core.settings import Settings, get_settings


logger = structlog.get_logger(__name__)


def configure_ffmpeg(settings: Settings | None = None) -> None:
    """Configure the bundled ffmpeg binary in serverless environments."""
    settings = settings or get_settings()
    if not settings.aws_lambda_function_name:
        logger.info("Running locally or on Railway, using system ffmpeg")
        return

    vendor_binary = Path(__file__).resolve().parents[2] / "vendor" / "ffmpeg"
    if not vendor_binary.exists():
        logger.warning("ffmpeg not found in vendor directory")
        return

    binary_path = str(vendor_binary)
    os.environ["FFMPEG_BINARY"] = binary_path
    os.environ["FFPROBE_BINARY"] = binary_path

    # Import only after the environment is configured.
    from pydub import AudioSegment

    AudioSegment.converter = binary_path
    AudioSegment.ffmpeg = binary_path
    AudioSegment.ffprobe = binary_path
    logger.info("Configured bundled ffmpeg", path=binary_path)

"""Small HTTP-layer utilities."""

import shutil
from pathlib import Path

import structlog


logger = structlog.get_logger(__name__)


def cleanup_temp_directory(directory: str) -> None:
    try:
        path = Path(directory)
        if path.exists():
            shutil.rmtree(path)
            logger.info("Cleaned up temp directory")
    except Exception as exc:
        logger.warning(
            "Failed to cleanup temp directory",
            error_type=type(exc).__name__,
        )

"""Shared FastAPI dependencies."""

import secrets
from typing import Optional

import structlog
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.core.settings import get_settings


logger = structlog.get_logger(__name__)
api_key_header = APIKeyHeader(name="X-Access-Secret", auto_error=False)
PLACEHOLDER_SECRETS = {"your_api_access_secret_here", "changeme", "change-me"}


async def verify_secret_key(
    header_secret: Optional[str] = Security(api_key_header),
) -> None:
    """Verify the configured shared access secret."""
    settings = get_settings()
    correct_secret = settings.api_access_secret

    if not correct_secret or correct_secret.lower() in PLACEHOLDER_SECRETS:
        if settings.is_production:
            logger.error(
                "API authentication is not configured",
                environment=settings.environment,
            )
            raise HTTPException(
                status_code=503,
                detail={"code": "authentication_not_configured"},
            )
        logger.warning("API authentication disabled in non-production environment")
        return None

    if not header_secret:
        logger.warning("API request rejected: missing access secret")
        raise HTTPException(
            status_code=401,
            detail={"code": "missing_access_secret"},
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not secrets.compare_digest(header_secret, correct_secret):
        logger.warning("API request rejected: invalid access secret")
        raise HTTPException(
            status_code=403,
            detail={"code": "invalid_access_secret"},
        )
    return None


def normalize_languages(languages: Optional[list[str]]) -> list[str]:
    """Normalize supported language aliases and preserve caller order."""
    if not languages:
        return ["en"]

    normalized: list[str] = []
    for language in languages:
        candidate = language.lower()
        if candidate in {"cn", "zh-cn", "zh-tw"}:
            candidate = "zh"
        elif candidate.startswith("en"):
            candidate = "en"
        if candidate not in normalized:
            normalized.append(candidate)
    return normalized

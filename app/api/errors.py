"""Stable API error responses and global exception handling."""

import structlog
from asgi_correlation_id import correlation_id
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


logger = structlog.get_logger(__name__)


def internal_error(code: str) -> HTTPException:
    """Build a stable 500 response without leaking provider or local details."""
    return HTTPException(
        status_code=500,
        detail={
            "code": code,
            "message": "The request could not be completed",
            "request_id": correlation_id.get(),
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = correlation_id.get()
    logger.exception(
        "Unhandled server exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_server_error",
                "message": "An unexpected server error occurred",
                "request_id": request_id,
            }
        },
    )

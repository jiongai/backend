import logging
import sys
from typing import Any

import structlog
from asgi_correlation_id import correlation_id

from app.core.settings import get_settings


SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
MAX_LOG_STRING_LENGTH = 500
def _sanitize_log_value(key: str, value: Any) -> Any:
    """Redact credentials and bound arbitrary log payload sizes."""
    normalized_key = key.lower()
    if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"

    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_log_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        sanitized = [
            _sanitize_log_value(normalized_key, item)
            for item in value[:20]
        ]
        if len(value) > 20:
            sanitized.append(f"[{len(value) - 20} more items]")
        return sanitized
    if isinstance(value, str):
        sanitized = value
        for secret_value in get_settings().sensitive_values:
            sanitized = sanitized.replace(secret_value, "[REDACTED]")
        if len(sanitized) > MAX_LOG_STRING_LENGTH:
            return f"{sanitized[:MAX_LOG_STRING_LENGTH]}...[truncated]"
        return sanitized
    return value


def redact_sensitive_data(logger, log_method, event_dict):
    """Structlog processor that prevents common credentials reaching output."""
    return {
        key: _sanitize_log_value(str(key), value)
        for key, value in event_dict.items()
    }


def control_exception_details(logger, log_method, event_dict):
    """Suppress stack traces by default in production logs."""
    if not get_settings().include_stacktraces:
        event_dict.pop("exc_info", None)
        event_dict.pop("stack", None)
    return event_dict


def configure_logging():
    """
    Configure structured logging for the application.
    """
    
    # Processors for structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        redact_sensitive_data,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        control_exception_details,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_sensitive_data,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add correlation ID to logs
    def add_correlation(logger, log_method, event_dict):
        request_id = correlation_id.get()
        if request_id:
            event_dict["request_id"] = request_id
        return event_dict
    
    processors.insert(1, add_correlation)

    settings = get_settings()
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.use_json_logs
        else structlog.dev.ConsoleRenderer()
    )
    
    # Final processor chain
    processors.append(renderer)

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure Standard Library Logging to define format and level
    log_level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

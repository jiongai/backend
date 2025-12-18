import logging
import sys
import structlog
from asgi_correlation_id import correlation_id

def configure_logging():
    """
    Configure structured logging for the application.
    """
    
    # Processors for structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add correlation ID to logs
    def add_correlation(logger, log_method, event_dict):
        request_id = correlation_id.get()
        if request_id:
            event_dict["request_id"] = request_id
        return event_dict
    
    processors.insert(1, add_correlation)

    # Renderer selection (JSON for Prod, Console for Dev)
    # Ideally should be env var controlled. For now default to ConsoleRenderer for dev friendliness
    # but structured enough.
    # If production, you might want JSONRenderer.
    
    # Using ConsoleRenderer for now as it's easier to read in development
    # Change to JSONRenderer for production deployment 
    renderer = structlog.dev.ConsoleRenderer() 
    
    # Final processor chain
    processors.append(renderer)

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure Standard Library Logging to define format and level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

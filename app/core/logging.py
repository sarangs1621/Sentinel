import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

_configured = False


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for ingestion by log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    """Configure the root logger's level and output format.

    Called once at process startup (FastAPI app and Celery workers/beat) so that
    `logging.getLogger(__name__)` calls throughout the codebase - e.g. the Redis
    fail-open warnings in `app.services.cache` and `app.core.redis` - are emitted
    with a consistent, timestamped format at the configured level.
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(handler)

    _configured = True

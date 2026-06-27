import json
import logging

import pytest

from app.core import logging as app_logging
from app.core.config import settings
from app.core.logging import JsonFormatter, configure_logging


def test_json_formatter_renders_expected_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.services.cache",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="Redis unavailable: %s",
        args=("connection refused",),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "WARNING"
    assert payload["logger"] == "app.services.cache"
    assert payload["message"] == "Redis unavailable: connection refused"
    assert "timestamp" in payload


def test_configure_logging_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    root_logger = logging.getLogger()
    monkeypatch.setattr(app_logging, "_configured", False)
    handlers_before = list(root_logger.handlers)

    try:
        configure_logging()
        configure_logging()
        assert len(root_logger.handlers) == len(handlers_before) + 1
    finally:
        root_logger.handlers = handlers_before


def test_configure_logging_uses_json_formatter_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    root_logger = logging.getLogger()
    monkeypatch.setattr(app_logging, "_configured", False)
    monkeypatch.setattr(settings, "LOG_FORMAT", "json")
    handlers_before = list(root_logger.handlers)

    try:
        configure_logging()
        assert isinstance(root_logger.handlers[-1].formatter, JsonFormatter)
    finally:
        root_logger.handlers = handlers_before

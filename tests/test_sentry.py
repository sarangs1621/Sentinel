from typing import Any

import pytest

from app.core import sentry as app_sentry
from app.core.config import settings


def test_configure_sentry_is_noop_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_sentry, "_configured", False)
    monkeypatch.setattr(settings, "SENTRY_DSN", None)

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(app_sentry.sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    app_sentry.configure_sentry()

    assert calls == []
    assert app_sentry._configured is False


def test_configure_sentry_initializes_when_dsn_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_sentry, "_configured", False)
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://example@sentry.io/1")
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.25)

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(app_sentry.sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    app_sentry.configure_sentry()

    assert calls == [
        {
            "dsn": "https://example@sentry.io/1",
            "environment": settings.ENVIRONMENT,
            "traces_sample_rate": 0.25,
        }
    ]
    assert app_sentry._configured is True


def test_configure_sentry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_sentry, "_configured", True)
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://example@sentry.io/1")

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(app_sentry.sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))

    app_sentry.configure_sentry()

    assert calls == []

import sentry_sdk

from app.core.config import settings

_configured = False


def configure_sentry() -> None:
    """Initialize Sentry error tracking if `SENTRY_DSN` is configured.

    No-op when `SENTRY_DSN` is unset, which is the default for local
    development and the test suite.
    """
    global _configured
    if _configured or not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )
    _configured = True

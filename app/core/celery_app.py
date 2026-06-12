from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.sentry import configure_sentry

configure_logging()
configure_sentry()

celery_app = Celery(
    "sentinel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "dispatch-due-checks": {
            "task": "app.workers.tasks.dispatch_due_checks",
            "schedule": settings.CHECK_DISPATCH_INTERVAL_SECONDS,
        },
        "dispatch-pending-notifications": {
            "task": "app.workers.tasks.dispatch_pending_notifications",
            "schedule": settings.CHECK_DISPATCH_INTERVAL_SECONDS,
        },
        "aggregate-daily-metrics": {
            "task": "app.workers.tasks.dispatch_metric_aggregation",
            "schedule": settings.METRICS_AGGREGATION_INTERVAL_SECONDS,
        },
    },
)

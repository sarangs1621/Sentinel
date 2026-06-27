import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.models.audit_log import AuditLog
from app.models.enums import NotificationChannel, NotificationStatus
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.incident import IncidentRepository
from app.repositories.monitor import MonitorRepository
from app.repositories.notification import NotificationRepository
from app.schemas.check import CheckCreate
from app.services.cache import CacheService
from app.services.check import CheckService
from app.services.metrics import MetricsService
from app.workers.checkers import perform_health_check
from app.workers.db import worker_redis, worker_session
from app.workers.notifier import deliver_email, deliver_webhook

NOTIFICATION_MAX_ATTEMPTS = 5


@celery_app.task(name="app.workers.tasks.dispatch_due_checks")
def dispatch_due_checks() -> int:
    """Periodic task: queue a `perform_check` for every monitor that's due."""
    monitor_ids = asyncio.run(_get_due_monitor_ids())
    for monitor_id in monitor_ids:
        perform_check.delay(str(monitor_id))
    return len(monitor_ids)


@celery_app.task(name="app.workers.tasks.perform_check")
def perform_check(monitor_id: str) -> None:
    """Run a single health check for a monitor and record the result."""
    asyncio.run(_perform_check(uuid.UUID(monitor_id)))


async def _get_due_monitor_ids(session: AsyncSession | None = None) -> list[uuid.UUID]:
    if session is not None:
        monitors = await MonitorRepository(session).list_due_for_check(datetime.now(UTC))
        return [monitor.id for monitor in monitors]

    async with worker_session() as worker_db:
        monitors = await MonitorRepository(worker_db).list_due_for_check(datetime.now(UTC))
        return [monitor.id for monitor in monitors]


async def _perform_check(monitor_id: uuid.UUID, session: AsyncSession | None = None) -> None:
    if session is not None:
        await _run_check(session, monitor_id)
        return

    async with worker_session() as worker_db, worker_redis() as redis:
        await _run_check(worker_db, monitor_id, CacheService(redis))


async def _run_check(session: AsyncSession, monitor_id: uuid.UUID, cache: CacheService | None = None) -> None:
    import logging
    logger = logging.getLogger(__name__)

    monitor = await MonitorRepository(session).get_by_id(monitor_id)
    if monitor is None or monitor.deleted_at is not None or not monitor.is_active:
        return

    logger.info(f"Monitor picked for execution: {monitor.name} ({monitor.id})")
    logger.info(f"Health check started for {monitor.name} to {monitor.target}")

    outcome = await perform_health_check(monitor.monitor_type, monitor.target)
    
    logger.info(f"Health check completed for {monitor.name}: status={outcome.status}, latency={outcome.response_time_ms}ms")

    await CheckService(session, cache).record_check(
        monitor.workspace_id,
        monitor.id,
        CheckCreate(
            status=outcome.status,
            response_time_ms=outcome.response_time_ms,
            error_message=outcome.error_message,
        ),
    )

    logger.info(f"Monitor status updated for {monitor.name} to {outcome.status}")
    logger.info(f"Next check scheduled for {monitor.name} in {monitor.check_interval_seconds} seconds")


@celery_app.task(name="app.workers.tasks.dispatch_pending_notifications")
def dispatch_pending_notifications() -> int:
    """Periodic task: queue a `deliver_notification` for every notification due for delivery."""
    notification_ids = asyncio.run(_get_due_notification_ids())
    for notification_id in notification_ids:
        deliver_notification.delay(str(notification_id))
    return len(notification_ids)


@celery_app.task(name="app.workers.tasks.deliver_notification")
def deliver_notification(notification_id: str) -> None:
    """Attempt webhook delivery for a single notification and record the outcome."""
    asyncio.run(_deliver_notification(uuid.UUID(notification_id)))


async def _get_due_notification_ids(session: AsyncSession | None = None) -> list[uuid.UUID]:
    if session is not None:
        notifications = await NotificationRepository(session).list_due_for_delivery(NOTIFICATION_MAX_ATTEMPTS)
        return [notification.id for notification in notifications]

    async with worker_session() as worker_db:
        notifications = await NotificationRepository(worker_db).list_due_for_delivery(NOTIFICATION_MAX_ATTEMPTS)
        return [notification.id for notification in notifications]


async def _deliver_notification(notification_id: uuid.UUID, session: AsyncSession | None = None) -> None:
    if session is not None:
        await _run_delivery(session, notification_id)
        return

    async with worker_session() as worker_db:
        await _run_delivery(worker_db, notification_id)


async def _run_delivery(session: AsyncSession, notification_id: uuid.UUID) -> None:
    notification = await NotificationRepository(session).get_by_id(notification_id)
    if notification is None or notification.status == NotificationStatus.SENT:
        return

    incident = await IncidentRepository(session).get_by_id(notification.incident_id)
    rule = await AlertRuleRepository(session).get_by_id(notification.alert_rule_id)
    if incident is None or rule is None or not rule.is_enabled:
        return

    logger.info("Delivering notification ID %s", notification_id)

    if rule.channel_type == NotificationChannel.EMAIL:
        logger.info("Calling email provider for target %s", rule.target)
        result = await deliver_email(rule.target, incident, notification.event_type)
    else:
        logger.info("Calling webhook provider for target %s", rule.target)
        result = await deliver_webhook(rule.target, incident, notification.event_type)

    if result.success:
        logger.info("%s sent successfully to %s", rule.channel_type.value.capitalize(), rule.target)
    else:
        logger.error("%s delivery failed for %s: %s", rule.channel_type.value.capitalize(), rule.target, result.error_message)

    notification.attempts += 1
    notification.last_attempted_at = datetime.now(UTC)
    notification.response_status_code = result.status_code
    notification.error_message = result.error_message
    notification.status = NotificationStatus.SENT if result.success else NotificationStatus.FAILED

    action = "notification.sent" if result.success else "notification.failed"
    AuditLogRepository(session).add(
        AuditLog(
            workspace_id=notification.workspace_id,
            user_id=None,
            action=action,
            entity_type="notification",
            entity_id=notification.id,
            old_values=None,
            new_values={
                "event_type": notification.event_type.value,
                "channel_type": rule.channel_type.value,
                "attempts": notification.attempts,
                **({"error": result.error_message} if not result.success else {}),
            },
        )
    )

    await session.commit()


@celery_app.task(name="app.workers.tasks.dispatch_metric_aggregation")
def dispatch_metric_aggregation() -> int:
    """Periodic task: aggregate yesterday's (UTC) MetricSnapshot for every
    active, non-deleted monitor."""
    monitor_ids = asyncio.run(_get_aggregation_monitor_ids())
    period_start = _yesterday_utc_midnight()
    for monitor_id in monitor_ids:
        aggregate_monitor_metrics.delay(str(monitor_id), period_start.isoformat())
    return len(monitor_ids)


@celery_app.task(name="app.workers.tasks.aggregate_monitor_metrics")
def aggregate_monitor_metrics(monitor_id: str, period_start_iso: str) -> None:
    """Aggregate and upsert the MetricSnapshot for a single monitor/day."""
    asyncio.run(_aggregate_monitor_metrics(uuid.UUID(monitor_id), datetime.fromisoformat(period_start_iso)))


def _yesterday_utc_midnight(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_midnight - timedelta(days=1)


async def _get_aggregation_monitor_ids(session: AsyncSession | None = None) -> list[uuid.UUID]:
    if session is not None:
        monitors = await MonitorRepository(session).list_all_active()
        return [monitor.id for monitor in monitors]

    async with worker_session() as worker_db:
        monitors = await MonitorRepository(worker_db).list_all_active()
        return [monitor.id for monitor in monitors]


async def _aggregate_monitor_metrics(
    monitor_id: uuid.UUID, period_start: datetime, session: AsyncSession | None = None
) -> None:
    if session is not None:
        await MetricsService(session).aggregate_daily_snapshot(monitor_id, period_start)
        return

    async with worker_session() as worker_db, worker_redis() as redis:
        await MetricsService(worker_db, CacheService(redis)).aggregate_daily_snapshot(monitor_id, period_start)

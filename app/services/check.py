import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditLog
from app.models.check import Check
from app.models.enums import CheckStatus, IncidentSeverity, IncidentStatus, MonitorStatus, NotificationEvent
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.repositories.audit_log import AuditLogRepository
from app.repositories.check import CheckRepository
from app.repositories.incident import IncidentRepository
from app.repositories.monitor import MonitorRepository
from app.schemas.check import CheckCreate, CheckRead
from app.services.cache import CacheService
from app.services.notification import NotificationService

_DEFAULT_INCIDENT_SEVERITY = IncidentSeverity.MAJOR


class CheckService:
    def __init__(self, session: AsyncSession, cache: CacheService | None = None) -> None:
        self.session = session
        self.checks = CheckRepository(session)
        self.incidents = IncidentRepository(session)
        self.monitors = MonitorRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.notifications = NotificationService(session)
        self.cache = cache if cache is not None else CacheService()

    @staticmethod
    def to_read(check: Check) -> CheckRead:
        return CheckRead.model_validate(check)

    async def list_checks(self, workspace_id: uuid.UUID, monitor_id: uuid.UUID) -> list[CheckRead]:
        monitor = await self.monitors.get_active_by_id(workspace_id, monitor_id)
        if monitor is None:
            raise NotFoundError("Monitor not found.")

        checks = await self.checks.list_by_monitor(monitor_id)
        return [self.to_read(c) for c in checks]

    async def record_check(self, workspace_id: uuid.UUID, monitor_id: uuid.UUID, data: CheckCreate) -> CheckRead:
        monitor = await self.monitors.get_active_by_id(workspace_id, monitor_id)
        if monitor is None:
            raise NotFoundError("Monitor not found.")

        now = datetime.now(UTC)

        check = Check(
            monitor_id=monitor.id,
            status=data.status,
            response_time_ms=data.response_time_ms,
            error_message=data.error_message,
        )
        self.checks.add(check)
        monitor.last_checked_at = now

        if data.status == CheckStatus.SUCCESS:
            monitor.consecutive_failures = 0
            monitor.status = MonitorStatus.UP
            await self.cache.reset_failure_count(monitor.id)
            await self._resolve_open_incident(monitor.id, now)
        else:
            monitor.consecutive_failures = await self.cache.increment_failure_count(
                monitor.id, monitor.consecutive_failures
            )
            if monitor.consecutive_failures >= monitor.failure_threshold:
                monitor.status = MonitorStatus.DOWN
                await self._open_incident_if_needed(workspace_id, monitor)

        await self.cache.set_monitor_status(monitor.id, monitor.status, now, data.response_time_ms)

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(check)
        return self.to_read(check)

    async def _open_incident_if_needed(self, workspace_id: uuid.UUID, monitor: Monitor) -> None:
        existing = await self.incidents.get_open_for_monitor(monitor.id)
        if existing is not None:
            return

        incident = Incident(
            workspace_id=workspace_id,
            monitor_id=monitor.id,
            title=f"{monitor.name} is down",
            status=IncidentStatus.OPEN,
            severity=_DEFAULT_INCIDENT_SEVERITY,
        )
        self.incidents.add(incident)
        await self.session.flush()

        self.audit_logs.add(
            AuditLog(
                workspace_id=workspace_id,
                user_id=None,
                action="incident.created",
                entity_type="incident",
                entity_id=incident.id,
                old_values=None,
                new_values={
                    "monitor_id": str(monitor.id),
                    "title": incident.title,
                    "status": incident.status.value,
                    "severity": incident.severity.value,
                },
            )
        )
        await self.notifications.evaluate_incident_event(incident, NotificationEvent.INCIDENT_OPENED)
        await self.cache.invalidate_dashboard(workspace_id)

    async def _resolve_open_incident(self, monitor_id: uuid.UUID, now: datetime) -> None:
        incident = await self.incidents.get_open_for_monitor(monitor_id)
        if incident is None:
            return

        old_status = incident.status.value
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = now

        self.audit_logs.add(
            AuditLog(
                workspace_id=incident.workspace_id,
                user_id=None,
                action="incident.resolved",
                entity_type="incident",
                entity_id=incident.id,
                old_values={"status": old_status},
                new_values={"status": "resolved", "reason": "monitor_recovered", "monitor_id": str(monitor_id)},
            )
        )
        await self.notifications.evaluate_incident_event(incident, NotificationEvent.INCIDENT_RESOLVED)
        await self.cache.invalidate_dashboard(incident.workspace_id)

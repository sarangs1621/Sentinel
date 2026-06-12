import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.enums import IncidentSeverity, NotificationEvent, NotificationStatus
from app.models.incident import Incident
from app.models.notification import Notification
from app.repositories.alert_rule import AlertRuleRepository
from app.repositories.notification import NotificationRepository
from app.schemas.notification import NotificationRead

_SEVERITY_RANK = {
    IncidentSeverity.MINOR: 1,
    IncidentSeverity.MAJOR: 2,
    IncidentSeverity.CRITICAL: 3,
}


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.alert_rules = AlertRuleRepository(session)
        self.notifications = NotificationRepository(session)

    @staticmethod
    def to_read(notification: Notification) -> NotificationRead:
        return NotificationRead.model_validate(notification)

    async def list_notifications(self, workspace_id: uuid.UUID) -> list[NotificationRead]:
        notifications = await self.notifications.list_by_workspace(workspace_id)
        return [self.to_read(n) for n in notifications]

    async def get_notification(self, workspace_id: uuid.UUID, notification_id: uuid.UUID) -> NotificationRead:
        notification = await self.notifications.get_by_id_in_workspace(workspace_id, notification_id)
        if notification is None:
            raise NotFoundError("Notification not found.")
        return self.to_read(notification)

    async def evaluate_incident_event(self, incident: Incident, event: NotificationEvent) -> None:
        """Queue a notification for `incident` for every enabled alert rule in
        the workspace whose `min_severity` (if any) the incident meets."""
        rules = await self.alert_rules.list_enabled_by_workspace(incident.workspace_id)

        for rule in rules:
            if (
                rule.min_severity is not None
                and _SEVERITY_RANK[incident.severity] < _SEVERITY_RANK[rule.min_severity]
            ):
                continue

            notification = Notification(
                workspace_id=incident.workspace_id,
                incident_id=incident.id,
                alert_rule_id=rule.id,
                event_type=event,
                status=NotificationStatus.PENDING,
            )
            self.notifications.add(notification)

        await self.session.flush()

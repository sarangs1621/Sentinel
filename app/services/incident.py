import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.enums import IncidentStatus, NotificationEvent
from app.models.incident import Incident
from app.models.user import User
from app.repositories.incident import IncidentRepository
from app.schemas.incident import IncidentRead, IncidentUpdate
from app.services.audit_log import AuditLogService, to_jsonable
from app.services.cache import CacheService
from app.services.notification import NotificationService


class IncidentService:
    def __init__(self, session: AsyncSession, cache: CacheService | None = None) -> None:
        self.session = session
        self.incidents = IncidentRepository(session)
        self.audit = AuditLogService(session)
        self.notifications = NotificationService(session)
        self.cache = cache if cache is not None else CacheService()

    @staticmethod
    def to_read(incident: Incident) -> IncidentRead:
        return IncidentRead.model_validate(incident)

    async def list_incidents(self, workspace_id: uuid.UUID) -> list[IncidentRead]:
        incidents = await self.incidents.list_by_workspace(workspace_id)
        return [self.to_read(i) for i in incidents]

    async def get_incident(self, workspace_id: uuid.UUID, incident_id: uuid.UUID) -> IncidentRead:
        incident = await self.incidents.get_by_id_in_workspace(workspace_id, incident_id)
        if incident is None:
            raise NotFoundError("Incident not found.")
        return self.to_read(incident)

    async def update_incident(
        self,
        workspace_id: uuid.UUID,
        incident_id: uuid.UUID,
        data: IncidentUpdate,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> IncidentRead:
        incident = await self.incidents.get_by_id_in_workspace(workspace_id, incident_id)
        if incident is None:
            raise NotFoundError("Incident not found.")

        if incident.status == IncidentStatus.RESOLVED:
            raise ConflictError("This incident is already resolved.")

        old_status = to_jsonable(incident.status)
        incident.status = data.status
        if data.status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(UTC)
            await self.audit.record(
                workspace_id,
                user.id,
                "incident.resolved",
                "incident",
                incident.id,
                {"status": old_status},
                {"status": "resolved", "reason": "manual"},
                ip_address,
                user_agent,
            )
            await self.notifications.evaluate_incident_event(incident, NotificationEvent.INCIDENT_RESOLVED)
            await self.cache.invalidate_dashboard(workspace_id)
        else:
            await self.audit.record(
                workspace_id,
                user.id,
                "incident.acknowledged",
                "incident",
                incident.id,
                {"status": old_status},
                {"status": "investigating"},
                ip_address,
                user_agent,
            )

        await self.session.commit()
        await self.session.refresh(incident)
        return self.to_read(incident)

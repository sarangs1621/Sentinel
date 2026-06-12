import uuid
from datetime import datetime

from sqlalchemy import func, or_, select

from app.models.enums import IncidentStatus
from app.models.incident import Incident
from app.repositories.base import BaseRepository

_OPEN_STATUSES = (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING)


class IncidentRepository(BaseRepository[Incident]):
    model = Incident

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[Incident]:
        result = await self.session.execute(
            select(Incident).where(Incident.workspace_id == workspace_id).order_by(Incident.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_in_workspace(self, workspace_id: uuid.UUID, incident_id: uuid.UUID) -> Incident | None:
        result = await self.session.execute(
            select(Incident).where(Incident.id == incident_id, Incident.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_open_for_monitor(self, monitor_id: uuid.UUID) -> Incident | None:
        result = await self.session.execute(
            select(Incident)
            .where(Incident.monitor_id == monitor_id, Incident.status.in_(_OPEN_STATUSES))
            .order_by(Incident.created_at.desc())
        )
        return result.scalars().first()

    async def list_overlapping(self, monitor_id: uuid.UUID, start: datetime, end: datetime) -> list[Incident]:
        """Incidents on this monitor whose `[created_at, resolved_at or now)`
        interval overlaps `[start, end)`."""
        result = await self.session.execute(
            select(Incident).where(
                Incident.monitor_id == monitor_id,
                Incident.created_at < end,
                or_(Incident.resolved_at.is_(None), Incident.resolved_at > start),
            )
        )
        return list(result.scalars().all())

    async def count_by_workspace_status(self, workspace_id: uuid.UUID) -> dict[IncidentStatus, int]:
        """Counts of incidents in the workspace grouped by status."""
        result = await self.session.execute(
            select(Incident.status, func.count())
            .where(Incident.workspace_id == workspace_id)
            .group_by(Incident.status)
        )
        return {status: count for status, count in result.all()}

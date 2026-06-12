import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.models.enums import MonitorStatus, MonitorType
from app.models.monitor import Monitor
from app.repositories.base import BaseRepository


class MonitorRepository(BaseRepository[Monitor]):
    model = Monitor

    async def get_active_by_id(self, workspace_id: uuid.UUID, monitor_id: uuid.UUID) -> Monitor | None:
        result = await self.session.execute(
            select(Monitor).where(
                Monitor.id == monitor_id,
                Monitor.workspace_id == workspace_id,
                Monitor.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[Monitor]:
        result = await self.session.execute(
            select(Monitor)
            .where(Monitor.workspace_id == workspace_id, Monitor.deleted_at.is_(None))
            .order_by(Monitor.created_at)
        )
        return list(result.scalars().all())

    async def count_by_workspace_status(self, workspace_id: uuid.UUID) -> dict[MonitorStatus, int]:
        """Counts of active, non-deleted monitors grouped by status."""
        result = await self.session.execute(
            select(Monitor.status, func.count())
            .where(Monitor.workspace_id == workspace_id, Monitor.deleted_at.is_(None))
            .group_by(Monitor.status)
        )
        return {status: count for status, count in result.all()}

    async def list_all_active(self) -> list[Monitor]:
        """All active, non-deleted monitors across all workspaces."""
        result = await self.session.execute(
            select(Monitor).where(Monitor.is_active.is_(True), Monitor.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def list_due_for_check(self, now: datetime) -> list[Monitor]:
        """Active, non-deleted monitors whose check interval has elapsed."""
        result = await self.session.execute(
            select(Monitor).where(Monitor.is_active.is_(True), Monitor.deleted_at.is_(None))
        )
        monitors = result.scalars().all()
        return [
            monitor
            for monitor in monitors
            if monitor.last_checked_at is None
            or (now - monitor.last_checked_at).total_seconds() >= monitor.check_interval_seconds
        ]

    async def exists_active(
        self,
        workspace_id: uuid.UUID,
        monitor_type: MonitorType,
        target: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        query = select(Monitor.id).where(
            Monitor.workspace_id == workspace_id,
            Monitor.monitor_type == monitor_type,
            Monitor.target == target,
            Monitor.deleted_at.is_(None),
        )
        if exclude_id is not None:
            query = query.where(Monitor.id != exclude_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

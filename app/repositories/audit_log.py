import uuid
from datetime import datetime

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.workspace_id == workspace_id)
            .order_by(AuditLog.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_in_workspace(self, workspace_id: uuid.UUID, audit_log_id: uuid.UUID) -> AuditLog | None:
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.id == audit_log_id, AuditLog.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.workspace_id == workspace_id)

        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if start is not None:
            stmt = stmt.where(AuditLog.created_at >= start)
        if end is not None:
            stmt = stmt.where(AuditLog.created_at < end)

        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

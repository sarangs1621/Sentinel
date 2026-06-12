import uuid

from sqlalchemy import select

from app.models.alert_rule import AlertRule
from app.repositories.base import BaseRepository


class AlertRuleRepository(BaseRepository[AlertRule]):
    model = AlertRule

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[AlertRule]:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.workspace_id == workspace_id).order_by(AlertRule.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_enabled_by_workspace(self, workspace_id: uuid.UUID) -> list[AlertRule]:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.workspace_id == workspace_id, AlertRule.is_enabled.is_(True))
        )
        return list(result.scalars().all())

    async def get_by_id_in_workspace(self, workspace_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule | None:
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.id == rule_id, AlertRule.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

import uuid

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.alert_rule import AlertRule
from app.models.user import User
from app.repositories.alert_rule import AlertRuleRepository
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleRead, AlertRuleUpdate, validate_target_for_channel
from app.services.audit_log import AuditLogService, to_jsonable


class AlertRuleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rules = AlertRuleRepository(session)
        self.audit = AuditLogService(session)

    @staticmethod
    def to_read(rule: AlertRule) -> AlertRuleRead:
        return AlertRuleRead.model_validate(rule)

    async def list_rules(self, workspace_id: uuid.UUID) -> list[AlertRuleRead]:
        rules = await self.rules.list_by_workspace(workspace_id)
        return [self.to_read(r) for r in rules]

    async def get_rule(self, workspace_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRuleRead:
        rule = await self.rules.get_by_id_in_workspace(workspace_id, rule_id)
        if rule is None:
            raise NotFoundError("Alert rule not found.")
        return self.to_read(rule)

    async def create_rule(
        self,
        workspace_id: uuid.UUID,
        data: AlertRuleCreate,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AlertRuleRead:
        rule = AlertRule(
            workspace_id=workspace_id,
            name=data.name,
            channel_type=data.channel_type,
            target=data.target,
            is_enabled=data.is_enabled,
            min_severity=data.min_severity,
        )
        self.rules.add(rule)
        await self.session.flush()

        await self.audit.record(
            workspace_id,
            user.id,
            "alert_rule.created",
            "alert_rule",
            rule.id,
            None,
            {
                "name": rule.name,
                "channel_type": to_jsonable(rule.channel_type),
                "target": rule.target,
                "is_enabled": rule.is_enabled,
                "min_severity": to_jsonable(rule.min_severity),
            },
            ip_address,
            user_agent,
        )

        await self.session.commit()
        await self.session.refresh(rule)
        return self.to_read(rule)

    async def update_rule(
        self,
        workspace_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: AlertRuleUpdate,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AlertRuleRead:
        rule = await self.rules.get_by_id_in_workspace(workspace_id, rule_id)
        if rule is None:
            raise NotFoundError("Alert rule not found.")

        updates = data.model_dump(exclude_unset=True)

        if "channel_type" in updates or "target" in updates:
            new_channel_type = updates.get("channel_type", rule.channel_type)
            new_target = updates.get("target", rule.target)
            try:
                validate_target_for_channel(new_channel_type, new_target)
            except (ValueError, PydanticValidationError) as exc:
                raise ValidationError(str(exc)) from exc

        old_values = {field: to_jsonable(getattr(rule, field)) for field in updates}

        for field, value in updates.items():
            setattr(rule, field, value)

        new_values = {field: to_jsonable(getattr(rule, field)) for field in updates}

        await self.audit.record(
            workspace_id,
            user.id,
            "alert_rule.updated",
            "alert_rule",
            rule.id,
            old_values,
            new_values,
            ip_address,
            user_agent,
        )

        await self.session.commit()
        await self.session.refresh(rule)
        return self.to_read(rule)

    async def delete_rule(
        self,
        workspace_id: uuid.UUID,
        rule_id: uuid.UUID,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        rule = await self.rules.get_by_id_in_workspace(workspace_id, rule_id)
        if rule is None:
            raise NotFoundError("Alert rule not found.")

        rule_id_for_audit = rule.id
        old_values = {
            "name": rule.name,
            "channel_type": to_jsonable(rule.channel_type),
            "target": rule.target,
            "is_enabled": rule.is_enabled,
            "min_severity": to_jsonable(rule.min_severity),
        }

        await self.rules.delete(rule)
        await self.audit.record(
            workspace_id,
            user.id,
            "alert_rule.deleted",
            "alert_rule",
            rule_id_for_audit,
            old_values,
            None,
            ip_address,
            user_agent,
        )
        await self.session.commit()

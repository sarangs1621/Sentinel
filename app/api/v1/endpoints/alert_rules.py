import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminOrOwner, AuditContextDep, CurrentUser, DbSession
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleRead, AlertRuleUpdate
from app.services.alert_rule import AlertRuleService

router = APIRouter()


@router.post("", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    data: AlertRuleCreate,
    current_user: CurrentUser,
    db: DbSession,
    membership: AdminOrOwner,
    audit_ctx: AuditContextDep,
) -> AlertRuleRead:
    workspace, _ = membership
    return await AlertRuleService(db).create_rule(
        workspace.id, data, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )


@router.get("", response_model=list[AlertRuleRead])
async def list_alert_rules(membership: AdminOrOwner, db: DbSession) -> list[AlertRuleRead]:
    workspace, _ = membership
    return await AlertRuleService(db).list_rules(workspace.id)


@router.get("/{rule_id}", response_model=AlertRuleRead)
async def get_alert_rule(rule_id: uuid.UUID, membership: AdminOrOwner, db: DbSession) -> AlertRuleRead:
    workspace, _ = membership
    return await AlertRuleService(db).get_rule(workspace.id, rule_id)


@router.patch("/{rule_id}", response_model=AlertRuleRead)
async def update_alert_rule(
    rule_id: uuid.UUID,
    data: AlertRuleUpdate,
    current_user: CurrentUser,
    db: DbSession,
    membership: AdminOrOwner,
    audit_ctx: AuditContextDep,
) -> AlertRuleRead:
    workspace, _ = membership
    return await AlertRuleService(db).update_rule(
        workspace.id, rule_id, data, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    membership: AdminOrOwner,
    audit_ctx: AuditContextDep,
) -> None:
    workspace, _ = membership
    await AlertRuleService(db).delete_rule(
        workspace.id, rule_id, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )

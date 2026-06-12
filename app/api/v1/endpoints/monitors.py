import uuid

from fastapi import APIRouter, status

from app.api.deps import AuditContextDep, CurrentUser, DbSession, WorkspaceMembership
from app.schemas.monitor import MonitorCreate, MonitorRead, MonitorUpdate
from app.services.monitor import MonitorService

router = APIRouter()


@router.post("", response_model=MonitorRead, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    data: MonitorCreate,
    current_user: CurrentUser,
    db: DbSession,
    membership: WorkspaceMembership,
    audit_ctx: AuditContextDep,
) -> MonitorRead:
    workspace, _ = membership
    return await MonitorService(db).create_monitor(
        workspace.id, current_user, data, audit_ctx.ip_address, audit_ctx.user_agent
    )


@router.get("", response_model=list[MonitorRead])
async def list_monitors(membership: WorkspaceMembership, db: DbSession) -> list[MonitorRead]:
    workspace, _ = membership
    return await MonitorService(db).list_monitors(workspace.id)


@router.get("/{monitor_id}", response_model=MonitorRead)
async def get_monitor(monitor_id: uuid.UUID, membership: WorkspaceMembership, db: DbSession) -> MonitorRead:
    workspace, _ = membership
    return await MonitorService(db).get_monitor(workspace.id, monitor_id)


@router.patch("/{monitor_id}", response_model=MonitorRead)
async def update_monitor(
    monitor_id: uuid.UUID,
    data: MonitorUpdate,
    current_user: CurrentUser,
    db: DbSession,
    membership: WorkspaceMembership,
    audit_ctx: AuditContextDep,
) -> MonitorRead:
    workspace, member = membership
    return await MonitorService(db).update_monitor(
        workspace.id, monitor_id, data, member, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    membership: WorkspaceMembership,
    audit_ctx: AuditContextDep,
) -> None:
    workspace, member = membership
    await MonitorService(db).delete_monitor(
        workspace.id, monitor_id, member, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )

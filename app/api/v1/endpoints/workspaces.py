import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminOrOwner, AuditContextDep, CurrentUser, DbSession, OwnerOnly, WorkspaceMembership
from app.schemas.workspace import WorkspaceCreate, WorkspaceJoin, WorkspaceRead, WorkspaceUpdate
from app.schemas.workspace_member import WorkspaceMemberRead, WorkspaceMemberRoleUpdate
from app.services.workspace import WorkspaceService

router = APIRouter()


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(data: WorkspaceCreate, current_user: CurrentUser, db: DbSession) -> WorkspaceRead:
    return await WorkspaceService(db).create_workspace(current_user, data)


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(current_user: CurrentUser, db: DbSession) -> list[WorkspaceRead]:
    return await WorkspaceService(db).list_workspaces(current_user)


@router.post("/join", response_model=WorkspaceRead)
async def join_workspace(
    data: WorkspaceJoin, current_user: CurrentUser, db: DbSession, audit_ctx: AuditContextDep
) -> WorkspaceRead:
    return await WorkspaceService(db).join_workspace(current_user, data, audit_ctx.ip_address, audit_ctx.user_agent)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(membership: WorkspaceMembership) -> WorkspaceRead:
    workspace, member = membership
    return WorkspaceService.to_workspace_read(workspace, member)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    data: WorkspaceUpdate, db: DbSession, membership: AdminOrOwner, audit_ctx: AuditContextDep
) -> WorkspaceRead:
    workspace, member = membership
    return await WorkspaceService(db).update_workspace(
        workspace.id, data, member, audit_ctx.ip_address, audit_ctx.user_agent
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(db: DbSession, membership: OwnerOnly) -> None:
    workspace, _ = membership
    await WorkspaceService(db).delete_workspace(workspace.id)


@router.post("/{workspace_id}/invite-code/regenerate", response_model=WorkspaceRead)
async def regenerate_invite_code(db: DbSession, membership: AdminOrOwner) -> WorkspaceRead:
    workspace, member = membership
    return await WorkspaceService(db).regenerate_invite_code(workspace.id, member)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
async def list_members(membership: WorkspaceMembership, db: DbSession) -> list[WorkspaceMemberRead]:
    workspace, _ = membership
    return await WorkspaceService(db).list_members(workspace.id)


@router.delete("/{workspace_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_workspace(membership: WorkspaceMembership, db: DbSession, audit_ctx: AuditContextDep) -> None:
    workspace, member = membership
    await WorkspaceService(db).leave_workspace(workspace.id, member.user_id, audit_ctx.ip_address, audit_ctx.user_agent)


@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberRead)
async def update_member_role(
    user_id: uuid.UUID,
    data: WorkspaceMemberRoleUpdate,
    db: DbSession,
    membership: AdminOrOwner,
) -> WorkspaceMemberRead:
    workspace, acting_member = membership
    return await WorkspaceService(db).update_member_role(workspace.id, user_id, data, acting_member)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID, db: DbSession, membership: AdminOrOwner, audit_ctx: AuditContextDep
) -> None:
    workspace, acting_member = membership
    await WorkspaceService(db).remove_member(
        workspace.id, user_id, acting_member, audit_ctx.ip_address, audit_ctx.user_agent
    )

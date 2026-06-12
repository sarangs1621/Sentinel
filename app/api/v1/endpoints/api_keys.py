import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminOrOwner, AuditContextDep, CurrentUser, DbSession
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_key import ApiKeyService

router = APIRouter()


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: CurrentUser,
    db: DbSession,
    membership: AdminOrOwner,
    audit_ctx: AuditContextDep,
) -> ApiKeyCreated:
    workspace, _ = membership
    return await ApiKeyService(db).create_key(
        workspace.id, data, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(membership: AdminOrOwner, db: DbSession) -> list[ApiKeyRead]:
    workspace, _ = membership
    return await ApiKeyService(db).list_keys(workspace.id)


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    membership: AdminOrOwner,
    audit_ctx: AuditContextDep,
) -> None:
    workspace, _ = membership
    await ApiKeyService(db).revoke_key(
        workspace.id, api_key_id, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminOrOwner, DbSession
from app.schemas.audit_log import AuditLogRead
from app.services.audit_log import AuditLogService

router = APIRouter()


@router.get("/search", response_model=list[AuditLogRead])
async def search_audit_logs(
    membership: AdminOrOwner,
    db: DbSession,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLogRead]:
    workspace, _ = membership
    return await AuditLogService(db).search(workspace.id, user_id, action, entity_type, start, end, limit, offset)


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(membership: AdminOrOwner, db: DbSession) -> list[AuditLogRead]:
    workspace, _ = membership
    return await AuditLogService(db).list_by_workspace(workspace.id)


@router.get("/{audit_log_id}", response_model=AuditLogRead)
async def get_audit_log(audit_log_id: uuid.UUID, membership: AdminOrOwner, db: DbSession) -> AuditLogRead:
    workspace, _ = membership
    return await AuditLogService(db).get_by_id(workspace.id, audit_log_id)

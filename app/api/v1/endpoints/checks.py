import uuid

from fastapi import APIRouter, status

from app.api.deps import DbSession, WorkspaceMembership, WorkspaceMembershipOrApiKey
from app.schemas.check import CheckCreate, CheckRead
from app.services.check import CheckService

router = APIRouter()


@router.post("", response_model=CheckRead, status_code=status.HTTP_201_CREATED)
async def record_check(
    monitor_id: uuid.UUID, data: CheckCreate, membership: WorkspaceMembershipOrApiKey, db: DbSession
) -> CheckRead:
    workspace, _ = membership
    return await CheckService(db).record_check(workspace.id, monitor_id, data)


@router.get("", response_model=list[CheckRead])
async def list_checks(monitor_id: uuid.UUID, membership: WorkspaceMembership, db: DbSession) -> list[CheckRead]:
    workspace, _ = membership
    return await CheckService(db).list_checks(workspace.id, monitor_id)

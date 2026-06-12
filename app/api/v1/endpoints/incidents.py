import uuid

from fastapi import APIRouter

from app.api.deps import AdminOrOwner, AuditContextDep, CurrentUser, DbSession, WorkspaceMembership
from app.schemas.incident import IncidentRead, IncidentUpdate
from app.services.incident import IncidentService

router = APIRouter()


@router.get("", response_model=list[IncidentRead])
async def list_incidents(membership: WorkspaceMembership, db: DbSession) -> list[IncidentRead]:
    workspace, _ = membership
    return await IncidentService(db).list_incidents(workspace.id)


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: uuid.UUID, membership: WorkspaceMembership, db: DbSession) -> IncidentRead:
    workspace, _ = membership
    return await IncidentService(db).get_incident(workspace.id, incident_id)


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: uuid.UUID,
    data: IncidentUpdate,
    current_user: CurrentUser,
    db: DbSession,
    membership: AdminOrOwner,
    audit_ctx: AuditContextDep,
) -> IncidentRead:
    workspace, _ = membership
    return await IncidentService(db).update_incident(
        workspace.id, incident_id, data, current_user, audit_ctx.ip_address, audit_ctx.user_agent
    )

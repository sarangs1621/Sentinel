from fastapi import APIRouter

from app.api.deps import DbSession, WorkspaceMembership
from app.schemas.metrics import WorkspaceDashboardRead
from app.services.metrics import MetricsService

router = APIRouter()


@router.get("", response_model=WorkspaceDashboardRead)
async def get_workspace_dashboard(membership: WorkspaceMembership, db: DbSession) -> WorkspaceDashboardRead:
    workspace, _ = membership
    return await MetricsService(db).get_workspace_dashboard(workspace.id)

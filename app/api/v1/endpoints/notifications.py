import uuid

from fastapi import APIRouter

from app.api.deps import DbSession, WorkspaceMembership
from app.schemas.notification import NotificationRead
from app.services.notification import NotificationService

router = APIRouter()


@router.get("", response_model=list[NotificationRead])
async def list_notifications(membership: WorkspaceMembership, db: DbSession) -> list[NotificationRead]:
    workspace, _ = membership
    return await NotificationService(db).list_notifications(workspace.id)


@router.get("/{notification_id}", response_model=NotificationRead)
async def get_notification(
    notification_id: uuid.UUID, membership: WorkspaceMembership, db: DbSession
) -> NotificationRead:
    workspace, _ = membership
    return await NotificationService(db).get_notification(workspace.id, notification_id)

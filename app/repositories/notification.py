import uuid

from sqlalchemy import and_, or_, select

from app.models.enums import NotificationStatus
from app.models.notification import Notification
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.workspace_id == workspace_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_in_workspace(
        self, workspace_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def list_due_for_delivery(self, max_attempts: int) -> list[Notification]:
        result = await self.session.execute(
            select(Notification).where(
                or_(
                    Notification.status == NotificationStatus.PENDING,
                    and_(
                        Notification.status == NotificationStatus.FAILED,
                        Notification.attempts < max_attempts,
                    ),
                )
            )
        )
        return list(result.scalars().all())

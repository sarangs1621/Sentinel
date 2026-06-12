import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.enums import WorkspaceRole
from app.models.workspace_member import WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    model = WorkspaceMember

    async def get_by_workspace_and_user(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .options(selectinload(WorkspaceMember.user))
        )
        return result.scalar_one_or_none()

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[WorkspaceMember]:
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .options(selectinload(WorkspaceMember.user))
            .order_by(WorkspaceMember.created_at)
        )
        return list(result.scalars().all())

    async def list_by_user(self, user_id: uuid.UUID) -> list[WorkspaceMember]:
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .options(selectinload(WorkspaceMember.workspace))
            .order_by(WorkspaceMember.created_at)
        )
        return list(result.scalars().all())

    async def count_by_workspace_and_role(self, workspace_id: uuid.UUID, role: WorkspaceRole) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == role,
            )
        )
        return result.scalar_one()

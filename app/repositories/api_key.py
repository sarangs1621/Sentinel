import uuid

from sqlalchemy import select

from app.models.api_key import ApiKey
from app.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    model = ApiKey

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[ApiKey]:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.workspace_id == workspace_id).order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_in_workspace(self, workspace_id: uuid.UUID, api_key_id: uuid.UUID) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == api_key_id, ApiKey.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_hash(self, hashed_key: str) -> ApiKey | None:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.hashed_key == hashed_key, ApiKey.revoked_at.is_(None))
        )
        return result.scalar_one_or_none()

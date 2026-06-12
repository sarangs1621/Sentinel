import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_api_key, hash_api_key
from app.models.api_key import ApiKey
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.api_key import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.audit_log import AuditLogService


class ApiKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.keys = ApiKeyRepository(session)
        self.audit = AuditLogService(session)

    @staticmethod
    def to_read(api_key: ApiKey) -> ApiKeyRead:
        return ApiKeyRead.model_validate(api_key)

    async def list_keys(self, workspace_id: uuid.UUID) -> list[ApiKeyRead]:
        keys = await self.keys.list_by_workspace(workspace_id)
        return [self.to_read(k) for k in keys]

    async def create_key(
        self,
        workspace_id: uuid.UUID,
        data: ApiKeyCreate,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ApiKeyCreated:
        raw_key, key_prefix, hashed_key = generate_api_key()

        api_key = ApiKey(
            workspace_id=workspace_id,
            created_by_user_id=user.id,
            name=data.name,
            key_prefix=key_prefix,
            hashed_key=hashed_key,
        )
        self.keys.add(api_key)
        await self.session.flush()

        await self.audit.record(
            workspace_id,
            user.id,
            "api_key.created",
            "api_key",
            api_key.id,
            None,
            {"name": api_key.name, "key_prefix": api_key.key_prefix},
            ip_address,
            user_agent,
        )

        await self.session.commit()
        await self.session.refresh(api_key)
        return ApiKeyCreated(**self.to_read(api_key).model_dump(), api_key=raw_key)

    async def revoke_key(
        self,
        workspace_id: uuid.UUID,
        api_key_id: uuid.UUID,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        api_key = await self.keys.get_by_id_in_workspace(workspace_id, api_key_id)
        if api_key is None:
            raise NotFoundError("API key not found.")
        if api_key.revoked_at is not None:
            raise ConflictError("API key is already revoked.")

        api_key.revoked_at = datetime.now(UTC)

        await self.audit.record(
            workspace_id,
            user.id,
            "api_key.revoked",
            "api_key",
            api_key.id,
            {"revoked_at": None},
            {"revoked_at": api_key.revoked_at.isoformat()},
            ip_address,
            user_agent,
        )

        await self.session.commit()

    async def authenticate(self, workspace_id: uuid.UUID, raw_key: str) -> Workspace | None:
        api_key = await self.keys.get_active_by_hash(hash_api_key(raw_key))
        if api_key is None or api_key.workspace_id != workspace_id:
            return None

        api_key.last_used_at = datetime.now(UTC)
        await self.session.commit()

        return await self.session.get(Workspace, workspace_id)

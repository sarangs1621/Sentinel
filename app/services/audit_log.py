import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditLog
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit_log import AuditLogRead

_SENSITIVE_FIELD_RE = re.compile(r"password|secret|token|api_key|hashed_key|^key$", re.IGNORECASE)


def to_jsonable(value: Any) -> Any:
    """Convert a Python value to a JSON-serializable form for old_values/new_values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def redact_sensitive(values: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mask values of fields whose names suggest they hold secrets, so audit
    log diffs never persist credentials even if a future caller passes one."""
    if values is None:
        return None
    return {key: ("[REDACTED]" if _SENSITIVE_FIELD_RE.search(key) else value) for key, value in values.items()}


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logs = AuditLogRepository(session)

    async def record(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        entry = AuditLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=redact_sensitive(old_values),
            new_values=redact_sensitive(new_values),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.logs.add(entry)
        await self.session.flush()

    async def list_by_workspace(self, workspace_id: uuid.UUID) -> list[AuditLogRead]:
        logs = await self.logs.list_by_workspace(workspace_id)
        return [AuditLogRead.model_validate(log) for log in logs]

    async def get_by_id(self, workspace_id: uuid.UUID, audit_log_id: uuid.UUID) -> AuditLogRead:
        log = await self.logs.get_by_id_in_workspace(workspace_id, audit_log_id)
        if log is None:
            raise NotFoundError("Audit log not found.")
        return AuditLogRead.model_validate(log)

    async def search(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogRead]:
        logs = await self.logs.search(workspace_id, user_id, action, entity_type, start, end, limit, offset)
        return [AuditLogRead.model_validate(log) for log in logs]

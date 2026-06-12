import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_log import AuditLogService, redact_sensitive
from tests.conftest import auth_headers


async def _create_workspace(client: AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_redact_sensitive_masks_secret_like_fields() -> None:
    values = {
        "name": "CI Key",
        "password": "hunter2",
        "secret": "shh",
        "token": "abc.def.ghi",
        "api_key": "sk_live_123",
        "hashed_key": "deadbeef",
        "key": "raw",
        "key_prefix": "sk_abcd1234",
    }

    redacted = redact_sensitive(values)

    assert redacted is not None
    assert redacted["name"] == "CI Key"
    assert redacted["key_prefix"] == "sk_abcd1234"
    for field in ("password", "secret", "token", "api_key", "hashed_key", "key"):
        assert redacted[field] == "[REDACTED]"


def test_redact_sensitive_handles_none() -> None:
    assert redact_sensitive(None) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_audit_log_record_redacts_sensitive_new_values(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await auth_headers(client, "redact-owner@example.com")
    workspace = await _create_workspace(client, headers, "Redact Co")

    service = AuditLogService(db_session)
    await service.record(
        workspace_id=uuid.UUID(workspace["id"]),
        user_id=None,
        action="api_key.created",
        entity_type="api_key",
        entity_id=uuid.uuid4(),
        new_values={"name": "CI Key", "key_prefix": "sk_abcd1234", "hashed_key": "deadbeef"},
    )
    await db_session.commit()

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=headers)
    entry = next(e for e in response.json() if e["action"] == "api_key.created")

    assert entry["new_values"]["name"] == "CI Key"
    assert entry["new_values"]["key_prefix"] == "sk_abcd1234"
    assert entry["new_values"]["hashed_key"] == "[REDACTED]"

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


# --- Helpers ---


async def _create_workspace(client: AsyncClient, headers: dict[str, str], name: str) -> dict:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _join_workspace(client: AsyncClient, headers: dict[str, str], invite_code: str) -> dict:
    response = await client.post("/api/v1/workspaces/join", json={"invite_code": invite_code}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _create_monitor(client: AsyncClient, headers: dict[str, str], workspace_id: str, **overrides) -> dict:
    payload = {
        "name": "Example",
        "monitor_type": "http",
        "target": "https://example.com",
        "check_interval_seconds": 60,
    }
    payload.update(overrides)
    response = await client.post(f"/api/v1/workspaces/{workspace_id}/monitors", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_api_key(
    client: AsyncClient, headers: dict[str, str], workspace_id: str, name: str = "CI Key"
) -> dict:
    response = await client.post(f"/api/v1/workspaces/{workspace_id}/api-keys", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- CRUD & RBAC ---


async def test_admin_or_owner_can_create_and_list_api_keys(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner1@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 1")

    created = await _create_api_key(client, owner_headers, workspace["id"], "CI Key")
    assert created["api_key"].startswith("sk_")
    assert created["key_prefix"] == created["api_key"][:11]
    assert created["name"] == "CI Key"
    assert created["revoked_at"] is None

    listed = await client.get(f"/api/v1/workspaces/{workspace['id']}/api-keys", headers=owner_headers)
    assert listed.status_code == 200
    entries = listed.json()
    assert len(entries) == 1
    assert entries[0]["key_prefix"] == created["key_prefix"]
    assert "api_key" not in entries[0]
    assert "hashed_key" not in entries[0]


async def test_member_denied_on_api_key_endpoints(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner2@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 2")
    created = await _create_api_key(client, owner_headers, workspace["id"])

    member_headers = await auth_headers(client, "apikey-member2@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    base = f"/api/v1/workspaces/{workspace['id']}/api-keys"
    assert (await client.post(base, json={"name": "Member Key"}, headers=member_headers)).status_code == 403
    assert (await client.get(base, headers=member_headers)).status_code == 403
    assert (await client.delete(f"{base}/{created['id']}", headers=member_headers)).status_code == 403


async def test_outsider_cannot_access_api_keys_in_other_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner3@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 3")
    created = await _create_api_key(client, owner_headers, workspace["id"])

    outsider_headers = await auth_headers(client, "apikey-outsider3@example.com")
    await _create_workspace(client, outsider_headers, "Outsider Co 3")

    base = f"/api/v1/workspaces/{workspace['id']}/api-keys"
    assert (await client.post(base, json={"name": "Outsider Key"}, headers=outsider_headers)).status_code == 403
    assert (await client.get(base, headers=outsider_headers)).status_code == 403
    assert (await client.delete(f"{base}/{created['id']}", headers=outsider_headers)).status_code == 403


# --- Revocation ---


async def test_revoke_nonexistent_api_key_returns_404(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner4b@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 4B")

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/api-keys/{uuid.uuid4()}", headers=owner_headers
    )
    assert response.status_code == 404


async def test_revoke_api_key(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner4@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 4")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])
    created = await _create_api_key(client, owner_headers, workspace["id"])

    base = f"/api/v1/workspaces/{workspace['id']}/api-keys"
    response = await client.delete(f"{base}/{created['id']}", headers=owner_headers)
    assert response.status_code == 204

    # Revoking again conflicts.
    response = await client.delete(f"{base}/{created['id']}", headers=owner_headers)
    assert response.status_code == 409

    # A revoked key can no longer authenticate the checks endpoint.
    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/checks",
        json={"status": "success"},
        headers={"X-API-Key": created["api_key"]},
    )
    assert response.status_code == 401


# --- Machine-to-machine auth on checks endpoint ---


async def test_checks_endpoint_accepts_valid_api_key_without_jwt(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner5@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 5")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])
    created = await _create_api_key(client, owner_headers, workspace["id"])

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/checks",
        json={"status": "success", "response_time_ms": 120},
        headers={"X-API-Key": created["api_key"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "success"


async def test_checks_endpoint_rejects_missing_credentials(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner6b@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 6B-creds")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/checks",
        json={"status": "success"},
    )
    assert response.status_code == 401


async def test_api_key_from_other_workspace_rejected_on_checks(client: AsyncClient) -> None:
    owner_a_headers = await auth_headers(client, "apikey-ownerA6@example.com")
    workspace_a = await _create_workspace(client, owner_a_headers, "API Key Co 6A")
    created_a = await _create_api_key(client, owner_a_headers, workspace_a["id"])

    owner_b_headers = await auth_headers(client, "apikey-ownerB6@example.com")
    workspace_b = await _create_workspace(client, owner_b_headers, "API Key Co 6B")
    monitor_b = await _create_monitor(client, owner_b_headers, workspace_b["id"])

    response = await client.post(
        f"/api/v1/workspaces/{workspace_b['id']}/monitors/{monitor_b['id']}/checks",
        json={"status": "success"},
        headers={"X-API-Key": created_a["api_key"]},
    )
    assert response.status_code == 401


# --- Audit logging ---


async def test_api_key_lifecycle_is_audited(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "apikey-owner7@example.com")
    workspace = await _create_workspace(client, owner_headers, "API Key Co 7")
    created = await _create_api_key(client, owner_headers, workspace["id"], "Audited Key")

    base = f"/api/v1/workspaces/{workspace['id']}/api-keys"
    await client.delete(f"{base}/{created['id']}", headers=owner_headers)

    audit = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=owner_headers)
    entries = {entry["action"]: entry for entry in audit.json() if entry["entity_id"] == created["id"]}

    assert entries["api_key.created"]["new_values"] == {"name": "Audited Key", "key_prefix": created["key_prefix"]}
    assert entries["api_key.revoked"]["new_values"]["revoked_at"] is not None

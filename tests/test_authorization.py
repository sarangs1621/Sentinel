import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, login_user, register_user

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


async def _record_check(
    client: AsyncClient, headers: dict[str, str], workspace_id: str, monitor_id: str, status_: str, **overrides
) -> dict:
    payload = {"status": status_}
    payload.update(overrides)
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/monitors/{monitor_id}/checks", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_alert_rule(client: AsyncClient, headers: dict[str, str], workspace_id: str, **overrides) -> dict:
    payload = {
        "name": "Default webhook",
        "channel_type": "webhook",
        "target": "https://hooks.example.com/notify",
    }
    payload.update(overrides)
    response = await client.post(f"/api/v1/workspaces/{workspace_id}/alert-rules", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Cross-workspace IDOR ---


async def test_outsider_cannot_access_monitor_in_other_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "idor-owner1@example.com")
    workspace = await _create_workspace(client, owner_headers, "IDOR Co 1")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    outsider_headers = await auth_headers(client, "idor-outsider1@example.com")
    await _create_workspace(client, outsider_headers, "Outsider Co 1")

    base = f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}"
    assert (await client.get(base, headers=outsider_headers)).status_code == 403
    assert (await client.patch(base, json={"name": "Hijacked"}, headers=outsider_headers)).status_code == 403
    assert (await client.delete(base, headers=outsider_headers)).status_code == 403


async def test_outsider_cannot_access_incident_in_other_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "idor-owner2@example.com")
    workspace = await _create_workspace(client, owner_headers, "IDOR Co 2")
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)
    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")

    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    outsider_headers = await auth_headers(client, "idor-outsider2@example.com")
    await _create_workspace(client, outsider_headers, "Outsider Co 2")

    base = f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}"
    assert (await client.get(base, headers=outsider_headers)).status_code == 403
    assert (await client.patch(base, json={"status": "investigating"}, headers=outsider_headers)).status_code == 403


async def test_outsider_cannot_access_alert_rule_in_other_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "idor-owner3@example.com")
    workspace = await _create_workspace(client, owner_headers, "IDOR Co 3")
    rule = await _create_alert_rule(client, owner_headers, workspace["id"])

    outsider_headers = await auth_headers(client, "idor-outsider3@example.com")
    await _create_workspace(client, outsider_headers, "Outsider Co 3")

    base = f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}"
    assert (await client.get(base, headers=outsider_headers)).status_code == 403
    assert (await client.patch(base, json={"is_enabled": False}, headers=outsider_headers)).status_code == 403
    assert (await client.delete(base, headers=outsider_headers)).status_code == 403


async def test_outsider_cannot_access_audit_log_in_other_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "idor-owner4@example.com")
    workspace = await _create_workspace(client, owner_headers, "IDOR Co 4")
    await _create_monitor(client, owner_headers, workspace["id"])

    logs = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=owner_headers)
    entry = logs.json()[0]

    outsider_headers = await auth_headers(client, "idor-outsider4@example.com")
    await _create_workspace(client, outsider_headers, "Outsider Co 4")

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/{entry['id']}", headers=outsider_headers
    )
    assert response.status_code == 403


# --- Role escalation: MEMBER denied on AdminOrOwner/OwnerOnly endpoints ---


async def test_member_denied_on_admin_or_owner_endpoints(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "rbac-owner1@example.com")
    workspace = await _create_workspace(client, owner_headers, "RBAC Co 1")
    rule = await _create_alert_rule(client, owner_headers, workspace["id"])
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)
    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")
    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    member_headers = await auth_headers(client, "rbac-member1@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    # OwnerOnly
    assert (await client.delete(f"/api/v1/workspaces/{workspace['id']}", headers=member_headers)).status_code == 403

    # AdminOrOwner: workspace update
    assert (
        await client.patch(f"/api/v1/workspaces/{workspace['id']}", json={"name": "Hacked"}, headers=member_headers)
    ).status_code == 403

    # AdminOrOwner: alert rules (create/list/read/update/delete)
    create_response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules",
        json={"name": "Second", "channel_type": "webhook", "target": "https://hooks.example.com/2"},
        headers=member_headers,
    )
    assert create_response.status_code == 403
    assert (
        await client.get(f"/api/v1/workspaces/{workspace['id']}/alert-rules", headers=member_headers)
    ).status_code == 403

    rule_base = f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}"
    assert (await client.get(rule_base, headers=member_headers)).status_code == 403
    assert (await client.patch(rule_base, json={"is_enabled": False}, headers=member_headers)).status_code == 403
    assert (await client.delete(rule_base, headers=member_headers)).status_code == 403

    # AdminOrOwner: incident updates (members can still read)
    incident_base = f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}"
    assert (
        await client.patch(incident_base, json={"status": "investigating"}, headers=member_headers)
    ).status_code == 403
    assert (await client.get(incident_base, headers=member_headers)).status_code == 200

    # AdminOrOwner: audit logs
    assert (
        await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=member_headers)
    ).status_code == 403


# --- Token-type confusion & revoked-token reuse ---


async def test_refresh_token_rejected_as_access_token(client: AsyncClient) -> None:
    await register_user(client, "tokenconfusion@example.com")
    tokens = await login_user(client, "tokenconfusion@example.com")

    response = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert response.status_code == 401


async def test_revoked_access_token_reuse_returns_401(client: AsyncClient) -> None:
    await register_user(client, "revokedreuse@example.com")
    tokens = await login_user(client, "revokedreuse@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert logout_response.status_code == 204

    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401

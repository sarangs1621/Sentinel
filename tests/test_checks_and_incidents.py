import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


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


async def test_create_monitor_default_failure_threshold(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner1@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 1")

    monitor = await _create_monitor(client, headers, workspace["id"])

    assert monitor["failure_threshold"] == 3
    assert monitor["consecutive_failures"] == 0
    assert monitor["last_checked_at"] is None


async def test_successful_check_marks_monitor_up(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner2@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 2")
    monitor = await _create_monitor(client, headers, workspace["id"])

    check = await _record_check(
        client, headers, workspace["id"], monitor["id"], "success", response_time_ms=120
    )
    assert check["status"] == "success"
    assert check["response_time_ms"] == 120

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "up"
    assert detail.json()["consecutive_failures"] == 0
    assert detail.json()["last_checked_at"] is not None


async def test_failure_below_threshold_does_not_open_incident(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner3@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 3")
    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=3)

    await _record_check(client, headers, workspace["id"], monitor["id"], "failure", error_message="timeout")

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["consecutive_failures"] == 1
    assert detail.json()["status"] == "pending"

    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    assert incidents.json() == []


async def test_failure_threshold_breach_opens_incident_and_recovery_resolves_it(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner4@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 4")
    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=2)

    await _record_check(client, headers, workspace["id"], monitor["id"], "failure", error_message="timeout")
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure", error_message="timeout")

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "down"
    assert detail.json()["consecutive_failures"] == 2

    incidents_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    incidents = incidents_response.json()
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["monitor_id"] == monitor["id"]
    assert incident["status"] == "open"
    assert incident["severity"] == "major"
    assert incident["resolved_at"] is None

    # a second consecutive failure should not open a duplicate incident
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure", error_message="timeout")
    incidents_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    assert len(incidents_response.json()) == 1

    # recovery resolves the incident and marks the monitor back up
    await _record_check(client, headers, workspace["id"], monitor["id"], "success")

    detail = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)
    assert detail.json()["status"] == "up"
    assert detail.json()["consecutive_failures"] == 0

    incidents_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    incident = incidents_response.json()[0]
    assert incident["status"] == "resolved"
    assert incident["resolved_at"] is not None


async def test_list_checks_for_monitor(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner5@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 5")
    monitor = await _create_monitor(client, headers, workspace["id"])

    await _record_check(client, headers, workspace["id"], monitor["id"], "success")
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/checks", headers=headers
    )

    assert response.status_code == 200
    statuses = {c["status"] for c in response.json()}
    assert statuses == {"success", "failure"}


async def test_record_check_for_nonexistent_monitor_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner6@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 6")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{uuid.uuid4()}/checks",
        json={"status": "success"},
        headers=headers,
    )

    assert response.status_code == 404


async def test_non_member_cannot_record_check(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "ci-owner7@example.com")
    workspace = await _create_workspace(client, owner_headers, "Reliability Co 7")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    outsider_headers = await auth_headers(client, "ci-outsider1@example.com")
    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}/checks",
        json={"status": "success"},
        headers=outsider_headers,
    )

    assert response.status_code == 403


async def test_get_nonexistent_incident_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner8@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 8")

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_update_nonexistent_incident_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "ci-owner8b@example.com")
    workspace = await _create_workspace(client, headers, "Reliability Co 8b")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{uuid.uuid4()}",
        json={"status": "investigating"},
        headers=headers,
    )

    assert response.status_code == 404


async def test_member_cannot_update_incident(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "ci-owner9@example.com")
    workspace = await _create_workspace(client, owner_headers, "Reliability Co 9")
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)

    member_headers = await auth_headers(client, "ci-member1@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")
    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "investigating"},
        headers=member_headers,
    )

    assert response.status_code == 403


async def test_admin_can_acknowledge_and_resolve_incident(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "ci-owner10@example.com")
    workspace = await _create_workspace(client, owner_headers, "Reliability Co 10")
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")
    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    ack_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "investigating"},
        headers=owner_headers,
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["status"] == "investigating"

    resolve_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "resolved"},
        headers=owner_headers,
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert resolve_response.json()["resolved_at"] is not None


async def test_cannot_update_already_resolved_incident(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "ci-owner11@example.com")
    workspace = await _create_workspace(client, owner_headers, "Reliability Co 11")
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")
    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "resolved"},
        headers=owner_headers,
    )

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "investigating"},
        headers=owner_headers,
    )

    assert response.status_code == 409


async def test_incident_update_rejects_open_status(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "ci-owner12@example.com")
    workspace = await _create_workspace(client, owner_headers, "Reliability Co 12")
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")
    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "open"},
        headers=owner_headers,
    )

    assert response.status_code == 422

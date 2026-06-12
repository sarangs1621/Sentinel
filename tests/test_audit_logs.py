import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.services.audit_log import to_jsonable
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


async def _get_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]


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


async def _list_audit_logs(client: AsyncClient, headers: dict[str, str], workspace_id: str) -> list[dict]:
    response = await client.get(f"/api/v1/workspaces/{workspace_id}/audit-logs", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _search_audit_logs(
    client: AsyncClient, headers: dict[str, str], workspace_id: str, **params
) -> list[dict]:
    response = await client.get(f"/api/v1/workspaces/{workspace_id}/audit-logs/search", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _find_log(logs: list[dict], action: str, entity_id: str | None = None) -> dict:
    matches = [log for log in logs if log["action"] == action and (entity_id is None or log["entity_id"] == entity_id)]
    assert matches, f"no audit log with action={action!r} entity_id={entity_id!r} found in {logs}"
    return matches[0]


# --- RBAC ---


async def test_member_cannot_access_audit_logs(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner1@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 1")

    member_headers = await auth_headers(client, "audit-member1@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    list_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=member_headers)
    assert list_response.status_code == 403

    search_response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/search", headers=member_headers
    )
    assert search_response.status_code == 403

    detail_response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/{uuid.uuid4()}", headers=member_headers
    )
    assert detail_response.status_code == 403


async def test_owner_can_list_audit_logs(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner2@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 2")

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    assert isinstance(logs, list)


# --- Monitor events ---


async def test_monitor_created_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner3@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 3")
    owner_id = await _get_user_id(client, owner_headers)

    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = _find_log(logs, "monitor.created", monitor["id"])

    assert entry["entity_type"] == "monitor"
    assert entry["user_id"] == owner_id
    assert entry["old_values"] is None
    assert entry["new_values"]["name"] == "Example"
    assert entry["new_values"]["monitor_type"] == "http"
    assert entry["new_values"]["target"] == "https://example.com"
    assert entry["new_values"]["is_active"] is True


async def test_monitor_updated_records_diff(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner4@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 4")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"name": "Renamed Monitor"},
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = _find_log(logs, "monitor.updated", monitor["id"])

    assert entry["old_values"] == {"name": "Example"}
    assert entry["new_values"] == {"name": "Renamed Monitor"}


async def test_monitor_enable_disable_emits_extra_event(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner5@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 5")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"is_active": False},
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    disabled_entry = _find_log(logs, "monitor.disabled", monitor["id"])
    assert disabled_entry["old_values"] == {"is_active": True}
    assert disabled_entry["new_values"] == {"is_active": False}

    updated_entry = _find_log(logs, "monitor.updated", monitor["id"])
    assert updated_entry["old_values"] == {"is_active": True}
    assert updated_entry["new_values"] == {"is_active": False}

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"is_active": True},
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    enabled_entry = _find_log(logs, "monitor.enabled", monitor["id"])
    assert enabled_entry["old_values"] == {"is_active": False}
    assert enabled_entry["new_values"] == {"is_active": True}


async def test_monitor_deleted_records_snapshot(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner6@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 6")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=owner_headers
    )
    assert response.status_code == 204, response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = _find_log(logs, "monitor.deleted", monitor["id"])

    assert entry["new_values"] is None
    assert entry["old_values"]["name"] == "Example"
    assert entry["old_values"]["monitor_type"] == "http"
    assert entry["old_values"]["target"] == "https://example.com"
    assert entry["old_values"]["is_active"] is True


# --- Incident events ---


async def test_auto_incident_lifecycle_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner7@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 7")
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")

    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    created_entry = _find_log(logs, "incident.created", incident_id)
    assert created_entry["entity_type"] == "incident"
    assert created_entry["user_id"] is None
    assert created_entry["old_values"] is None
    assert created_entry["new_values"]["status"] == "open"
    assert created_entry["new_values"]["monitor_id"] == monitor["id"]

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "success")

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    resolved_entry = _find_log(logs, "incident.resolved", incident_id)
    assert resolved_entry["user_id"] is None
    assert resolved_entry["old_values"] == {"status": "open"}
    assert resolved_entry["new_values"]["status"] == "resolved"
    assert resolved_entry["new_values"]["reason"] == "monitor_recovered"


async def test_manual_incident_acknowledge_and_resolve_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner8@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 8")
    owner_id = await _get_user_id(client, owner_headers)
    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)

    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")
    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=owner_headers)
    incident_id = incidents.json()[0]["id"]

    ack_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "investigating"},
        headers=owner_headers,
    )
    assert ack_response.status_code == 200, ack_response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    ack_entry = _find_log(logs, "incident.acknowledged", incident_id)
    assert ack_entry["user_id"] == owner_id
    assert ack_entry["old_values"] == {"status": "open"}
    assert ack_entry["new_values"] == {"status": "investigating"}

    resolve_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "resolved"},
        headers=owner_headers,
    )
    assert resolve_response.status_code == 200, resolve_response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    resolve_entry = _find_log(logs, "incident.resolved", incident_id)
    assert resolve_entry["user_id"] == owner_id
    assert resolve_entry["old_values"] == {"status": "investigating"}
    assert resolve_entry["new_values"] == {"status": "resolved", "reason": "manual"}


# --- Alert rule events ---


async def test_alert_rule_crud_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner9@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 9")

    rule = await _create_alert_rule(client, owner_headers, workspace["id"])

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    created_entry = _find_log(logs, "alert_rule.created", rule["id"])
    assert created_entry["old_values"] is None
    assert created_entry["new_values"]["name"] == "Default webhook"
    assert created_entry["new_values"]["channel_type"] == "webhook"
    assert created_entry["new_values"]["target"] == "https://hooks.example.com/notify"

    update_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}",
        json={"is_enabled": False},
        headers=owner_headers,
    )
    assert update_response.status_code == 200, update_response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    updated_entry = _find_log(logs, "alert_rule.updated", rule["id"])
    assert updated_entry["old_values"] == {"is_enabled": True}
    assert updated_entry["new_values"] == {"is_enabled": False}

    delete_response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}", headers=owner_headers
    )
    assert delete_response.status_code == 204, delete_response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    deleted_entry = _find_log(logs, "alert_rule.deleted", rule["id"])
    assert deleted_entry["new_values"] is None
    assert deleted_entry["old_values"]["name"] == "Default webhook"
    assert deleted_entry["old_values"]["channel_type"] == "webhook"


# --- Workspace & membership events ---


async def test_workspace_updated_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner10@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 10")
    owner_id = await _get_user_id(client, owner_headers)

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"description": "New description"},
        headers=owner_headers,
    )
    assert response.status_code == 200, response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = _find_log(logs, "workspace.updated", workspace["id"])
    assert entry["entity_type"] == "workspace"
    assert entry["user_id"] == owner_id
    assert entry["old_values"] == {"description": None}
    assert entry["new_values"] == {"description": "New description"}


async def test_member_added_and_removed_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner11@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 11")

    member_headers = await auth_headers(client, "audit-member11@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])
    member_id = await _get_user_id(client, member_headers)

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    added_entry = _find_log(logs, "member.added", member_id)
    assert added_entry["entity_type"] == "user"
    assert added_entry["user_id"] == member_id
    assert added_entry["old_values"] is None
    assert added_entry["new_values"] == {"role": "member"}

    remove_response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{member_id}", headers=owner_headers
    )
    assert remove_response.status_code == 204, remove_response.text

    owner_id = await _get_user_id(client, owner_headers)
    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    removed_entry = _find_log(logs, "member.removed", member_id)
    assert removed_entry["entity_type"] == "user"
    assert removed_entry["user_id"] == owner_id
    assert removed_entry["old_values"] == {"role": "member"}
    assert removed_entry["new_values"] is None


async def test_member_leave_recorded(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner12@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 12")

    member_headers = await auth_headers(client, "audit-member12@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])
    member_id = await _get_user_id(client, member_headers)

    leave_response = await client.delete(f"/api/v1/workspaces/{workspace['id']}/members/me", headers=member_headers)
    assert leave_response.status_code == 204, leave_response.text

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    removed_entry = _find_log(logs, "member.removed", member_id)
    assert removed_entry["user_id"] == member_id
    assert removed_entry["old_values"] == {"role": "member"}
    assert removed_entry["new_values"] is None


# --- Search & filtering ---


async def test_search_filters_by_action_and_entity_type(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner13@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 13")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])
    await _create_alert_rule(client, owner_headers, workspace["id"])

    by_action = await _search_audit_logs(client, owner_headers, workspace["id"], action="monitor.created")
    assert len(by_action) == 1
    assert by_action[0]["entity_id"] == monitor["id"]

    by_entity_type = await _search_audit_logs(client, owner_headers, workspace["id"], entity_type="alert_rule")
    assert len(by_entity_type) == 1
    assert by_entity_type[0]["action"] == "alert_rule.created"


async def test_search_filters_by_user_id(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner14@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 14")
    owner_id = await _get_user_id(client, owner_headers)

    member_headers = await auth_headers(client, "audit-member14@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])
    member_id = await _get_user_id(client, member_headers)

    await _create_monitor(client, owner_headers, workspace["id"])

    by_owner = await _search_audit_logs(client, owner_headers, workspace["id"], user_id=owner_id)
    actions = {log["action"] for log in by_owner}
    assert "monitor.created" in actions

    by_member = await _search_audit_logs(client, owner_headers, workspace["id"], user_id=member_id)
    actions = {log["action"] for log in by_member}
    assert "member.added" in actions
    assert "monitor.created" not in actions


async def test_search_filters_by_date_range(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner15@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 15")
    await _create_monitor(client, owner_headers, workspace["id"])

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    created_at = logs[0]["created_at"]

    before = await _search_audit_logs(client, owner_headers, workspace["id"], end=created_at)
    assert before == []

    after = await _search_audit_logs(client, owner_headers, workspace["id"], start=created_at)
    assert len(after) >= 1


async def test_search_pagination(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner16@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 16")

    for i in range(3):
        await _create_monitor(client, owner_headers, workspace["id"], target=f"https://example{i}.com")

    page1 = await _search_audit_logs(
        client, owner_headers, workspace["id"], action="monitor.created", limit=2, offset=0
    )
    page2 = await _search_audit_logs(
        client, owner_headers, workspace["id"], action="monitor.created", limit=2, offset=2
    )

    assert len(page1) == 2
    assert len(page2) == 1
    assert {log["id"] for log in page1}.isdisjoint({log["id"] for log in page2})


# --- Detail endpoint ---


async def test_get_audit_log_detail_and_404s(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner17@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 17")
    monitor = await _create_monitor(client, owner_headers, workspace["id"])

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = _find_log(logs, "monitor.created", monitor["id"])

    detail_response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/{entry['id']}", headers=owner_headers
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json() == entry

    unknown_response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/{uuid.uuid4()}", headers=owner_headers
    )
    assert unknown_response.status_code == 404

    other_owner_headers = await auth_headers(client, "audit-owner17b@example.com")
    other_workspace = await _create_workspace(client, other_owner_headers, "Audit Co 17b")

    cross_workspace_response = await client.get(
        f"/api/v1/workspaces/{other_workspace['id']}/audit-logs/{entry['id']}", headers=other_owner_headers
    )
    assert cross_workspace_response.status_code == 404


# --- Request metadata capture ---


async def test_audit_log_captures_ip_and_user_agent(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner18@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 18")

    custom_headers = {**owner_headers, "User-Agent": "sentinel-test-agent/1.0"}
    monitor = await _create_monitor(client, custom_headers, workspace["id"])

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = _find_log(logs, "monitor.created", monitor["id"])

    assert entry["ip_address"] is not None
    assert entry["user_agent"] == "sentinel-test-agent/1.0"


# --- Immutability ---


async def test_audit_logs_are_immutable(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "audit-owner19@example.com")
    workspace = await _create_workspace(client, owner_headers, "Audit Co 19")
    await _create_monitor(client, owner_headers, workspace["id"])

    logs = await _list_audit_logs(client, owner_headers, workspace["id"])
    entry = logs[0]

    patch_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/{entry['id']}",
        json={"action": "tampered"},
        headers=owner_headers,
    )
    assert patch_response.status_code == 405

    delete_response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs/{entry['id']}", headers=owner_headers
    )
    assert delete_response.status_code == 405

    collection_patch_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/audit-logs", json={}, headers=owner_headers
    )
    assert collection_patch_response.status_code == 405


# --- to_jsonable ---


async def test_to_jsonable_converts_uuid_and_datetime() -> None:
    value = uuid.uuid4()
    assert to_jsonable(value) == str(value)

    dt = datetime.now(UTC)
    assert to_jsonable(dt) == dt.isoformat()

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _get_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


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


async def test_create_http_monitor(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner1@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 1")
    user_id = await _get_user_id(client, headers)

    monitor = await _create_monitor(client, headers, workspace["id"], name="API", target="https://api.example.com")

    assert monitor["name"] == "API"
    assert monitor["monitor_type"] == "http"
    assert monitor["target"] == "https://api.example.com"
    assert monitor["status"] == "pending"
    assert monitor["is_active"] is True
    assert monitor["created_by_user_id"] == user_id


async def test_create_monitor_invalid_http_target_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner2@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 2")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors",
        json={"name": "Bad", "monitor_type": "http", "target": "not-a-url"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_create_tcp_monitor(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner3@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 3")

    monitor = await _create_monitor(
        client, headers, workspace["id"], name="DB", monitor_type="tcp", target="db.example.com:5432"
    )

    assert monitor["monitor_type"] == "tcp"
    assert monitor["target"] == "db.example.com:5432"


async def test_create_monitor_invalid_tcp_target_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner4@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 4")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors",
        json={"name": "Bad", "monitor_type": "tcp", "target": "db.example.com"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_create_ping_monitor(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner5@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 5")

    monitor = await _create_monitor(
        client, headers, workspace["id"], name="Host", monitor_type="ping", target="8.8.8.8"
    )

    assert monitor["monitor_type"] == "ping"
    assert monitor["target"] == "8.8.8.8"


async def test_create_monitor_invalid_ping_target_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner6@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 6")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors",
        json={"name": "Bad", "monitor_type": "ping", "target": "http://example.com"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_create_duplicate_monitor_returns_409(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner7@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 7")

    await _create_monitor(client, headers, workspace["id"], target="https://dup.example.com")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/monitors",
        json={"name": "Dup", "monitor_type": "http", "target": "https://dup.example.com"},
        headers=headers,
    )

    assert response.status_code == 409


async def test_member_can_create_monitor(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner8@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 8")

    member_headers = await auth_headers(client, "mon-member1@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    monitor = await _create_monitor(client, member_headers, workspace["id"], target="https://member.example.com")

    assert monitor["target"] == "https://member.example.com"


async def test_non_member_cannot_list_monitors(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner9@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 9")

    outsider_headers = await auth_headers(client, "mon-outsider1@example.com")
    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors", headers=outsider_headers)

    assert response.status_code == 403


async def test_get_nonexistent_monitor_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner10@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 10")

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_list_monitors_excludes_soft_deleted(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner11@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 11")

    keep = await _create_monitor(client, headers, workspace["id"], target="https://keep.example.com")
    remove = await _create_monitor(client, headers, workspace["id"], target="https://remove.example.com")

    delete_response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{remove['id']}", headers=headers
    )
    assert delete_response.status_code == 204

    list_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/monitors", headers=headers)
    targets = {m["target"] for m in list_response.json()}
    assert targets == {"https://keep.example.com"}

    get_response = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{remove['id']}", headers=headers
    )
    assert get_response.status_code == 404

    assert keep["target"] == "https://keep.example.com"


async def test_creator_can_update_own_monitor(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner12@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 12")

    member_headers = await auth_headers(client, "mon-member2@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    monitor = await _create_monitor(client, member_headers, workspace["id"], target="https://creator.example.com")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"name": "Renamed"},
        headers=member_headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


async def test_other_member_cannot_update_monitor(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner13@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 13")

    creator_headers = await auth_headers(client, "mon-member3@example.com")
    await _join_workspace(client, creator_headers, workspace["invite_code"])
    monitor = await _create_monitor(client, creator_headers, workspace["id"], target="https://other.example.com")

    other_headers = await auth_headers(client, "mon-member4@example.com")
    await _join_workspace(client, other_headers, workspace["invite_code"])

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"name": "Hacked"},
        headers=other_headers,
    )

    assert response.status_code == 403


async def test_admin_can_update_others_monitor(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner14@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 14")

    creator_headers = await auth_headers(client, "mon-member5@example.com")
    await _join_workspace(client, creator_headers, workspace["invite_code"])
    monitor = await _create_monitor(client, creator_headers, workspace["id"], target="https://admin.example.com")

    admin_headers = await auth_headers(client, "mon-admin1@example.com")
    await _join_workspace(client, admin_headers, workspace["invite_code"])
    admin_id = await _get_user_id(client, admin_headers)
    promote_response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{admin_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert promote_response.status_code == 200

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_other_member_cannot_delete_monitor(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner15@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 15")

    creator_headers = await auth_headers(client, "mon-member6@example.com")
    await _join_workspace(client, creator_headers, workspace["invite_code"])
    monitor = await _create_monitor(client, creator_headers, workspace["id"], target="https://protected.example.com")

    other_headers = await auth_headers(client, "mon-member7@example.com")
    await _join_workspace(client, other_headers, workspace["invite_code"])

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=other_headers
    )

    assert response.status_code == 403


async def test_update_monitor_duplicate_target_returns_409(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner16@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 16")

    await _create_monitor(client, headers, workspace["id"], target="https://taken.example.com")
    movable = await _create_monitor(client, headers, workspace["id"], target="https://free.example.com")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{movable['id']}",
        json={"target": "https://taken.example.com"},
        headers=headers,
    )

    assert response.status_code == 409


async def test_update_monitor_target_to_new_value_succeeds(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner16b@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 16b")

    monitor = await _create_monitor(client, headers, workspace["id"], target="https://old.example.com")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"target": "https://new.example.com"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["target"] == "https://new.example.com"


async def test_update_nonexistent_monitor_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner16c@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 16c")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{uuid.uuid4()}",
        json={"name": "Nope"},
        headers=headers,
    )

    assert response.status_code == 404


async def test_audit_log_records_monitor_lifecycle(client: AsyncClient) -> None:
    headers = await auth_headers(client, "mon-owner17@example.com")
    workspace = await _create_workspace(client, headers, "Monitor Co 17")

    monitor = await _create_monitor(client, headers, workspace["id"], target="https://audit.example.com")
    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}",
        json={"name": "Audited"},
        headers=headers,
    )
    await client.delete(f"/api/v1/workspaces/{workspace['id']}/monitors/{monitor['id']}", headers=headers)

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=headers)

    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json() if entry["entity_id"] == monitor["id"]]
    assert sorted(actions) == ["monitor.created", "monitor.deleted", "monitor.updated"]


async def test_member_cannot_view_audit_logs(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "mon-owner18@example.com")
    workspace = await _create_workspace(client, owner_headers, "Monitor Co 18")

    member_headers = await auth_headers(client, "mon-member8@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=member_headers)

    assert response.status_code == 403

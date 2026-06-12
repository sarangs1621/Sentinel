import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _get_user_id(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


async def _create_workspace(client: AsyncClient, headers: dict[str, str], name: str = "Acme Inc") -> dict:
    response = await client.post("/api/v1/workspaces", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_workspace_creator_becomes_owner(client: AsyncClient) -> None:
    headers = await auth_headers(client, "owner1@example.com")

    workspace = await _create_workspace(client, headers, "Acme Inc")

    assert workspace["name"] == "Acme Inc"
    assert workspace["slug"] == "acme-inc"
    assert workspace["role"] == "owner"
    assert workspace["invite_code"]  # owner can see the invite code


async def test_list_workspaces_returns_memberships(client: AsyncClient) -> None:
    headers = await auth_headers(client, "owner2@example.com")
    await _create_workspace(client, headers, "Workspace One")
    await _create_workspace(client, headers, "Workspace Two")

    response = await client.get("/api/v1/workspaces", headers=headers)

    assert response.status_code == 200
    names = {w["name"] for w in response.json()}
    assert names == {"Workspace One", "Workspace Two"}


async def test_get_nonexistent_workspace_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "owner3@example.com")

    response = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_non_member_cannot_access_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner4@example.com")
    workspace = await _create_workspace(client, owner_headers, "Private Co")

    other_headers = await auth_headers(client, "outsider1@example.com")
    response = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=other_headers)

    assert response.status_code == 403


async def test_join_workspace_via_invite_code(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner5@example.com")
    workspace = await _create_workspace(client, owner_headers, "Open Co")

    member_headers = await auth_headers(client, "member1@example.com")
    response = await client.post(
        "/api/v1/workspaces/join",
        json={"invite_code": workspace["invite_code"]},
        headers=member_headers,
    )

    assert response.status_code == 200
    joined = response.json()
    assert joined["id"] == workspace["id"]
    assert joined["role"] == "member"
    assert joined["invite_code"] is None  # members don't see the invite code


async def test_join_workspace_invalid_code_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "member2@example.com")

    response = await client.post(
        "/api/v1/workspaces/join", json={"invite_code": "does-not-exist"}, headers=headers
    )

    assert response.status_code == 404


async def test_join_workspace_already_member_returns_409(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner6@example.com")
    workspace = await _create_workspace(client, owner_headers, "Re-Join Co")

    response = await client.post(
        "/api/v1/workspaces/join",
        json={"invite_code": workspace["invite_code"]},
        headers=owner_headers,
    )

    assert response.status_code == 409


async def test_member_cannot_update_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner7@example.com")
    workspace = await _create_workspace(client, owner_headers, "Locked Co")

    member_headers = await auth_headers(client, "member3@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}", json={"name": "Hacked"}, headers=member_headers
    )

    assert response.status_code == 403


async def test_owner_can_update_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner8@example.com")
    workspace = await _create_workspace(client, owner_headers, "Editable Co")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}",
        json={"description": "Updated description"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"
    assert response.json()["name"] == "Editable Co"


async def test_regenerate_invite_code(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner9@example.com")
    workspace = await _create_workspace(client, owner_headers, "Rotating Co")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/invite-code/regenerate", headers=owner_headers
    )

    assert response.status_code == 200
    assert response.json()["invite_code"] != workspace["invite_code"]


async def test_list_members(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner10@example.com")
    workspace = await _create_workspace(client, owner_headers, "Team Co")

    member_headers = await auth_headers(client, "member4@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=owner_headers)

    assert response.status_code == 200
    members = response.json()
    roles = {m["email"]: m["role"] for m in members}
    assert roles["owner10@example.com"] == "owner"
    assert roles["member4@example.com"] == "member"


async def test_admin_can_promote_member_to_admin(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner11@example.com")
    workspace = await _create_workspace(client, owner_headers, "Promo Co")

    member_headers = await auth_headers(client, "member5@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )
    member_id = await _get_user_id(client, member_headers)

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{member_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_admin_cannot_grant_owner_role(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner12@example.com")
    workspace = await _create_workspace(client, owner_headers, "Strict Co")

    admin_headers = await auth_headers(client, "admin1@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=admin_headers
    )
    admin_id = await _get_user_id(client, admin_headers)
    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{admin_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )

    member_headers = await auth_headers(client, "member6@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )
    member_id = await _get_user_id(client, member_headers)

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{member_id}",
        json={"role": "owner"},
        headers=admin_headers,
    )

    assert response.status_code == 403


async def test_cannot_demote_sole_owner(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner13@example.com")
    workspace = await _create_workspace(client, owner_headers, "Solo Co")
    owner_id = await _get_user_id(client, owner_headers)

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )

    assert response.status_code == 409


async def test_remove_member(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner14@example.com")
    workspace = await _create_workspace(client, owner_headers, "Trim Co")

    member_headers = await auth_headers(client, "member7@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )
    member_id = await _get_user_id(client, member_headers)

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{member_id}", headers=owner_headers
    )

    assert response.status_code == 204

    members_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/members", headers=owner_headers)
    emails = {m["email"] for m in members_response.json()}
    assert "member7@example.com" not in emails


async def test_update_role_for_nonexistent_member_returns_404(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner18@example.com")
    workspace = await _create_workspace(client, owner_headers, "Ghost Co")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{uuid.uuid4()}",
        json={"role": "admin"},
        headers=owner_headers,
    )

    assert response.status_code == 404


async def test_remove_nonexistent_member_returns_404(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner19@example.com")
    workspace = await _create_workspace(client, owner_headers, "Ghost Co 2")

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{uuid.uuid4()}", headers=owner_headers
    )

    assert response.status_code == 404


async def test_non_owner_cannot_remove_owner(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner20@example.com")
    workspace = await _create_workspace(client, owner_headers, "Hierarchy Co")
    owner_id = await _get_user_id(client, owner_headers)

    admin_headers = await auth_headers(client, "admin2@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=admin_headers
    )
    admin_id = await _get_user_id(client, admin_headers)
    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/members/{admin_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}", headers=admin_headers
    )

    assert response.status_code == 403


async def test_sole_owner_cannot_remove_self_via_member_endpoint(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner21@example.com")
    workspace = await _create_workspace(client, owner_headers, "Sole Owner Co 2")
    owner_id = await _get_user_id(client, owner_headers)

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/members/{owner_id}", headers=owner_headers
    )

    assert response.status_code == 409


async def test_leave_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner15@example.com")
    workspace = await _create_workspace(client, owner_headers, "Departure Co")

    member_headers = await auth_headers(client, "member8@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )

    response = await client.delete(f"/api/v1/workspaces/{workspace['id']}/members/me", headers=member_headers)

    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=member_headers)
    assert get_response.status_code == 403


async def test_sole_owner_cannot_leave_workspace(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner16@example.com")
    workspace = await _create_workspace(client, owner_headers, "Anchored Co")

    response = await client.delete(f"/api/v1/workspaces/{workspace['id']}/members/me", headers=owner_headers)

    assert response.status_code == 409


async def test_delete_workspace_requires_owner(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "owner17@example.com")
    workspace = await _create_workspace(client, owner_headers, "Doomed Co")

    member_headers = await auth_headers(client, "member9@example.com")
    await client.post(
        "/api/v1/workspaces/join", json={"invite_code": workspace["invite_code"]}, headers=member_headers
    )

    forbidden = await client.delete(f"/api/v1/workspaces/{workspace['id']}", headers=member_headers)
    assert forbidden.status_code == 403

    allowed = await client.delete(f"/api/v1/workspaces/{workspace['id']}", headers=owner_headers)
    assert allowed.status_code == 204

    not_found = await client.get(f"/api/v1/workspaces/{workspace['id']}", headers=owner_headers)
    assert not_found.status_code == 404

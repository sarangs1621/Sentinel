import uuid

import aiosmtplib
import pytest
from httpx import AsyncClient, ConnectError, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.tasks import NOTIFICATION_MAX_ATTEMPTS, _deliver_notification, _get_due_notification_ids
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


# --- Alert rule CRUD / RBAC ---


async def test_list_alert_rules_empty_initially(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner1@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 1")

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/alert-rules", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_owner_can_create_webhook_alert_rule(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner2@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 2")

    body = await _create_alert_rule(client, headers, workspace["id"])

    assert body["channel_type"] == "webhook"
    assert body["target"] == "https://hooks.example.com/notify"
    assert body["is_enabled"] is True
    assert body["min_severity"] is None

    get_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/alert-rules/{body['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


async def test_owner_can_create_email_alert_rule(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner2b@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 2b")

    body = await _create_alert_rule(
        client, headers, workspace["id"], name="Ops email", channel_type="email", target="ops@example.com"
    )

    assert body["channel_type"] == "email"
    assert body["target"] == "ops@example.com"


async def test_member_cannot_create_alert_rule(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "alert-owner3@example.com")
    workspace = await _create_workspace(client, owner_headers, "Alert Co 3")

    member_headers = await auth_headers(client, "alert-member1@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    post_response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules",
        json={"name": "Member rule", "channel_type": "webhook", "target": "https://hooks.example.com/notify"},
        headers=member_headers,
    )
    assert post_response.status_code == 403

    get_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/alert-rules", headers=member_headers)
    assert get_response.status_code == 403


async def test_get_nonexistent_alert_rule_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner4@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 4")

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/alert-rules/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_update_nonexistent_alert_rule_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner4b@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 4b")

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{uuid.uuid4()}",
        json={"is_enabled": False},
        headers=headers,
    )

    assert response.status_code == 404


async def test_delete_nonexistent_alert_rule_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner4c@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 4c")

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{uuid.uuid4()}", headers=headers
    )

    assert response.status_code == 404


async def test_invalid_webhook_target_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner5@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 5")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules",
        json={"name": "Bad webhook", "channel_type": "webhook", "target": "not-a-url"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_invalid_email_target_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner5b@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 5b")

    response = await client.post(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules",
        json={"name": "Bad email", "channel_type": "email", "target": "not-an-email"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_update_alert_rule(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner6@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 6")
    rule = await _create_alert_rule(client, headers, workspace["id"])

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}",
        json={"is_enabled": False, "min_severity": "critical"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_enabled"] is False
    assert body["min_severity"] == "critical"


async def test_update_alert_rule_with_invalid_target_for_new_channel_returns_422(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner7@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 7")
    rule = await _create_alert_rule(client, headers, workspace["id"])

    response = await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}",
        json={"channel_type": "email"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_delete_alert_rule(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner8@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 8")
    rule = await _create_alert_rule(client, headers, workspace["id"])

    response = await client.delete(f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}", headers=headers)
    assert response.status_code == 204

    get_response = await client.get(f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}", headers=headers)
    assert get_response.status_code == 404


async def test_member_cannot_delete_alert_rule(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "alert-owner9@example.com")
    workspace = await _create_workspace(client, owner_headers, "Alert Co 9")
    rule = await _create_alert_rule(client, owner_headers, workspace["id"])

    member_headers = await auth_headers(client, "alert-member2@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    response = await client.delete(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}", headers=member_headers
    )
    assert response.status_code == 403


async def test_alert_rule_audit_events(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner10@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 10")
    rule = await _create_alert_rule(client, headers, workspace["id"])

    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}",
        json={"is_enabled": False},
        headers=headers,
    )
    await client.delete(f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}", headers=headers)

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=headers)

    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json() if entry["entity_id"] == rule["id"]]
    assert sorted(actions) == ["alert_rule.created", "alert_rule.deleted", "alert_rule.updated"]


# --- Notification generation on incident lifecycle ---


async def test_incident_opened_and_auto_resolved_generate_notifications(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner11@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 11")
    await _create_alert_rule(client, headers, workspace["id"])

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure", error_message="timeout")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    items = notifications.json()
    assert len(items) == 1
    assert items[0]["event_type"] == "incident_opened"
    assert items[0]["status"] == "pending"
    assert items[0]["attempts"] == 0
    assert items[0]["alert_rule_id"] is not None

    await _record_check(client, headers, workspace["id"], monitor["id"], "success")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    items = notifications.json()
    assert len(items) == 2
    event_types = {item["event_type"] for item in items}
    assert event_types == {"incident_opened", "incident_resolved"}


async def test_multiple_alert_rules_each_generate_a_notification(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner11b@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 11b")
    await _create_alert_rule(client, headers, workspace["id"], name="Webhook rule")
    await _create_alert_rule(
        client, headers, workspace["id"], name="Email rule", channel_type="email", target="ops@example.com"
    )

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    items = notifications.json()
    assert len(items) == 2
    rule_ids = {item["alert_rule_id"] for item in items}
    assert len(rule_ids) == 2


async def test_manual_resolve_generates_notification(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner12@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 12")
    await _create_alert_rule(client, headers, workspace["id"])

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    incidents = await client.get(f"/api/v1/workspaces/{workspace['id']}/incidents", headers=headers)
    incident_id = incidents.json()[0]["id"]

    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/incidents/{incident_id}",
        json={"status": "resolved"},
        headers=headers,
    )

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    event_types = [item["event_type"] for item in notifications.json()]
    assert event_types.count("incident_opened") == 1
    assert event_types.count("incident_resolved") == 1


async def test_no_notification_without_alert_rules(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner13@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 13")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    assert notifications.json() == []


async def test_disabled_rule_does_not_notify(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner14@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 14")
    await _create_alert_rule(client, headers, workspace["id"], is_enabled=False)

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    assert notifications.json() == []


async def test_min_severity_above_incident_severity_blocks_notification(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner15@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 15")
    # auto-opened incidents are "major" severity; requiring "critical" should suppress them.
    await _create_alert_rule(client, headers, workspace["id"], min_severity="critical")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    assert notifications.json() == []


async def test_min_severity_at_incident_severity_allows_notification(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner16@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 16")
    # auto-opened incidents are "major" severity; "minor" is a lower bar so it should pass.
    await _create_alert_rule(client, headers, workspace["id"], min_severity="minor")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    assert len(notifications.json()) == 1


# --- Notification listing / RBAC ---


async def test_get_nonexistent_notification_returns_404(client: AsyncClient) -> None:
    headers = await auth_headers(client, "alert-owner17@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 17")

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_member_can_list_notifications(client: AsyncClient) -> None:
    owner_headers = await auth_headers(client, "alert-owner18@example.com")
    workspace = await _create_workspace(client, owner_headers, "Alert Co 18")
    await _create_alert_rule(client, owner_headers, workspace["id"])

    monitor = await _create_monitor(client, owner_headers, workspace["id"], failure_threshold=1)
    await _record_check(client, owner_headers, workspace["id"], monitor["id"], "failure")

    member_headers = await auth_headers(client, "alert-member3@example.com")
    await _join_workspace(client, member_headers, workspace["invite_code"])

    response = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=member_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


# --- Webhook delivery ---


async def test_deliver_webhook_notification_success(client: AsyncClient, db_session: AsyncSession, respx_mock) -> None:
    headers = await auth_headers(client, "alert-owner19@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 19")
    await _create_alert_rule(client, headers, workspace["id"], target="https://hooks.example.com/notify")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    respx_mock.post("https://hooks.example.com/notify").mock(return_value=Response(200))

    await _deliver_notification(notification_id, session=db_session)

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "sent"
    assert body["attempts"] == 1
    assert body["response_status_code"] == 200
    assert body["error_message"] is None
    assert body["last_attempted_at"] is not None

    audit = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=headers)
    actions = [entry["action"] for entry in audit.json() if entry["entity_id"] == str(notification_id)]
    assert actions == ["notification.sent"]


async def test_deliver_webhook_notification_failure_status(
    client: AsyncClient, db_session: AsyncSession, respx_mock
) -> None:
    headers = await auth_headers(client, "alert-owner20@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 20")
    await _create_alert_rule(client, headers, workspace["id"], target="https://hooks.example.com/notify-fail")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    respx_mock.post("https://hooks.example.com/notify-fail").mock(return_value=Response(500))

    await _deliver_notification(notification_id, session=db_session)

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "failed"
    assert body["attempts"] == 1
    assert body["response_status_code"] == 500
    assert body["error_message"] == "HTTP 500"

    audit = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=headers)
    actions = [entry["action"] for entry in audit.json() if entry["entity_id"] == str(notification_id)]
    assert actions == ["notification.failed"]


async def test_deliver_webhook_notification_connection_error(
    client: AsyncClient, db_session: AsyncSession, respx_mock
) -> None:
    headers = await auth_headers(client, "alert-owner21@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 21")
    await _create_alert_rule(client, headers, workspace["id"], target="https://hooks.example.com/notify-error")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    respx_mock.post("https://hooks.example.com/notify-error").mock(side_effect=ConnectError("boom"))

    await _deliver_notification(notification_id, session=db_session)

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "failed"
    assert body["attempts"] == 1
    assert body["response_status_code"] is None
    assert body["error_message"] is not None


async def test_due_notification_listing_respects_max_attempts(
    client: AsyncClient, db_session: AsyncSession, respx_mock
) -> None:
    headers = await auth_headers(client, "alert-owner22@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 22")
    await _create_alert_rule(client, headers, workspace["id"], target="https://hooks.example.com/notify-retry")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    due_ids = await _get_due_notification_ids(session=db_session)
    assert notification_id in due_ids

    respx_mock.post("https://hooks.example.com/notify-retry").mock(return_value=Response(500))

    for _ in range(NOTIFICATION_MAX_ATTEMPTS):
        await _deliver_notification(notification_id, session=db_session)

    due_ids = await _get_due_notification_ids(session=db_session)
    assert notification_id not in due_ids

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "failed"
    assert body["attempts"] == NOTIFICATION_MAX_ATTEMPTS


# --- Email delivery ---


async def test_deliver_email_notification_success(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await auth_headers(client, "alert-owner23@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 23")
    await _create_alert_rule(
        client, headers, workspace["id"], name="Ops email", channel_type="email", target="ops@example.com"
    )

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    sent_messages = []

    async def fake_send(message, **kwargs):
        sent_messages.append(message)
        return ({}, "OK")

    monkeypatch.setattr("app.workers.notifier.aiosmtplib.send", fake_send)

    await _deliver_notification(notification_id, session=db_session)

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "sent"
    assert body["attempts"] == 1
    assert body["error_message"] is None

    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "ops@example.com"
    assert "Incident" in sent_messages[0]["Subject"]


async def test_deliver_email_notification_failure(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await auth_headers(client, "alert-owner24@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 24")
    await _create_alert_rule(
        client, headers, workspace["id"], name="Ops email", channel_type="email", target="ops@example.com"
    )

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    async def fake_send(message, **kwargs):
        raise aiosmtplib.SMTPException("connection refused")

    monkeypatch.setattr("app.workers.notifier.aiosmtplib.send", fake_send)

    await _deliver_notification(notification_id, session=db_session)

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "failed"
    assert body["attempts"] == 1
    assert body["response_status_code"] is None
    assert body["error_message"] == "connection refused"

    audit = await client.get(f"/api/v1/workspaces/{workspace['id']}/audit-logs", headers=headers)
    actions = [entry["action"] for entry in audit.json() if entry["entity_id"] == str(notification_id)]
    assert actions == ["notification.failed"]


async def test_deliver_email_notification_for_resolved_incident_includes_resolved_at(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await auth_headers(client, "alert-owner24b@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 24b")
    await _create_alert_rule(
        client, headers, workspace["id"], name="Ops email", channel_type="email", target="ops@example.com"
    )

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")
    await _record_check(client, headers, workspace["id"], monitor["id"], "success")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    resolved = next(item for item in notifications.json() if item["event_type"] == "incident_resolved")
    notification_id = uuid.UUID(resolved["id"])

    sent_messages = []

    async def fake_send(message, **kwargs):
        sent_messages.append(message)
        return ({}, "OK")

    monkeypatch.setattr("app.workers.notifier.aiosmtplib.send", fake_send)

    await _deliver_notification(notification_id, session=db_session)

    assert len(sent_messages) == 1
    assert "Resolved at:" in sent_messages[0].get_content()


async def test_deliver_notification_skips_disabled_rule(
    client: AsyncClient, db_session: AsyncSession, respx_mock
) -> None:
    headers = await auth_headers(client, "alert-owner25@example.com")
    workspace = await _create_workspace(client, headers, "Alert Co 25")
    rule = await _create_alert_rule(client, headers, workspace["id"], target="https://hooks.example.com/notify")

    monitor = await _create_monitor(client, headers, workspace["id"], failure_threshold=1)
    await _record_check(client, headers, workspace["id"], monitor["id"], "failure")

    notifications = await client.get(f"/api/v1/workspaces/{workspace['id']}/notifications", headers=headers)
    notification_id = uuid.UUID(notifications.json()[0]["id"])

    await client.patch(
        f"/api/v1/workspaces/{workspace['id']}/alert-rules/{rule['id']}",
        json={"is_enabled": False},
        headers=headers,
    )

    respx_mock.post("https://hooks.example.com/notify").mock(return_value=Response(200))

    await _deliver_notification(notification_id, session=db_session)

    detail = await client.get(
        f"/api/v1/workspaces/{workspace['id']}/notifications/{notification_id}", headers=headers
    )
    body = detail.json()
    assert body["status"] == "pending"
    assert body["attempts"] == 0

from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from app.core.config import settings
from app.models.enums import NotificationEvent
from app.models.incident import Incident

_DELIVERY_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    status_code: int | None
    error_message: str | None


def _build_payload(incident: Incident, event: NotificationEvent) -> dict:
    return {
        "event": event.value,
        "incident": {
            "id": str(incident.id),
            "workspace_id": str(incident.workspace_id),
            "monitor_id": str(incident.monitor_id),
            "title": incident.title,
            "status": incident.status.value,
            "severity": incident.severity.value,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "created_at": incident.created_at.isoformat(),
        },
    }


async def deliver_webhook(webhook_url: str, incident: Incident, event: NotificationEvent) -> DeliveryResult:
    payload = _build_payload(incident, event)
    try:
        async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT_SECONDS) as http_client:
            response = await http_client.post(webhook_url, json=payload)
        if response.status_code < 400:
            return DeliveryResult(True, response.status_code, None)
        return DeliveryResult(False, response.status_code, f"HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        return DeliveryResult(False, None, str(exc))


def _build_subject(incident: Incident, event: NotificationEvent) -> str:
    verb = "opened" if event == NotificationEvent.INCIDENT_OPENED else "resolved"
    return f"[Sentinel] Incident {verb}: {incident.title}"


def _build_body(incident: Incident, event: NotificationEvent) -> str:
    lines = [
        f"Incident: {incident.title}",
        f"Event: {event.value}",
        f"Status: {incident.status.value}",
        f"Severity: {incident.severity.value}",
        f"Created at: {incident.created_at.isoformat()}",
    ]
    if incident.resolved_at is not None:
        lines.append(f"Resolved at: {incident.resolved_at.isoformat()}")
    return "\n".join(lines)


async def deliver_email(to_address: str, incident: Incident, event: NotificationEvent) -> DeliveryResult:
    if not settings.RESEND_API_KEY:
        return DeliveryResult(False, None, "RESEND_API_KEY is not configured")

    payload = {
        "from": settings.EMAIL_FROM_ADDRESS,
        "to": [to_address],
        "subject": _build_subject(incident, event),
        "html": _build_body(incident, event).replace('\n', '<br>')
    }

    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT_SECONDS) as http_client:
            response = await http_client.post("https://api.resend.com/emails", json=payload, headers=headers)
        if response.status_code < 400:
            return DeliveryResult(True, response.status_code, None)
        return DeliveryResult(False, response.status_code, f"Resend API error: {response.text}")
    except httpx.HTTPError as exc:
        return DeliveryResult(False, None, str(exc))

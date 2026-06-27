from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib
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
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM_ADDRESS
    message["To"] = to_address
    message["Subject"] = _build_subject(incident, event)
    message.set_content(_build_body(incident, event))

    try:
        use_tls = settings.SMTP_USE_TLS and settings.SMTP_PORT == 465
        start_tls = settings.SMTP_USE_TLS and settings.SMTP_PORT != 465

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            use_tls=use_tls,
            start_tls=start_tls,
            timeout=_DELIVERY_TIMEOUT_SECONDS,
        )
        return DeliveryResult(True, None, None)
    except (aiosmtplib.SMTPException, OSError) as exc:
        return DeliveryResult(False, None, str(exc))

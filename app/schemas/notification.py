import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationEvent, NotificationStatus


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    incident_id: uuid.UUID
    alert_rule_id: uuid.UUID
    event_type: NotificationEvent
    status: NotificationStatus
    attempts: int
    last_attempted_at: datetime | None
    response_status_code: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import IncidentSeverity, IncidentStatus


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    monitor_id: uuid.UUID
    title: str
    status: IncidentStatus
    severity: IncidentSeverity
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class IncidentUpdate(BaseModel):
    status: IncidentStatus

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: IncidentStatus) -> IncidentStatus:
        if value not in (IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED):
            raise ValueError("status must be 'investigating' or 'resolved'")
        return value

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, TypeAdapter, ValidationError, model_validator

from app.models.enums import IncidentSeverity, NotificationChannel

_EMAIL_ADAPTER = TypeAdapter(EmailStr)
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def validate_target_for_channel(channel_type: NotificationChannel, target: str) -> None:
    """Raise `ValueError` if `target` isn't a valid destination for `channel_type`."""
    try:
        if channel_type == NotificationChannel.EMAIL:
            _EMAIL_ADAPTER.validate_python(target)
        else:
            _HTTP_URL_ADAPTER.validate_python(target)
    except ValidationError as exc:
        raise ValueError(f"'{target}' is not a valid {channel_type.value} target.") from exc


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    channel_type: NotificationChannel
    target: str = Field(min_length=1, max_length=2048)
    is_enabled: bool = True
    min_severity: IncidentSeverity | None = None

    @model_validator(mode="after")
    def _check_target(self) -> "AlertRuleCreate":
        validate_target_for_channel(self.channel_type, self.target)
        return self


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    channel_type: NotificationChannel | None = None
    target: str | None = Field(default=None, min_length=1, max_length=2048)
    is_enabled: bool | None = None
    min_severity: IncidentSeverity | None = None


class AlertRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    channel_type: NotificationChannel
    target: str
    is_enabled: bool
    min_severity: IncidentSeverity | None
    created_at: datetime
    updated_at: datetime

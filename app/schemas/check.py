import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CheckStatus


class CheckCreate(BaseModel):
    status: CheckStatus
    response_time_ms: int | None = Field(default=None, ge=0)
    error_message: str | None = Field(default=None, max_length=1000)


class CheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    monitor_id: uuid.UUID
    status: CheckStatus
    response_time_ms: int | None
    error_message: str | None
    created_at: datetime

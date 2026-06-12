import ipaddress
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import MonitorStatus, MonitorType

_HOSTNAME_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$"
)


def _validate_http_target(target: str) -> None:
    parsed = urlparse(target)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("HTTP monitors require an absolute 'http://' or 'https://' URL.")


def _validate_tcp_target(target: str) -> None:
    host, sep, port = target.rpartition(":")
    if not sep or not host:
        raise ValueError("TCP monitors require a target in 'host:port' format.")
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        raise ValueError("TCP monitor port must be an integer between 1 and 65535.")


def _validate_ping_target(target: str) -> None:
    host = target.strip()
    if not host or "://" in host or "/" in host or " " in host or len(host) > 253:
        raise ValueError("PING monitors require a bare hostname or IP address.")
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    if not _HOSTNAME_RE.match(host):
        raise ValueError("PING monitor target must be a valid hostname or IP address.")


_TARGET_VALIDATORS: dict[MonitorType, Callable[[str], None]] = {
    MonitorType.HTTP: _validate_http_target,
    MonitorType.TCP: _validate_tcp_target,
    MonitorType.PING: _validate_ping_target,
}


def validate_target_for_type(monitor_type: MonitorType, target: str) -> None:
    """Raise `ValueError` if `target` isn't a valid target for `monitor_type`."""
    _TARGET_VALIDATORS[monitor_type](target)


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    monitor_type: MonitorType
    target: str = Field(min_length=1, max_length=512)
    check_interval_seconds: int = Field(default=60, ge=30, le=86400)
    failure_threshold: int = Field(default=3, ge=1, le=100)
    is_active: bool = True

    @model_validator(mode="after")
    def _check_target(self) -> "MonitorCreate":
        validate_target_for_type(self.monitor_type, self.target)
        return self


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target: str | None = Field(default=None, min_length=1, max_length=512)
    check_interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    failure_threshold: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class MonitorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    monitor_type: MonitorType
    target: str
    check_interval_seconds: int
    failure_threshold: int
    consecutive_failures: int
    last_checked_at: datetime | None
    status: MonitorStatus
    is_active: bool
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    last_response_time_ms: int | None = None

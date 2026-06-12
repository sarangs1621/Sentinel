from enum import StrEnum


def enum_column_values(enum_cls: type[StrEnum]) -> list[str]:
    """`values_callable` for SAEnum columns: use `.value` (lowercase) instead of
    SQLAlchemy's default of `.name`, so native enum types match server defaults
    and Alembic-defined enum values."""
    return [member.value for member in enum_cls]


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MonitorType(StrEnum):
    HTTP = "http"
    TCP = "tcp"
    PING = "ping"


class MonitorStatus(StrEnum):
    PENDING = "pending"
    UP = "up"
    DOWN = "down"


class CheckStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class IncidentSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class NotificationEvent(StrEnum):
    INCIDENT_OPENED = "incident_opened"
    INCIDENT_RESOLVED = "incident_resolved"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationChannel(StrEnum):
    WEBHOOK = "webhook"
    EMAIL = "email"


class MetricPeriod(StrEnum):
    DAILY = "daily"

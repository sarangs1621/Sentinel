# Database ER Diagram

Sentinel's schema is managed by Alembic (`alembic/versions/`, 9 migrations) and
defined in `app/models/`. Every table uses a UUID primary key
(`UUIDPkMixin`) and `created_at`/`updated_at` timestamps
(`CreatedAtMixin`/`TimestampMixin`).

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email
        string hashed_password
        string full_name
        bool is_active
        bool is_superuser
    }

    WORKSPACES {
        uuid id PK
        string name
        string slug
        string description
        string invite_code
    }

    WORKSPACE_MEMBERS {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        enum role "owner | admin | member"
    }

    MONITORS {
        uuid id PK
        uuid workspace_id FK
        uuid created_by_user_id FK
        string name
        enum monitor_type "http | tcp | ping"
        string target
        int check_interval_seconds
        int failure_threshold
        int consecutive_failures
        enum status "pending | up | down"
        bool is_active
        datetime deleted_at
    }

    CHECKS {
        uuid id PK
        uuid monitor_id FK
        enum status "success | failure"
        int response_time_ms
        string error_message
        datetime created_at
    }

    INCIDENTS {
        uuid id PK
        uuid workspace_id FK
        uuid monitor_id FK
        string title
        enum status "open | investigating | resolved"
        enum severity "minor | major | critical"
        datetime resolved_at
    }

    ALERT_RULES {
        uuid id PK
        uuid workspace_id FK
        string name
        enum channel_type "webhook | email"
        string target
        bool is_enabled
        enum min_severity "minor | major | critical | null"
    }

    NOTIFICATIONS {
        uuid id PK
        uuid workspace_id FK
        uuid incident_id FK
        uuid alert_rule_id FK
        enum event_type "incident_opened | incident_resolved"
        enum status "pending | sent | failed"
        int attempts
        datetime last_attempted_at
        int response_status_code
        string error_message
    }

    AUDIT_LOGS {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        string action
        string entity_type
        uuid entity_id
        jsonb old_values
        jsonb new_values
        string ip_address
        string user_agent
        datetime created_at
    }

    API_KEYS {
        uuid id PK
        uuid workspace_id FK
        uuid created_by_user_id FK
        string name
        string key_prefix
        string hashed_key
        datetime last_used_at
        datetime revoked_at
    }

    REFRESH_TOKENS {
        uuid id PK "doubles as JWT jti"
        uuid user_id FK
        datetime expires_at
        bool revoked
    }

    METRIC_SNAPSHOTS {
        uuid id PK
        uuid monitor_id FK
        uuid workspace_id FK
        enum period_type "daily"
        datetime period_start
        datetime period_end
        int total_checks
        int successful_checks
        int failed_checks
        float uptime_percentage
        float check_pass_ratio
        float avg_response_time_ms
        float p95_response_time_ms
        int incidents_count
    }

    USERS ||--o{ WORKSPACE_MEMBERS : "belongs to (role)"
    WORKSPACES ||--o{ WORKSPACE_MEMBERS : "has members"

    WORKSPACES ||--o{ MONITORS : "owns"
    WORKSPACES ||--o{ INCIDENTS : "owns"
    WORKSPACES ||--o{ ALERT_RULES : "configures"
    WORKSPACES ||--o{ NOTIFICATIONS : "owns"
    WORKSPACES ||--o{ AUDIT_LOGS : "logs"
    WORKSPACES ||--o{ API_KEYS : "issues"
    WORKSPACES ||--o{ METRIC_SNAPSHOTS : "aggregates"

    MONITORS ||--o{ CHECKS : "produces"
    MONITORS ||--o{ INCIDENTS : "triggers"
    MONITORS ||--o{ METRIC_SNAPSHOTS : "rolls up into"

    INCIDENTS ||--o{ NOTIFICATIONS : "fans out to"
    ALERT_RULES ||--o{ NOTIFICATIONS : "delivers via"

    USERS ||--o{ REFRESH_TOKENS : "owns sessions"
    USERS |o--o{ MONITORS : "created by (optional)"
    USERS |o--o{ API_KEYS : "created by (optional)"
    USERS |o--o{ AUDIT_LOGS : "performed by (nullable for system events)"
```

## Notes on design decisions

- **UUID primary keys everywhere** — avoids leaking sequential IDs across
  workspace boundaries and lets rows be created client-side / merged across
  environments without collision.
- **`workspace_id` on almost every table** — Sentinel is multi-tenant; every
  domain table (monitors, incidents, alert rules, notifications, audit logs,
  API keys, metric snapshots) is scoped to a workspace and every repository
  query filters on it. See [`docs/INTERVIEW_NOTES.md`](INTERVIEW_NOTES.md)
  for the "why multi-tenant" rationale.
- **Soft delete on `monitors`** — `deleted_at` (nullable) instead of a hard
  delete, so historical `checks`/`incidents`/`metric_snapshots` referencing
  a deleted monitor remain intact for audit/analytics. A partial unique index
  (`uq_monitors_workspace_id_monitor_type_target`, `WHERE deleted_at IS
  NULL`) allows re-creating a monitor with the same type+target after the
  original is deleted.
- **`ON DELETE SET NULL` for "created by" / "actor" FKs** (`monitors.
  created_by_user_id`, `api_keys.created_by_user_id`,
  `audit_logs.user_id`) — deleting a user doesn't cascade-delete the
  resources they created or the audit trail of their actions; `user_id`
  becomes `NULL`, and `audit_logs.user_id = NULL` is also used deliberately
  for **system-generated** events (auto incident open/resolve, notification
  delivery worker).
- **`refresh_tokens.id` doubles as the JWT `jti` claim** — revocation is a
  single indexed `UPDATE refresh_tokens SET revoked = true WHERE id = :jti`,
  no separate denylist table for refresh tokens (access tokens use a
  short-TTL Redis denylist instead — see
  [`docs/INTERVIEW_NOTES.md`](INTERVIEW_NOTES.md)).
- **`metric_snapshots` unique on `(monitor_id, period_type, period_start)`**
  — the daily aggregation job is idempotent; re-running it for a day it has
  already processed upserts the existing row instead of duplicating it.
- **Indexes** added in migration `0008` on high-cardinality query paths:
  `checks(created_at)`, `checks(monitor_id, created_at)`,
  `checks(monitor_id, status, created_at)`, `incidents(status)`,
  `incidents(created_at)`, `notifications(status)`,
  `monitors(is_active)`, `monitors(deleted_at)` — these back the dashboard,
  metrics, and notification-dispatch queries.

For full column-level detail, see the SQLAlchemy models in `app/models/` and
the migration history in `alembic/versions/`.

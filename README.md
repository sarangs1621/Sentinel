# Sentinel — Phases 1-3, 5, 6 & 7: Auth, Workspaces, Monitors, Incidents, Scheduler, Alerting, Analytics & Audit Logging

Production-grade observability/incident-management platform. Phase 1
implements user registration/login (JWT) and workspace creation/joining with
owner/admin/member roles. Phase 2 adds monitor CRUD (HTTP/TCP/PING), RBAC
enforcement, soft delete, and workspace audit logging. Phase 3 (slice 1)
adds check-result recording, a per-monitor failure counter, and automatic
incident detection/resolution. Phase 3 (slice 2) adds a Celery + Redis
scheduler and worker that automatically run those checks. Phase 5 adds
per-workspace alert rules (webhook or email channels, each with their own
enabled flag and minimum severity) and async notification delivery for
incident open/resolve events. Phase 6 adds latency and uptime/SLA reporting,
persisted daily metric snapshots, a workspace dashboard, and a scheduled
daily aggregation job. Phase 7 enriches the audit log with before/after
diffs, request metadata (IP/user agent), and search/filtering APIs so that
admins/owners can trace who changed what, when, and from where.

## Stack

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Alembic · Pydantic v2 ·
Celery + Redis · Repository + Service layers · Pytest

## Local development

1. Copy the environment template and adjust as needed:

   ```bash
   cp .env.example .env
   ```

2. Start Postgres (and the API) with Docker Compose:

   ```bash
   docker compose up -d
   ```

   The `api` container runs `alembic upgrade head` automatically on startup.

3. API docs are available at `http://localhost:8000/docs`.

### Running without Docker

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Local Postgres (no Docker, Windows)

This machine has no Docker and the system `postgresql-x64-17` service (port
5432, runs as `NetworkService`) has an unknown superuser password. Local dev
instead uses a second, user-owned Postgres instance on port **5433**, with
data dir `C:\Users\saran\pgdata\sentinel`. `.env` is already configured for
this (`sentinel`/`sentinel` on `localhost:5433`, databases `sentinel` and
`sentinel_test`).

Start it:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D "C:\Users\saran\pgdata\sentinel" -l "C:\Users\saran\pgdata\sentinel.log" -o "-p 5433" start
```

Stop it:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D "C:\Users\saran\pgdata\sentinel" stop
```

## Database migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Tests

Tests run against `TEST_DATABASE_URL` (a separate database from the dev DB).

```bash
createdb sentinel_test   # or via psql/pgAdmin
pytest -v
```

## Coverage

Every `pytest` run reports line+branch coverage for `app/` (configured via
`pytest.ini` and `pyproject.toml`) and fails if overall coverage drops below
**95%**:

```bash
pytest --cov=app --cov-report=html
```

A detailed HTML report is written to `htmlcov/index.html` — open it in a
browser to see exactly which lines/branches are missing per file. The
`concurrency = ["greenlet", "thread"]` setting in `pyproject.toml` is required
for accurate measurement, since SQLAlchemy's async ORM calls run user code
inside `greenlet_spawn` and Celery workers spin up per-task event loops in
separate threads — without it, lines that run on every request can be
misreported as uncovered.

## API overview (Phase 1)

| Method & Path | Auth | Description |
|---|---|---|
| POST `/api/v1/auth/register` | – | Create a user account |
| POST `/api/v1/auth/login` | – | OAuth2 password login → access + refresh token |
| POST `/api/v1/auth/refresh` | – | Rotate a refresh token for a new token pair |
| POST `/api/v1/auth/logout` | – | Revoke a refresh token |
| GET `/api/v1/users/me` | user | Current user profile |
| POST `/api/v1/workspaces` | user | Create a workspace (creator becomes owner) |
| GET `/api/v1/workspaces` | user | List workspaces the user belongs to |
| POST `/api/v1/workspaces/join` | user | Join a workspace via invite code |
| GET `/api/v1/workspaces/{id}` | member | Workspace detail |
| PATCH `/api/v1/workspaces/{id}` | admin/owner | Update workspace |
| DELETE `/api/v1/workspaces/{id}` | owner | Delete workspace |
| POST `/api/v1/workspaces/{id}/invite-code/regenerate` | admin/owner | Rotate invite code |
| GET `/api/v1/workspaces/{id}/members` | member | List members |
| PATCH `/api/v1/workspaces/{id}/members/{user_id}` | admin/owner | Change member role |
| DELETE `/api/v1/workspaces/{id}/members/{user_id}` | admin/owner | Remove a member |
| DELETE `/api/v1/workspaces/{id}/members/me` | member | Leave workspace |

## API overview (Phase 2)

| Method & Path | Auth | Description |
|---|---|---|
| POST `/api/v1/workspaces/{id}/monitors` | member | Create a monitor (http/tcp/ping) |
| GET `/api/v1/workspaces/{id}/monitors` | member | List active monitors |
| GET `/api/v1/workspaces/{id}/monitors/{monitor_id}` | member | Monitor detail |
| PATCH `/api/v1/workspaces/{id}/monitors/{monitor_id}` | admin/owner/creator | Update a monitor |
| DELETE `/api/v1/workspaces/{id}/monitors/{monitor_id}` | admin/owner/creator | Soft-delete a monitor |
| GET `/api/v1/workspaces/{id}/audit-logs` | admin/owner | List workspace audit log entries |

Monitor targets are validated per type: HTTP requires an absolute
`http(s)://` URL, TCP requires `host:port`, and PING requires a bare
hostname or IP. Duplicate monitors (same type + target) within a workspace
are rejected with 409. Deleting a monitor sets `deleted_at` and excludes it
from list/get; every create/update/delete is recorded in the workspace's
audit log.

## API overview (Phase 3, slice 1: reliability & incidents)

| Method & Path | Auth | Description |
|---|---|---|
| POST `/api/v1/workspaces/{id}/monitors/{monitor_id}/checks` | member | Record a health check result (success/failure) |
| GET `/api/v1/workspaces/{id}/monitors/{monitor_id}/checks` | member | List a monitor's check history |
| GET `/api/v1/workspaces/{id}/incidents` | member | List workspace incidents |
| GET `/api/v1/workspaces/{id}/incidents/{incident_id}` | member | Incident detail |
| PATCH `/api/v1/workspaces/{id}/incidents/{incident_id}` | admin/owner | Acknowledge (`investigating`) or manually `resolve` an incident |

Each monitor has a configurable `failure_threshold` (default 3). Recording
a `failure` check increments the monitor's `consecutive_failures`; once it
reaches `failure_threshold`, the monitor is marked `down` and an incident
(severity `major`, status `open`) is opened — unless one is already open for
that monitor. Recording a `success` check resets the counter, marks the
monitor `up`, and auto-resolves any open incident. Admins/owners can also
acknowledge (`investigating`) or manually `resolve` an incident; resolved
incidents cannot be transitioned further.

This slice has no scheduler yet — check results must be submitted via the
API above. The scheduler/Celery/Redis execution layer that performs checks
automatically is implemented in slice 2, below.

## Phase 3, slice 2: scheduler & health-check worker

A Celery beat schedule periodically dispatches a check for every active,
non-deleted monitor whose `check_interval_seconds` has elapsed since
`last_checked_at` (or that has never been checked). Each check runs in a
Celery worker task and performs the actual probe:

- **HTTP**: `GET` the target URL; any response under 400 is `success`,
  4xx/5xx or a connection error is `failure`.
- **TCP**: open a TCP connection to `host:port`; success/failure based on
  whether the connection completes.
- **PING**: run the OS `ping` command (one packet) against the target host.

The result (status, response time, error message) is fed into
`CheckService.record_check`, which drives the same failure-counter and
incident lifecycle described above.

### Running the scheduler

```bash
# Worker (executes checks)
celery -A app.core.celery_app worker --loglevel=info

# Beat (dispatches due checks on a schedule)
celery -A app.core.celery_app beat --loglevel=info
```

Both require Redis (`REDIS_URL`, used as the Celery broker and result
backend) and `CELERY_TASK_ALWAYS_EAGER=false`. With Docker Compose, `redis`,
`worker`, and `beat` services are started alongside `db` and `api`.

This machine has no Redis available, so local dev/tests set
`CELERY_TASK_ALWAYS_EAGER=true` in `.env` — Celery tasks run synchronously
in-process rather than via a broker. The dispatch interval is configurable
via `CHECK_DISPATCH_INTERVAL_SECONDS` (default 10s).

## API overview (Phase 5: notification & alerting engine)

| Method & Path | Auth | Description |
|---|---|---|
| POST `/api/v1/workspaces/{id}/alert-rules` | admin/owner | Create an alert rule (`name`, `channel_type`, `target`, `is_enabled`, `min_severity`) |
| GET `/api/v1/workspaces/{id}/alert-rules` | admin/owner | List alert rules for the workspace |
| GET `/api/v1/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Get a single alert rule |
| PATCH `/api/v1/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Update an alert rule |
| DELETE `/api/v1/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Delete an alert rule |
| GET `/api/v1/workspaces/{id}/notifications` | member | List notifications sent/queued for the workspace |
| GET `/api/v1/workspaces/{id}/notifications/{notification_id}` | member | Notification detail |

Each workspace can configure any number of alert rules. Each rule has a
`channel_type` (`webhook` or `email`), a `target` (a webhook URL or an email
address, validated accordingly), an `is_enabled` flag, and an optional
`min_severity` (`minor`/`major`/`critical`) that filters out lower-severity
incidents. When an incident is **opened** (failure-threshold breach) or
**resolved** (auto-recovery or manual resolve),
`NotificationService.evaluate_incident_event` fans out to every enabled rule
whose `min_severity` the incident meets, queuing one `Notification` row per
rule (`status=pending`).

A Celery beat schedule (`dispatch-pending-notifications`, same interval as
`CHECK_DISPATCH_INTERVAL_SECONDS`) finds notifications that are `pending` or
`failed` with `attempts < NOTIFICATION_MAX_ATTEMPTS` (5) and queues a
`deliver_notification` task for each. That task looks up the notification's
`AlertRule` and dispatches by `channel_type`:

- `webhook` — POSTs a JSON payload (`{"event": ..., "incident": {...}}`) to
  the rule's `target` URL via `httpx`.
- `email` — sends a plaintext email to the rule's `target` address via
  `aiosmtplib`, configured through `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/
  `SMTP_PASSWORD`/`SMTP_USE_TLS`/`SMTP_FROM_ADDRESS`.

Either way, the task records `attempts`, `last_attempted_at`,
`response_status_code` (webhook only), `error_message`, and `status` (`sent`
on success, `failed` otherwise), and writes a `notification.sent` or
`notification.failed` audit log entry. `alert_rule.created`,
`alert_rule.updated`, and `alert_rule.deleted` audit events are recorded for
rule changes.

This machine has no SMTP server configured, so `deliver_email` will fail
with a connection error unless `SMTP_*` settings point at a real server;
tests mock `aiosmtplib.send` directly.

## API overview (Phase 6: analytics & reporting engine)

| Method & Path | Auth | Description |
|---|---|---|
| GET `/api/v1/workspaces/{id}/monitors/{monitor_id}/metrics/latency` | member | Latency stats (avg/min/max/p50/p95/p99 response time, ms) over a time range |
| GET `/api/v1/workspaces/{id}/monitors/{monitor_id}/metrics/uptime` | member | Uptime/SLA report (check-based pass ratio + time-based uptime %) over a time range |
| GET `/api/v1/workspaces/{id}/monitors/{monitor_id}/metrics/snapshots` | member | List persisted daily `MetricSnapshot` rows, optionally filtered by `start`/`end` date |
| GET `/api/v1/workspaces/{id}/dashboard` | member | Workspace-wide monitor/incident status counts and trailing-24h check stats |

`latency` and `uptime` accept optional `start`/`end` ISO-8601 query params;
if either is omitted, both default to the trailing 24 hours. `end` must be
after `start` and the range cannot exceed 90 days, or the request is
rejected with 422.

`uptime` reports two complementary SLA measures over `[start, end)`:

- **check-based** — `check_pass_ratio` is
  `successful_checks / (successful_checks + failed_checks) * 100`.
- **time-based** — `uptime_percentage` is derived from
  `total_downtime_seconds`, the summed overlap of the monitor's incidents'
  `[created_at, resolved_at or now)` windows with `[start, end)`.

### Scheduled daily aggregation

A Celery beat schedule (`aggregate-daily-metrics`, interval
`METRICS_AGGREGATION_INTERVAL_SECONDS`, default 3600s) runs
`dispatch_metric_aggregation`, which queues an `aggregate_monitor_metrics`
task for every active, non-deleted monitor. Each task computes the previous
UTC day's check counts, latency stats, and uptime/downtime, then upserts a
`MetricSnapshot` row keyed on `(monitor_id, period_type, period_start)` —
re-running for the same monitor/day updates the existing row instead of
duplicating it. The `snapshots` endpoint reads these persisted rows, while
`latency`, `uptime`, and the dashboard compute live from `checks` and
`incidents`.

## API overview (Phase 7: audit logging & compliance)

| Method & Path | Auth | Description |
|---|---|---|
| GET `/api/v1/workspaces/{id}/audit-logs` | admin/owner | List all audit log entries for the workspace (newest first) |
| GET `/api/v1/workspaces/{id}/audit-logs/search` | admin/owner | Search/filter audit logs by `user_id`, `action`, `entity_type`, `start`/`end` date range, with `limit`/`offset` pagination |
| GET `/api/v1/workspaces/{id}/audit-logs/{audit_log_id}` | admin/owner | Get a single audit log entry by id |

Every `AuditLogRead` record has: `id`, `workspace_id`, `user_id` (`null` for
system-generated events), `action`, `entity_type`, `entity_id`, `old_values`,
`new_values` (both JSON snapshots, either may be `null`), `ip_address`,
`user_agent`, and `created_at`. The audit log API is **read-only** —
`PATCH`/`DELETE` on any audit-log route return 405, since entries must remain
immutable for compliance purposes.

The following actions are recorded automatically:

- **Monitor**: `monitor.created`, `monitor.updated`, `monitor.deleted`,
  and — when a PATCH toggles `is_active` — an additional
  `monitor.enabled`/`monitor.disabled` event.
- **Incident**: `incident.created` and `incident.resolved` (system-generated,
  `user_id` is `null`, `new_values.reason = "monitor_recovered"`) when the
  failure-threshold/recovery lifecycle opens or auto-resolves an incident;
  `incident.acknowledged` and `incident.resolved`
  (`new_values.reason = "manual"`) when an admin/owner manually transitions
  an incident.
- **Alert Rule**: `alert_rule.created`, `alert_rule.updated`,
  `alert_rule.deleted`.
- **Notification**: `notification.sent` / `notification.failed`, recorded by
  the delivery worker (`user_id` is `null`).
- **Workspace**: `workspace.updated` (diff of changed fields).
- **Membership**: `member.added` (on join, `entity_type="user"`,
  `new_values={"role": ...}`) and `member.removed` (on admin-initiated
  removal or self-leave, `old_values={"role": ...}`).

For mutations made via the HTTP API, `ip_address` and `user_agent` are
captured from the request (`AuditContextDep` in `app/api/deps.py`).
System-generated events (auto incident open/resolve, notification delivery)
have `user_id`, `ip_address`, and `user_agent` all `null`.

## Out of scope

Slack, Discord, Microsoft Teams, and SMS notifications, plus AI-driven
analysis, forecasting, and anomaly detection, SIEM integrations, compliance
exports, and external log shipping — reserved for future phases. Phase 8
(platform optimization & scalability) is next.

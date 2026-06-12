# API Reference

Base path: `{API_V1_PREFIX}` (default `/api/v1`). Interactive docs at
`/docs` (Swagger UI) and `/api/v1/openapi.json` (OpenAPI schema).

**Auth column legend:**
- `–` — no authentication required
- `user` — valid JWT access token or `X-API-Key`
- `member` / `admin/owner` / `owner` — workspace role required, in addition
  to being authenticated (RBAC via `app/api/deps.py`)

## Auth

| Method & Path | Auth | Description |
|---|---|---|
| POST `/auth/register` | – | Create a user account |
| POST `/auth/login` | – | OAuth2 password login (`username` = email) → access + refresh token pair |
| POST `/auth/refresh` | – | Rotate a refresh token (`jti`-based) for a new token pair |
| POST `/auth/logout` | – | Revoke a single refresh token; if an access token is also presented, it's added to the Redis denylist |
| POST `/auth/logout-all` | user | Revoke **all** of the current user's refresh tokens and denylist the presented access token |

## Users

| Method & Path | Auth | Description |
|---|---|---|
| GET `/users/me` | user | Current user profile |

## Workspaces & Members

| Method & Path | Auth | Description |
|---|---|---|
| POST `/workspaces` | user | Create a workspace (creator becomes `owner`) |
| GET `/workspaces` | user | List workspaces the current user belongs to |
| POST `/workspaces/join` | user | Join a workspace via invite code (becomes `member`) |
| GET `/workspaces/{id}` | member | Workspace detail |
| PATCH `/workspaces/{id}` | admin/owner | Update workspace (name/description) |
| DELETE `/workspaces/{id}` | owner | Delete a workspace and all its data |
| POST `/workspaces/{id}/invite-code/regenerate` | admin/owner | Rotate the workspace invite code |
| GET `/workspaces/{id}/members` | member | List workspace members and roles |
| PATCH `/workspaces/{id}/members/{user_id}` | admin/owner | Change a member's role |
| DELETE `/workspaces/{id}/members/{user_id}` | admin/owner | Remove a member from the workspace |
| DELETE `/workspaces/{id}/members/me` | member | Leave the workspace |

## Monitors

| Method & Path | Auth | Description |
|---|---|---|
| POST `/workspaces/{id}/monitors` | member | Create a monitor (`monitor_type`: `http`/`tcp`/`ping`) |
| GET `/workspaces/{id}/monitors` | member | List active (non-deleted) monitors |
| GET `/workspaces/{id}/monitors/{monitor_id}` | member | Monitor detail (incl. `status`, `consecutive_failures`) |
| PATCH `/workspaces/{id}/monitors/{monitor_id}` | admin/owner/creator | Update a monitor |
| DELETE `/workspaces/{id}/monitors/{monitor_id}` | admin/owner/creator | Soft-delete a monitor (`deleted_at` set) |

Target validation is per-type: HTTP requires an absolute `http(s)://` URL,
TCP requires `host:port`, PING requires a bare hostname/IP. Duplicate
monitors (same `monitor_type` + `target`) within a workspace return `409`.
Every create/update/delete is recorded in the audit log, including
`monitor.enabled`/`monitor.disabled` when a PATCH toggles `is_active`.

## Checks

| Method & Path | Auth | Description |
|---|---|---|
| POST `/workspaces/{id}/monitors/{monitor_id}/checks` | member | Record a check result (`success`/`failure`) — also used by the Celery worker |
| GET `/workspaces/{id}/monitors/{monitor_id}/checks` | member | List a monitor's check history (newest first) |

Recording a `failure` increments `consecutive_failures`; reaching
`failure_threshold` (default 3) marks the monitor `down` and opens an
`Incident` (unless one is already open). A `success` resets the counter,
marks the monitor `up`, and auto-resolves any open incident.

## Incidents

| Method & Path | Auth | Description |
|---|---|---|
| GET `/workspaces/{id}/incidents` | member | List workspace incidents (newest first) |
| GET `/workspaces/{id}/incidents/{incident_id}` | member | Incident detail |
| PATCH `/workspaces/{id}/incidents/{incident_id}` | admin/owner | Acknowledge (`investigating`) or manually `resolve` |

Resolved incidents cannot be transitioned further. Manual resolution sets
`new_values.reason = "manual"` in the audit log; automatic resolution sets
`reason = "monitor_recovered"`.

## Alerting (Alert Rules & Notifications)

| Method & Path | Auth | Description |
|---|---|---|
| POST `/workspaces/{id}/alert-rules` | admin/owner | Create an alert rule (`name`, `channel_type`: `webhook`/`email`, `target`, `is_enabled`, `min_severity`) |
| GET `/workspaces/{id}/alert-rules` | admin/owner | List alert rules |
| GET `/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Get a single alert rule |
| PATCH `/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Update an alert rule |
| DELETE `/workspaces/{id}/alert-rules/{rule_id}` | admin/owner | Delete an alert rule |
| GET `/workspaces/{id}/notifications` | member | List notifications sent/queued for the workspace |
| GET `/workspaces/{id}/notifications/{notification_id}` | member | Notification detail (status, attempts, error) |

On incident open/resolve, `evaluate_incident_event` queues one
`Notification` (`status=pending`) per enabled `AlertRule` whose
`min_severity` the incident meets. A Beat job retries `pending`/`failed`
notifications (up to `NOTIFICATION_MAX_ATTEMPTS=5`), delivering via
`httpx` (webhook) or `aiosmtplib` (email) and recording
`attempts`/`last_attempted_at`/`response_status_code`/`error_message`/`status`.

## Metrics & Dashboard

| Method & Path | Auth | Description |
|---|---|---|
| GET `/workspaces/{id}/monitors/{monitor_id}/metrics/latency` | member | Latency stats (avg/min/max/p50/p95/p99 ms) over `start`/`end` |
| GET `/workspaces/{id}/monitors/{monitor_id}/metrics/uptime` | member | Uptime/SLA report (check-based + time-based) over `start`/`end` |
| GET `/workspaces/{id}/monitors/{monitor_id}/metrics/snapshots` | member | List persisted daily `MetricSnapshot`s, optional `start`/`end` filter |
| GET `/workspaces/{id}/dashboard` | member | Workspace-wide monitor/incident status counts + trailing-24h check stats |

`latency`/`uptime` accept optional ISO-8601 `start`/`end` query params; if
either is omitted, both default to the trailing 24 hours. `end` must be
after `start` and the range cannot exceed 90 days (`422` otherwise).
`uptime_percentage` is time-based (downtime = overlap of incident windows
with `[start, end)`); `check_pass_ratio` is check-based
(`successful / (successful + failed) * 100`).

## Audit Logs

| Method & Path | Auth | Description |
|---|---|---|
| GET `/workspaces/{id}/audit-logs` | admin/owner | List all audit log entries (newest first) |
| GET `/workspaces/{id}/audit-logs/search` | admin/owner | Filter by `user_id`, `action`, `entity_type`, `start`/`end`, with `limit` (1-200, default 50) / `offset` pagination |
| GET `/workspaces/{id}/audit-logs/{audit_log_id}` | admin/owner | Get a single audit log entry |

The audit log API is **read-only** — there are no `PATCH`/`DELETE` routes,
since entries must remain immutable for compliance. Each entry has
`old_values`/`new_values` JSON diffs, `ip_address`, `user_agent`, and
`user_id` (`null` for system-generated events such as auto incident
open/resolve and notification delivery).

## API Keys

| Method & Path | Auth | Description |
|---|---|---|
| POST `/workspaces/{id}/api-keys` | admin/owner | Create an API key — the **full key is returned only once** (response includes `ApiKeyCreated`, only `key_prefix` + `hashed_key` are stored) |
| GET `/workspaces/{id}/api-keys` | admin/owner | List API keys (prefix, name, `last_used_at`, `revoked_at`) |
| DELETE `/workspaces/{id}/api-keys/{api_key_id}` | admin/owner | Revoke an API key |

API keys authenticate via the `X-API-Key` header as an alternative to a
JWT bearer token, scoped to the workspace that created them.

## Health

| Method & Path | Auth | Description |
|---|---|---|
| GET `/health` | – | Liveness check, returns `{"status": "ok"}` (not under `/api/v1`) |

# Interview Notes: Design Decisions

Short, defensible answers to "why did you build it this way?" — each
grounded in the actual implementation, not just theory.

## Why PostgreSQL?

Sentinel's data is fundamentally **relational and transactional**:
workspaces own monitors, monitors own checks/incidents, incidents fan out
to notifications, and almost every table carries a `workspace_id` foreign
key that must stay consistent. Postgres gives:

- **ACID transactions** for multi-step writes — e.g. recording a check,
  updating `monitors.consecutive_failures`/`status`, and opening an
  `Incident` all happen in one transaction (`CheckService.record_check`),
  so a crash can't leave a monitor `down` with no incident or vice versa.
- **Rich querying for analytics** — `MetricsService` uses
  `percentile_cont` window functions directly in SQL to compute p50/p95/p99
  latency, rather than pulling rows into Python.
- **JSONB** for `audit_logs.old_values`/`new_values` — flexible,
  per-entity diff payloads without a sprawling EAV schema, while still
  being queryable.
- **Partial/composite indexes** — e.g. the soft-delete unique constraint
  (`uq_monitors_workspace_id_monitor_type_target WHERE deleted_at IS NULL`)
  enforces "no duplicate active monitor" at the database layer, not just
  in application code.

## Why Redis?

Redis is used for everything that is **fast, ephemeral, or naturally
queue-shaped** — deliberately kept separate from Postgres so the source of
truth never depends on it:

- **Celery broker + result backend** for background jobs (see "Why
  Celery?").
- **Application cache** (`app/services/cache.py`) for read-heavy endpoints
  like the workspace dashboard.
- **Rate limiting** (`RateLimitMiddleware`) — fixed-window counters per
  user/IP, cheap atomic `INCR`+`EXPIRE`.
- **JWT access-token denylist** — logout/`logout-all` add the token's
  claims to Redis with a TTL matching the token's remaining lifetime, so
  revocation is instant without hitting Postgres on every request.
- **Login-failure counters** for account lockout.

Every Redis call is wrapped to catch `RedisError` and **fail open** — if
Redis is unreachable, caching/rate-limiting/denylist checks are skipped and
the request still succeeds against Postgres. This means Redis is a
performance/security *enhancement*, never a hard dependency for
correctness — a deliberate availability trade-off (a revoked access token
might work for a few extra seconds during a Redis outage, but the API
doesn't go down).

## Why Celery?

Health checks, alert delivery, and metric aggregation are all **slow,
external-I/O-bound, and need retries/scheduling** — exactly the wrong
things to do inline in a request handler:

- **Scheduling** — Celery Beat replaces a cron job + script with
  in-process, version-controlled schedules (`app/core/celery_app.py`,
  `beat_schedule`): `dispatch_due_checks`,
  `dispatch_pending_notifications`, and the daily
  `aggregate_monitor_metrics` dispatch.
- **Decoupling** — a slow webhook/SMTP call or a TCP probe with a 10s
  timeout never blocks an API request; it runs in a worker process and the
  result is written back via the same service layer
  (`CheckService.record_check`).
- **Retries built in** — failed notifications stay `pending`/`failed` with
  an `attempts` counter and are picked up again by the next Beat tick (up
  to `NOTIFICATION_MAX_ATTEMPTS`), without custom retry-loop code.
- **Testability** — `CELERY_TASK_ALWAYS_EAGER=true` runs the exact same
  task functions synchronously, in-process, with no broker. Tests and CI
  exercise the real `_perform_check`/`deliver_notification` code paths,
  not mocks of "the worker."

## Why Multi-Tenant Architecture?

Sentinel is built as a **shared-schema, row-level multi-tenant** system:
one database, one set of tables, and a `workspace_id` foreign key on
almost every domain table (monitors, incidents, alert rules,
notifications, audit logs, API keys, metric snapshots — see
[`docs/ER_DIAGRAM.md`](ER_DIAGRAM.md)).

- **Why shared schema over DB-per-tenant**: a monitoring SaaS has many
  small tenants (workspaces) — provisioning a database per workspace would
  multiply operational overhead (migrations, connections, backups) for no
  benefit at this scale, and cross-workspace analytics/admin tooling would
  need fan-out queries.
- **Isolation is enforced at the repository layer** — every repository
  method that reads/writes domain data takes a `workspace_id` and filters
  on it, and every endpoint resolves a `WorkspaceMembership` dependency
  first (`app/api/deps.py`), so a user literally cannot construct a query
  that crosses workspace boundaries.
- **It's what makes RBAC meaningful** — roles (`owner`/`admin`/`member`)
  are defined *per workspace* via `WorkspaceMember`, not globally, so the
  same user can be an `owner` of one workspace and a `member` of another.

## Why RBAC?

Three roles — `owner`, `admin`, `member` — cover the realistic permission
boundaries for an incident-management tool without over-engineering a
generic permissions system:

- **`member`** — day-to-day usage: create/view monitors, view incidents,
  view dashboards/metrics, record check results.
- **`admin`/`owner`** — anything that changes shared configuration or
  exposes sensitive data: alert rules (where alerts go), API keys (who can
  call the API programmatically), audit logs (who-did-what), member roles.
- **`owner`** — workspace deletion; the one truly destructive,
  irreversible action.

Enforcement is **declarative**, via typed FastAPI dependencies
(`WorkspaceMembership`, `AdminOrOwner`, `OwnerOnly` in `app/api/deps.py`)
that resolve "does this user belong to this workspace, and with what
role?" once per request and raise `PermissionDeniedError` (→ `403`)
otherwise. Handlers never write `if role == "admin"` checks themselves —
the dependency *is* the check, so it can't be forgotten on a new endpoint
and it's covered by a single set of tests.

## Why Incident Thresholds?

A single failed check is usually noise (a transient network blip, a
deploy-time restart), not an incident — paging someone for every failure
trains them to ignore alerts. `failure_threshold` (per-monitor, default 3)
is Sentinel's answer to **alert fatigue vs. detection speed**:

- `consecutive_failures` increments on each `failure` check and **resets
  to zero on any `success`** — only a *sustained* run of failures opens an
  incident, so flapping services don't spam alerts.
- The threshold is **configurable per monitor** — a critical
  payment-gateway health check might use `failure_threshold=1` (page
  immediately), while a low-priority internal tool might use `5` (tolerate
  more noise before paging).
- Resolution is symmetric and automatic: one `success` after an open
  incident flips the monitor back to `up` and resolves the incident
  (`reason="monitor_recovered"`) — no manual "close the ticket" step for
  the common case, while admins can still `acknowledge`/manually `resolve`
  for cases that need human follow-up.

This turns "is this thing up?" from a binary per-check fact into a
**stateful incident lifecycle**, which is what the Notification Engine
actually fans out on (incident opened/resolved — not every check).

## Why Caching?

Sentinel caches **derived, read-heavy, slightly-stale-tolerant** data —
not transactional state:

- The workspace dashboard aggregates counts across monitors/incidents/
  checks; recomputing it on every poll from a monitoring UI is wasted
  Postgres load for data that changes on the order of seconds, not
  milliseconds.
- The cache is **read-through with a short TTL** and every write path that
  could affect cached data still writes Postgres first — Redis is never
  the source of truth, so a cache miss or a Redis outage just means "go
  compute it from Postgres," not "the data is wrong."
- Combined with the fail-open Redis pattern (see "Why Redis?"), caching is
  purely an optimization: correctness doesn't regress if it's disabled or
  unavailable, only latency/DB load does.

## Why Audit Logs?

An incident-management platform is itself part of an organization's
compliance and on-call story — "who changed this alert rule right before
we stopped getting paged?" needs to be answerable.

- **Immutable by design** — the audit log API exposes only `GET` routes;
  there is no update/delete path, so the trail can't be tampered with after
  the fact.
- **Before/after diffs** (`old_values`/`new_values` JSONB) — not just "X
  updated the monitor," but exactly which fields changed and to what,
  which is what makes an audit log useful for debugging, not just
  compliance.
- **Redaction** — fields matching
  `password|secret|token|api_key|hashed_key|^key$` are stripped before
  storage, so the audit trail itself can't become a credential leak.
- **System events included** — automatic incident open/resolve and
  notification delivery write audit entries with `user_id=null`,
  distinguishing "the system did this because a threshold was crossed"
  from "an admin did this." Without this, the audit log would have gaps
  around the most operationally important events.
- **Request context captured** (`ip_address`, `user_agent` via
  `AuditContextDep`) — useful for security investigations (e.g. "was this
  change made from an unexpected location?").

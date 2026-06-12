# Resume Bullet Points

Pick 3-5 depending on the role. Each is self-contained and quantifies the
engineering decision, not just the technology used.

## Project summary (one-liner)

> Sentinel — a multi-tenant observability and incident-management API
> (FastAPI, PostgreSQL, Redis, Celery) with automated health checks,
> threshold-based incident detection, alert delivery, analytics, and a
> full audit trail; CI/CD via GitHub Actions with a 95% coverage gate.

## Distributed Monitoring

- Built a Celery-beat-driven monitoring engine that schedules and executes
  HTTP, TCP, and PING health checks per monitor on independent intervals,
  decoupling probe execution from the request/response cycle.
- Implemented three protocol-specific health checkers (HTTP status-code
  validation, raw TCP connect, OS-level ping) behind a single async
  interface with bounded timeouts to prevent slow targets from blocking
  worker capacity.

## Incident Management

- Designed a stateful incident lifecycle driven by a configurable
  per-monitor failure threshold — consecutive failures automatically open
  an incident, and the next successful check auto-resolves it, reducing
  alert noise from transient failures.
- Added manual acknowledge/resolve workflows for admins on top of the
  automatic lifecycle, with every transition recorded in an immutable
  audit log including the reason (`automatic` vs. `manual`).

## Multi-Tenant Architecture

- Architected a shared-schema multi-tenant data model where every domain
  table is scoped by `workspace_id`, with isolation enforced at the
  repository layer so cross-tenant data access is structurally impossible.
- Implemented role-based access control (owner/admin/member) per
  workspace via reusable FastAPI dependencies, enforcing authorization
  declaratively across 12 routers and 40+ endpoints.

## Background Processing

- Built an async notification pipeline (Celery + Redis) that fans out
  incident open/resolve events to per-workspace alert rules (webhook via
  `httpx`, email via `aiosmtplib`), with retry tracking and delivery-status
  audit logging.
- Implemented a daily metrics-aggregation job that upserts idempotent
  `MetricSnapshot` rows per monitor, enabling historical uptime/latency
  reporting without re-scanning raw check history.
- Used `CELERY_TASK_ALWAYS_EAGER` to run the identical task code
  synchronously in tests/CI, achieving full coverage of worker logic
  without a message broker dependency in the test environment.

## Caching

- Added a Redis-backed read-through cache for hot read endpoints (e.g.
  workspace dashboard) with a fail-open degradation path, so a Redis
  outage degrades latency, not correctness.
- Implemented Postgres window-function (`percentile_cont`) queries for
  on-demand p50/p95/p99 latency and uptime/SLA reporting over arbitrary
  date ranges.

## Security

- Implemented JWT auth with refresh-token rotation, single-session and
  all-sessions revocation (logout / logout-all) backed by a Redis
  access-token denylist, and per-workspace API keys for service-to-service
  auth.
- Added defense-in-depth middleware: fixed-window rate limiting (stricter
  on auth endpoints), account lockout after repeated failed logins,
  request-size limits, and security headers (CSP, HSTS, X-Frame-Options).
- Built an audit-logging system capturing before/after diffs, IP address,
  and user agent for every mutation, with automatic redaction of
  credential-like fields before storage.

## CI/CD

- Designed a GitHub Actions pipeline with five independent jobs (lint,
  type-check, test + coverage, Docker build validation, dependency/secret
  scanning) gating merges to `main` via branch protection.
- Enforced a 95% line+branch coverage threshold across an async codebase
  (SQLAlchemy async ORM + Celery), configuring coverage to track execution
  across `greenlet` and `thread` contexts for accurate measurement.
- Diagnosed and fixed a CI-only test hang caused by a Python 3.12
  `asyncio` behavior change, adding `pytest-timeout` as a regression
  safety net.

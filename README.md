# Sentinel

[![CI](https://github.com/sarangs1621/Sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/sarangs1621/Sentinel/actions/workflows/ci.yml)

Sentinel is a production-grade observability and incident management
platform built using **FastAPI**, **PostgreSQL**, **Redis**, and **Celery**.

It lets a team register HTTP/TCP/PING monitors for the services they care
about, automatically probes them on a schedule, opens and resolves
incidents based on a configurable failure threshold, fans alerts out to
webhook/email channels, and reports latency/uptime SLAs — all scoped to
per-workspace tenants with role-based access control and a full audit
trail.

## Documentation

| Doc | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System diagram, background-job pipeline (Monitoring → Incident → Notification → Analytics), middleware stack, code layout |
| [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) | Full database schema as a Mermaid ER diagram, with design-decision notes |
| [`docs/API.md`](docs/API.md) | Full REST API reference, grouped by resource |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Environment variables, Docker setup, migrations, worker startup, health checks, troubleshooting |
| [`docs/INTERVIEW_NOTES.md`](docs/INTERVIEW_NOTES.md) | "Why X?" design-decision write-ups (Postgres, Redis, Celery, multi-tenancy, RBAC, thresholds, caching, audit logs) |
| [`docs/RESUME_BULLETS.md`](docs/RESUME_BULLETS.md) | Resume-ready bullet points describing this project |

## Features

- **Authentication** — JWT access/refresh tokens with refresh-token
  rotation and revocation, Redis-backed access-token denylist (logout),
  account lockout after repeated failed logins, and per-workspace API keys
  for service-to-service access.
- **RBAC** — every workspace member has a role (`owner` / `admin` /
  `member`); endpoints enforce role checks via FastAPI dependencies.
- **Workspace Management** — multi-tenant workspaces with invite-code
  joining, member role management, and self-leave.
- **Monitor Management** — CRUD for HTTP/TCP/PING monitors with per-type
  target validation, duplicate detection, and soft delete.
- **Monitoring Engine** — Celery-beat-driven scheduler dispatches due
  checks; a worker probes each target (HTTP GET, TCP connect, OS ping) and
  records the result.
- **Incident Management** — a configurable `failure_threshold` per monitor
  drives automatic incident open/resolve, plus manual
  acknowledge/resolve by admins/owners.
- **Alerting** — per-workspace alert rules (webhook or email,
  severity-filtered) with async, retrying notification delivery.
- **Analytics** — on-demand latency percentiles (p50/p95/p99) and
  check-based + time-based uptime/SLA reporting, plus a daily aggregation
  job that persists historical `MetricSnapshot`s.
- **Audit Logs** — immutable, searchable log of every mutation with
  before/after diffs, IP address, and user agent; sensitive fields are
  redacted automatically.
- **Caching** — Redis-backed read-through cache for hot endpoints with a
  fail-open degradation path if Redis is unavailable.
- **Rate Limiting** — fixed-window limiter (per-user or per-IP), with
  stricter limits on auth endpoints, plus security-headers middleware
  (CSP, HSTS, X-Frame-Options, request-size limits).
- **CI/CD** — GitHub Actions pipeline with lint (ruff), type checking
  (mypy), tests + coverage gate (pytest, 95% minimum), Docker build
  validation, and security scanning (pip-audit, detect-secrets), with
  branch protection on `main`.

## Architecture Overview

```
Client ──HTTPS──> FastAPI ──SQLAlchemy (async)──> PostgreSQL
                     │
                     ├──cache / rate-limit / denylist──> Redis
                     │
                     └──enqueue──> Redis ──> Celery Beat + Workers
                                                  │
                                   Monitoring Engine (HTTP/TCP/PING checks)
                                                  │
                                          Incident Engine
                                    (failure threshold, open/resolve)
                                                  │
                                        Notification Engine
                                       (webhook / email delivery)

                              Analytics Engine ──> daily MetricSnapshots
                              Audit Engine ──> immutable AuditLog rows
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full Mermaid
diagrams and component-by-component breakdown, and
[`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) for the database schema.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, Repository + Service layer architecture |
| Database | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic migrations |
| Caching | Redis 7 (application cache, rate limiting, JWT denylist) |
| Workers | Celery (beat + worker), Redis broker/result backend |
| Infrastructure | Docker, multi-stage Dockerfile, Docker Compose (db/redis/api/worker/beat) |
| Testing | Pytest, pytest-asyncio, respx, 95% coverage gate |
| CI/CD | GitHub Actions (lint, type check, test+coverage, Docker build, security scan), branch protection |

## Local Setup

### Requirements

- Docker + Docker Compose (recommended), **or** Python 3.12 + a local
  PostgreSQL instance for running without Docker.

### Environment Variables

Copy the template and adjust as needed:

```bash
cp .env.example .env
```

Key variables (see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full
reference):

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | — (required) | JWT signing secret (≥32 chars outside `testing`) |
| `DATABASE_URL` | — (required) | `postgresql+asyncpg://...` connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker/result backend + cache |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | `true` runs Celery tasks in-process (no broker needed) |
| `BACKEND_CORS_ORIGINS` | `[]` | Explicit allow-list of CORS origins (never `*`) |
| `CHECK_DISPATCH_INTERVAL_SECONDS` | `10` | How often Beat looks for due monitor checks |
| `RATE_LIMIT_ENABLED` | `true` | Toggle the rate-limit middleware |

### Docker Commands

```bash
docker compose up -d
```

This starts `db` (Postgres), `redis`, `api`, `worker`, and `beat`. The
`api` container runs `alembic upgrade head` automatically before starting
`uvicorn`.

### Run Instructions (without Docker)

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Run the worker and beat scheduler in separate terminals (requires Redis,
`CELERY_TASK_ALWAYS_EAGER=false`):

```bash
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
```

### Tests

```bash
createdb sentinel_test   # or via psql/pgAdmin
pytest -v
```

## API Documentation

Once the app is running:

- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI schema**: http://localhost:8000/api/v1/openapi.json
- **Health check**: http://localhost:8000/health

For a full endpoint reference grouped by resource (auth, workspaces,
monitors, checks, incidents, alert rules, notifications, metrics, audit
logs, API keys), see [`docs/API.md`](docs/API.md).

## Portfolio Assets

- **Architecture diagram** — [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
  (Mermaid, renders on GitHub)
- **Database ER diagram** — [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md)
  (Mermaid, renders on GitHub)
- **Swagger UI** — ![Swagger UI](docs/screenshots/swagger-ui.png)
- **Sample API call** — ![API response](docs/screenshots/api-response.png)
- **Local deployment** — ![Docker Compose](docs/screenshots/docker-compose.png)
- **CI/CD pipeline** — ![CI pipeline](docs/screenshots/ci-pipeline.png)

The four screenshots above are captured locally (not generated by this
repo) — see [`docs/screenshots/README.md`](docs/screenshots/README.md) for
the exact steps and filenames.

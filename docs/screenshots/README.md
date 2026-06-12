# Portfolio Screenshots

This directory holds the screenshot assets referenced from the main
[`README.md`](../../README.md) "Portfolio Assets" section. They aren't
generated automatically (Sentinel must be running locally, and capturing a
screen isn't something this environment can do) — capture each one
following the steps below, save it with the exact filename listed, and the
links in the root README will resolve.

| Filename | What to capture | How |
|---|---|---|
| `swagger-ui.png` | Swagger UI endpoint list | `docker compose up -d` (or `uvicorn app.main:app --reload`), open `http://localhost:8000/docs`, screenshot the full page showing the grouped endpoint tags (auth, workspaces, monitors, incidents, alerting, metrics, audit-logs, api-keys) |
| `api-response.png` | A live API call and response | In Swagger UI, expand `POST /api/v1/auth/register` or `GET /api/v1/workspaces/{id}/dashboard`, click **Try it out** → **Execute**, screenshot the request + response panel |
| `docker-compose.png` | Local deployment running | After `docker compose up -d`, run `docker compose ps` in a terminal — screenshot showing all five services (`db`, `redis`, `api`, `worker`, `beat`) as `healthy`/`running` |
| `ci-pipeline.png` | CI/CD pipeline | Open the [Actions tab](https://github.com/sarangs1621/Sentinel/actions) on a recent successful run, screenshot the job graph showing `Lint`, `Type check`, `Test & coverage`, `Docker build validation`, and `Security checks` |

## Architecture & ER diagrams

The architecture and ER diagrams are **not screenshots** — they're
Mermaid diagrams checked into source so they stay in sync with the code
and render directly on GitHub:

- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`docs/ER_DIAGRAM.md`](../ER_DIAGRAM.md)

If you want PNG/SVG exports of these for a slide deck, render them with the
[Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) (`mmdc -i
../ARCHITECTURE.md -o architecture.png`, and likewise `mmdc -i
../ER_DIAGRAM.md -o er-diagram.png`, when run from `docs/screenshots/`) or
paste the diagram source into the
[Mermaid Live Editor](https://mermaid.live) and export.

# Mission AI Possible Challenge Analytics Tool

Mission AI Possible generates dozens of AI "missions" each week. This repository bundles the services, dashboard, and utilities that turn OpenWebUI telemetry plus credit-award files into an auditable leaderboard, chat browser, and campaign scoring surface.

## Highlights
- **Full-stack analytics** - FastAPI aggregates OpenWebUI chats/models/users, persists them to SQLite/Postgres, and exposes mission summaries plus reload logs.
- **Interactive dashboard** - Next.js 14 UI ships four high-level tabs (Overview, Challenge Results, All Chats, Missions) with filter chips, exports, and chat previews.
- **Campaign credit tracking** - Upload the official `SubmittedActivityList.csv` to compare awarded credits vs. mission completions and identify gaps.
- **Pluggable auth** - Local accounts by default with optional Microsoft Entra ID OAuth support (`AUTH_MODE`), email verification, and admin approval workflows.
- **Dev ergonomics** - Makefile shortcuts, Docker Compose, helper scripts, sample data, and documented docs/ guides keep local setup predictable.

## Architecture at a Glance

| Layer | Tech | Responsibilities |
| --- | --- | --- |
| Data ingest | `backend/app/services/mission_analyzer.py` | Pull chat/model/user exports from OpenWebUI (API or JSON files), detect missions, normalize metadata (weeks, points, difficulty). |
| Persistence | SQLAlchemy + Alembic | Store chats, models, users, reload logs, campaign ranks in SQLite (`data/mission_dashboard.sqlite`) or Postgres. |
| API | FastAPI (`backend/app/main.py`) | Auth/session management, `/dashboard` payloads, `/admin/db/*` reload endpoints, campaign upload APIs, setup bootstrap. |
| Frontend | Next.js 14 + Tailwind (`frontend/...`) | Mission dashboard, admin console, auth flows, campaign leaderboard, CSV uploader, toast UX. |
| Tooling | `scripts/`, `Makefile`, `docs/` | CLI automation, credit comparison report, deployment references, ops runbooks. |

## Repository Layout
- `backend/` - FastAPI app, auth subsystem, campaign service, SQLAlchemy models, Alembic migrations, pytest suite.
- `frontend/` - Next.js application with server components, middleware enforcement, Tailwind styling, Vitest setup.
- `data/` - Runtime databases plus required CSV inputs. Auto-generated artifacts (SQLite db, chat exports) live here.
- `sample_data/` - Small OpenWebUI snapshots for offline development or demos when the API is unavailable.
- `scripts/` - Bootstrap helpers (`setup_env.sh`, `run_analyzer.sh`) and the `missing_credit_report.py` comparison workflow.
- `docs/` - Admin and deployment guides, "What's New", mission briefs, and other reference material.
- `exports/` - Target directory for generated Excel reports (git-ignored).

## Prerequisites
- Python 3.11+
- Node.js 18.17+ (npm included)
- Docker + Docker Compose (optional but recommended)
- Access to an OpenWebUI instance (hostname + API key) **or** exported chat/model JSON files saved under `data/`

## Setup

1. **Clone and enter the repo**
   ```bash
   git clone https://github.com/mission-ai-possible/mission-ai-possible-challenge-analytics-tool.git
   cd mission-ai-possible-challenge-analytics-tool
   ```

2. **Create a `.env` file**
   ```bash
   cp .env.example .env
   ```
   Fill in the OpenWebUI variables plus any auth or database overrides (examples below).

3. **Install dependencies (once)**
   ```bash
   make install        # creates .venv + installs npm packages
   ```
   If Docker is your primary workflow, `npm install` is handled automatically when the container starts (`make up`).

### Key environment variables

| Variable | Purpose |
| --- | --- |
| `BACKEND_PORT` / `FRONTEND_PORT` | Keeps Uvicorn, Next.js dev server, and Docker port bindings in sync (defaults 5098/5099 in `.env.example`). |
| `DB_ENGINE` | `sqlite` (default) writes to `data/mission_dashboard.sqlite`. Set `postgres` and populate `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD` to run against Postgres. |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-facing API origin, usually `http://localhost:${BACKEND_PORT}`. |
| `API_BASE_URL` | Server-side API base; Docker services use `http://backend:${BACKEND_PORT}`. |
| `OPEN_WEBUI_HOSTNAME` / `OPEN_WEBUI_API_KEY` | Required for live data reloads from OpenWebUI. Without these the backend falls back to cached/sample files. |
| `MISSION_DATA_FILE` / `MISSION_USER_NAMES_FILE` | Optional overrides that point to exported JSON/CSV assets in `data/`. By default the latest matching file is auto-discovered. |
| `AUTH_MODE` | `DEFAULT` (local accounts only), `HYBRID` (local + Microsoft OAuth), or `OAUTH` (Microsoft only). |
| `SESSION_SECRET`, `SESSION_COOKIE_*` | Secure the FastAPI session + refresh tokens. Update them before production use. |
| `OAUTH_*` & `SMTP_*` | Microsoft Entra ID credentials and SMTP settings for password reset / verification emails. |

> **Database migrations** - Alembic runs automatically on FastAPI startup, but when switching engines run `cd backend && alembic upgrade head` to seed tables before launching the API.

## Getting Data into the Dashboard

- **Live OpenWebUI fetches** - With `OPEN_WEBUI_*` configured, the backend hits `/api/v1/chats`, `/api/v1/models`, and `/api/v1/users` to refresh data. Use the admin console or `POST /admin/db/reload/*` to trigger updates.
- **Offline mode** - Drop exports into `data/` (`sample_data/` contains working examples). `MISSION_DATA_FILE` and `MISSION_USER_NAMES_FILE` let you point to specific files.
- **Mission credit CSV** - Place `data/SubmittedActivityList.csv` (columns: `Email, MissionChallenge, ActivityStatus, PointsAwarded`) before running the credit comparison script or uploading via the campaign UI.
- **Generated artifacts** - SQLite DBs, CSVs, and XLSX reports stay inside `data/` or `exports/` and are ignored by git. Back up these folders before deleting or truncating data.

## Running the Stack

### Option A - Docker Compose (recommended)
```bash
make up        # builds & starts backend + frontend with hot reload
make logs      # tail both services
make down      # stop containers and remove the dev stack
```
Backend code is mounted into the container so reloading happens instantly. The `frontend_node_modules` volume keeps npm installs fast; remove it (`docker volume rm mission-ai-possible-challenge-analytics-tool_frontend_node_modules`) after dependency changes.

### Option B - Local dev servers
```bash
# Backend
source .venv/bin/activate
uvicorn backend.app.main:app --reload --port ${BACKEND_PORT:-5098}

# Frontend (new terminal)
cd frontend
npm run dev -- --port ${FRONTEND_PORT:-5099}
```
Alternatively run `./scripts/run_analyzer.sh` to start both servers with sensible defaults, or use the Makefile helpers below.

### Useful Make targets

| Command | Description |
| --- | --- |
| `make backend-dev` / `make frontend-dev` | Run FastAPI or Next.js locally with reload. |
| `make backend-test` | Executes `pytest backend/tests`. |
| `make frontend-lint` / `make frontend-build` | Runs Next.js ESLint or production build. |
| `make test` | Backend tests + frontend lint in one command. |
| `make clean` | Remove `.venv` and `frontend/node_modules`. |

## Dashboard & Admin Features
- **Overview tab** - Mission summary cards (attempts, completions, unique users), leaderboards sortable by attempts/completions/points, and filters for week, challenge, status, or user.
- **Challenge Results tab** - Detailed per-challenge breakdown with completion timestamps and success states. Export CSV/Excel straight from the header.
- **All Chats tab** - Search every OpenWebUI conversation, filter to mission/regular/completed chats, and expand previews to skim the first few exchanges without leaving the page.
- **Missions tab** - Mission-by-mission progress grid with tooltip details for completed, in-progress, and not-started challenges.
- **Data freshness indicator** - Shows when each resource (users, models, chats) last reloaded and whether records changed.
- **Admin console (`/admin/config`)** - View row counts, database engine, reload history, and trigger resource-specific or full reloads (`upsert` or `truncate` modes).
- **Setup + auth** - The first visitor is redirected to `/setup` to create the bootstrap admin. Middleware (`frontend/middleware.ts`) enforces login on all non-public pages, attaches session cookies, and obeys the selected `AUTH_MODE`.

## Campaign Credit Tracker

Navigate to `/campaign` to review leaderboard standings that blend mission-derived points with the manually awarded credit file.

- **CSV uploads** - Drag/drop the latest `SubmittedActivityList.csv` (<=5 MB) to refresh credits. Admins can re-upload; other users fall back to SSR-provided data.
- **Ranks & badges** - Users are grouped into named ranks (`backend/app/campaign/service.py` seeds defaults) with per-week scoring columns.
- **Status indicators** - Surface data quality issues (missing emails, duplicate submissions, weeks with zero activity).
- **Exports & summaries** - Totals per week, per user, plus a quick view of the last upload timestamp.
- **CLI validation** - `python scripts/missing_credit_report.py` compares API completions with the CSV and writes `exports/combined_report.xlsx` + `exports/missing_credit_report.xlsx`. Set `API_BASE_URL` if the backend is not on `localhost:8000`.

## Railway / Railpack Deployment

`./start.sh` is Railpack-aware and can launch either service based on `SERVICE_ROLE`. Recommended setup for two Railway services:

| Service | Build commands | Required env vars | Notes |
| --- | --- | --- | --- |
| Backend API | `pip install -r backend/requirements.txt` (ensure Alembic + deps baked in) | `SERVICE_ROLE=backend`<br>`PYTHON_BIN=/app/.venv/bin/python` (or path to your interpreter)<br>`BACKEND_PORT=${PORT}` (Railway injects `PORT` automatically)<br>Database credentials (`DB_ENGINE`, `DB_HOST`, etc.) | `start.sh` will run Alembic migrations unless `SKIP_DB_MIGRATIONS=1`. If you prefer migrations during build, export that flag at runtime. |
| Frontend UI | `cd frontend && npm install && npm run build` | `SERVICE_ROLE=frontend`<br>`NEXT_PUBLIC_API_BASE_URL=https://<backend-service>.up.railway.app`<br>`API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}`<br>`FRONTEND_PORT=${PORT}` | Startup falls back to `npm run build` only when `.next/` is missing, so prebuilding keeps deploys snappy. |

Additional tips:
- Naming the services `backend` / `frontend` lets the script infer the role even without `SERVICE_ROLE`, but setting it explicitly avoids warnings.
- Single-service installs can set `DEFAULT_SERVICE_ROLE=backend` to silence the fallback message when the Railway service name doesn’t include “backend”.
- Point `PYTHON_BIN` at the exact interpreter produced during the build (for example `/app/.venv/bin/python`) so Uvicorn launches with the same environment that holds dependencies.
- When using Railway Postgres, either populate the `DB_*` variables or export `SQLALCHEMY_DATABASE_URI` using Railway’s managed connection string.

## CLI & Automation Helpers

- `scripts/setup_env.sh` - Create `.venv`, install backend dependencies, and optionally pin a custom env path.
- `scripts/run_analyzer.sh` - Launches Uvicorn + Next.js dev servers with coordinated env vars.
- `scripts/missing_credit_report.py` - Performs the credit comparison workflow described above, auto-refreshing OpenWebUI data if the cache is more than an hour old.
- Windows batch counterparts (`RUN_ANALYSIS.bat`, `RUN_WITH_API_FETCH.bat`, `FETCH_FROM_DEV.bat`) mirror the Bash scripts for teammates developing on Windows.

## Testing & Quality Checks

```bash
# Backend unit tests + campaign logic
make backend-test

# Frontend lint (ESLint) and component tests (Vitest)
make frontend-lint
cd frontend && npm run test

# Full CI-lite sweep
make test
```
Vitest is preconfigured with JSDOM (`frontend/vitest.config.ts`) and Testing Library helpers; backend tests live under `backend/tests/`.

## Troubleshooting & Further Reading
- `docs/ADMIN_DEPLOYMENT_GUIDE.md`, `docs/API_SETUP_GUIDE.md`, and `docs/WHATS_NEW.txt` contain deeper operational notes, OAuth walkthroughs, and release highlights.
- `QUICKSTART_DASHBOARD.md` summarizes the original static dashboard flow for historical context.
- `data/README.md` explains required/optional runtime files and safe-handling guidance.
- When switching databases or environments, always back up `data/mission_dashboard.sqlite` and the `exports/` folder before running destructive reloads.

Questions or improvements? Open an issue or start a discussion describing the scenario you're tackling--this stack is designed to evolve with each Mission AI Possible challenge cycle.

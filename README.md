# Mission Challenge Analytics

Mission Challenge Analytics is a two-service stack that exposes AI mission telemetry through a FastAPI backend and a Next.js dashboard. The backend aggregates OpenWebUI chat exports (or live API data), while the frontend renders leaderboards, mission breakdowns, chat previews, and model usage insights.

## Repository Layout

- `backend/` – FastAPI application (`backend/app/main.py`) and service layer
- `frontend/` – Next.js 14 dashboard written in TypeScript
- `data/` – Chat exports and optional `user_names.json` mapping
- `scripts/` – Helper scripts for setting up environments and starting the stack
- `docs/` – Operations guides, deployment notes, and legacy instructions
- `archive/` – Historical CLI utilities and static dashboard generator retained for reference

## Prerequisites

- Python 3.11+
- Node.js 18.17+ with npm
- Docker (optional, required for the compose workflow)

## Getting Started

1. Clone the repository and change into it.
2. Copy `.env.example` to `.env` and adjust values as needed.
3. Place an export file in `data/` (e.g. `data/all-chats-export-20240501.json`). A matching `data/user_names.json` is optional but recommended.

### Quick Start (Docker + Make)

```bash
cp .env.example .env       # if you haven't already
make up
```

This builds both images, starts the containers, and mounts the repository for hot reload. Use `make down` when you are finished and `make logs` to tail the stack.

### Run Locally (manual terminals)

```bash
# Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 to access the dashboard. By default the frontend talks to http://localhost:8000.

### Run Locally (helper script)

```bash
./scripts/setup_env.sh          # once, to create .venv
./scripts/run_analyzer.sh
```

The script launches `uvicorn` and `next dev` together and watches for source changes.

### Run with Docker Compose

```bash
make up
# or: docker compose up --build
```

The compose stack mounts the repository, enables hot reload, and shares `data/` into both containers. Use `make down` to stop services and `make logs` to tail output.

## Data Sources

- **Local exports (default):** The backend reads the latest `all-chats-export-*.json` in `data/`. Override with `MISSION_DATA_FILE` if you need a specific archive.
- **Live OpenWebUI fetch:** Set `OPEN_WEBUI_HOSTNAME` and `OPEN_WEBUI_API_KEY` to stream chats and users directly from OpenWebUI APIs on each request. When these variables are present, local JSON exports are bypassed.
- **User display names:** Provide `data/user_names.json` or point `MISSION_USER_NAMES_FILE` to a custom mapping so the leaderboard shows friendly names instead of UUID fragments.

## Environment Variables

### Minimal `.env` configuration

For local file-based analytics (no live OpenWebUI fetch), the following values must be present:

- `BACKEND_PORT=8000`
- `FRONTEND_PORT=3000`
- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- `API_BASE_URL=http://backend:8000`

Override `OPEN_WEBUI_HOSTNAME` and `OPEN_WEBUI_API_KEY` if you want to stream data directly from an OpenWebUI instance instead of `data/`.

Backend:
- `MISSION_DATA_FILE` – explicit path to an export (optional)
- `MISSION_USER_NAMES_FILE` – path to a JSON map of `user_id -> display_name`
- `OPEN_WEBUI_HOSTNAME` – base URL of OpenWebUI (e.g. https://example.com)
- `OPEN_WEBUI_API_KEY` – bearer token used for live API calls
- `BACKEND_PORT` – port exposed by Docker compose (defaults to 8000)

Frontend:
- `NEXT_PUBLIC_API_BASE_URL` – URL used by the browser to reach the API
- `API_BASE_URL` – URL used by Next.js server-side fetches (defaults to the Docker service name)
- `FRONTEND_PORT` – port exposed by Docker compose (defaults to 3000)

The provided `.env.example` captures the common variables for local development.

## Development Notes

- Backend dependencies live in `backend/requirements.txt`. Add new packages there and rebuild the virtual environment or compose image.
- Frontend tooling is configured via `frontend/package.json`; standard `npm run build` and `npm run lint` commands are available.
- The FastAPI service returns a single dashboard payload (`/dashboard`) plus `/health` for readiness checks.
- Mission analytics logic resides in `backend/app/services/mission_analyzer.py` and is shared by both live and archived workflows.

## Legacy CLI

Earlier single-script utilities are preserved under `archive/`. They are no longer part of the active deployment path but can be referenced for historical behaviour or backfilling reports.

## Additional Documentation

Operational runbooks, deployment steps, and admin guides live in the `docs/` directory. Start with `docs/ADMIN_DEPLOYMENT_GUIDE.md` and `docs/QUICKSTART.txt` if you need deeper operational detail.

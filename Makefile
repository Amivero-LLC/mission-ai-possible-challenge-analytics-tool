# Declare non-file targets so make never treats them as artifacts.
.PHONY: up down logs backend frontend

# Spin up both backend and frontend services with fresh images.
up:
	docker compose up --build

# Tear down running containers and networks defined in docker-compose.yml.
down:
	docker compose down

# Stream aggregated logs for quick troubleshooting (Ctrl+C to exit).
logs:
	docker compose logs -f

# Rebuild and start only the FastAPI backend service (good for API-only work).
backend:
	docker compose up backend --build

# Rebuild and start only the Next.js frontend service.
frontend:
	docker compose up frontend --build

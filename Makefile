.PHONY: up down logs backend frontend

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend:
	docker compose up backend --build

frontend:
	docker compose up frontend --build

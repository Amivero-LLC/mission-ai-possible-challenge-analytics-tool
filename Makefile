SHELL := /bin/bash

BACKEND_DIR := backend
FRONTEND_DIR := frontend
VENV := .venv

ifeq ($(OS),Windows_NT)
  VENV_BIN := $(VENV)/Scripts
else
  VENV_BIN := $(VENV)/bin
endif

PYTHON ?= python3
PIP := $(VENV_BIN)/pip
PYTEST := $(VENV_BIN)/pytest
UVICORN := $(VENV_BIN)/uvicorn

NPM := npm --prefix $(FRONTEND_DIR)

.PHONY: help up down logs backend-up frontend-up backend-install frontend-install install backend-dev frontend-dev backend-test frontend-lint frontend-build test clean backend frontend

help:
	@echo "Mission Challenge Analytics – available commands"
	@echo "  make install           # Install backend (venv) and frontend dependencies"
	@echo "  make backend-dev       # Run FastAPI locally with auto reload"
	@echo "  make frontend-dev      # Run Next.js dev server"
	@echo "  make backend-test      # Run backend pytest suite"
	@echo "  make frontend-lint     # Run Next.js lint checks"
	@echo "  make frontend-build    # Build production Next.js bundle"
	@echo "  make test              # Run backend tests + frontend lint"
	@echo "  make up                # docker compose up --build"
	@echo "  make down              # docker compose down"
	@echo "  make logs              # Tail docker compose logs"
	@echo "  make backend-up        # docker compose up backend --build"
	@echo "  make frontend-up       # docker compose up frontend --build"
	@echo "  make clean             # Remove local venv and node_modules"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-up:
	docker compose up backend --build

frontend-up:
	docker compose up frontend --build

backend: backend-up

frontend: frontend-up

$(VENV_BIN):
	$(PYTHON) -m venv $(VENV)

backend-install: $(VENV_BIN)
	$(PIP) install --upgrade pip
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt

frontend-install:
	$(NPM) install

install: backend-install frontend-install

backend-dev: backend-install
	$(UVICORN) backend.app.main:app --reload

frontend-dev: frontend-install
	$(NPM) run dev

backend-test: backend-install
	$(PYTEST) $(BACKEND_DIR)/tests

frontend-lint: frontend-install
	$(NPM) run lint

frontend-build: frontend-install
	$(NPM) run build

test: backend-test frontend-lint

clean:
	rm -rf $(VENV) $(FRONTEND_DIR)/node_modules

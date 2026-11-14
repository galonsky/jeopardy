PY=uv run python backend/manage.py

.PHONY: install setup services migrate migrations dev dev-backend dev-frontend test lint format generate-api sample export-progress import-progress
install:
	uv sync --frozen --all-groups
	cd frontend && corepack pnpm install --frozen-lockfile

setup:
	$(PY) migrate
	$(PY) seed_taxonomy
	$(PY) seed_presets

services:
	docker compose up -d postgres valkey

migrate:
	$(PY) migrate

migrations:
	$(PY) makemigrations

dev:
	$(MAKE) services
	process-compose up

dev-backend:
	uv run uvicorn config.asgi:application --app-dir backend --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && corepack pnpm dev

test:
	uv run pytest -n auto backend

lint:
	uv run ruff check backend
	PYTHONPATH=backend uv run mypy backend

format:
	uv run ruff format backend
	cd frontend && corepack pnpm format

generate-api:
	$(PY) dump_openapi --output frontend/openapi.json
	cd frontend && corepack pnpm generate

sample: setup
	$(PY) import_clues data/sample.tsv --revision sample-season-1

export-progress:
	$(PY) export_progress $(FILE)

import-progress:
	$(PY) import_progress $(FILE)


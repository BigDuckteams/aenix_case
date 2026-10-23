# Удобные команды. На Windows без make выполняйте команды из правых колонок напрямую.
.PHONY: dev-backend dev-frontend test lint gen-api up doctor submit

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && pnpm dev

test:
	cd backend && uv run pytest
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm typecheck

gen-api:
	cd backend && uv run python -m app.export_openapi ../frontend/openapi.json
	cd frontend && pnpm gen:api

up:
	docker compose up --build

doctor:
	python scripts/doctor.py

submit:
	@echo "Сборка комплекта сдачи появится на этапе S10"

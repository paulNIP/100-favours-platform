# Run from the repo root. `make help` lists targets.
SERVICES := gateway odds notifications predictions
# Postgres integration tests run when this points at a database (see `make db-test`).
TEST_DATABASE_URL ?= $(shell grep -s '^DATABASE_URL=' .env | cut -d= -f2- | sed 's,/odds$$,/odds_test,')

.PHONY: help install test lint format up down logs db db-test \
        dev-gateway dev-odds dev-notifications dev-predictions

help:  ## show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-20s %s\n", $$1, $$2}'

install:  ## create .venv with every service + dev tools
	uv sync --all-packages

test:  ## run each service's tests (separately: each has its own tests/ package)
	@for s in $(SERVICES); do echo "== $$s"; \
	  TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run --all-packages pytest -q services/$$s/tests || exit 1; done

lint:  ## ruff check + format check
	uv run ruff check . && uv run ruff format --check .

format:  ## ruff fix + format
	uv run ruff check --fix . && uv run ruff format .

# Local dev servers on the ports the gateway's defaults point at.
dev-gateway:  ## gateway on :8000
	uv run uvicorn gateway.main:app --host 127.0.0.1 --port 8000 --reload
dev-odds:  ## odds-service on :8001
	uv run uvicorn odds_service.main:app --host 127.0.0.1 --port 8001 --reload
dev-notifications:  ## notification-service on :8002
	uv run uvicorn notification_service.main:app --host 127.0.0.1 --port 8002 --reload
dev-predictions:  ## prediction-service on :8003
	uv run uvicorn prediction_service.main:app --host 127.0.0.1 --port 8003 --reload

up:  ## build and start everything in Docker
	docker compose up --build -d
down:  ## stop Docker services
	docker compose down
logs:  ## follow Docker logs
	docker compose logs -f

db:  ## start only Postgres (127.0.0.1:5433)
	docker compose up -d postgres
db-test: db  ## create the odds_test database used by integration tests
	docker compose exec -T postgres psql -U odds -d postgres -qc "CREATE DATABASE odds_test" 2>/dev/null || true

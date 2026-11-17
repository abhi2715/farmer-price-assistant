# Local dev without Docker (SQLite + in-memory Redis fallbacks). With Docker: `docker compose up --build`.
PY := backend/.venv/bin/python
API_PORT ?= 8000

.PHONY: setup bootstrap api web test lint up down
setup:            ## create venv, install deps (+ macOS libomp fix), install frontend
	cd backend && uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt -r ../ml/requirements.txt -r requirements-dev.txt -e ../ml
	./scripts/fix-macos-libomp.sh $(PY)
	cd frontend && npm install
bootstrap:        ## migrate + seed + train + forecast + match + alerts
	cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.scripts.bootstrap
api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port $(API_PORT)
web:
	cd frontend && NEXT_PUBLIC_API_URL=http://localhost:$(API_PORT) npm run dev
test:
	cd backend && .venv/bin/pytest -q
lint:
	backend/.venv/bin/ruff check backend ml && cd frontend && npm run typecheck
up:
	docker compose up --build
down:
	docker compose down

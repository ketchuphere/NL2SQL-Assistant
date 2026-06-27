.PHONY: help install dev-backend dev-frontend dev docker-up docker-down \
        index-schema test-backend lint-frontend clean

help:
	@echo ""
	@echo "  NL2SQL Full-Stack — Commands"
	@echo "  ──────────────────────────────────────────────────"
	@echo "  make install        Install all dependencies (frontend + backend)"
	@echo "  make dev            Start backend + frontend in dev mode (2 terminals)"
	@echo "  make dev-backend    Start FastAPI backend only (hot-reload)"
	@echo "  make dev-frontend   Start React frontend only"
	@echo "  make docker-up      Start full stack via Docker Compose"
	@echo "  make docker-down    Stop all Docker services"
	@echo "  make index-schema   Index the target database schema into Qdrant"
	@echo "  make test-backend   Run backend test suite"
	@echo "  make lint-frontend  Lint the frontend code"
	@echo "  make clean          Remove caches and build artefacts"
	@echo ""

install:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# Run both in parallel (requires GNU make or run separately)
dev:
	@echo "Start two terminals and run:"
	@echo "  Terminal 1: make dev-backend"
	@echo "  Terminal 2: make dev-frontend"

docker-up:
	docker compose up -d --build
	@echo ""
	@echo "  Backend API:   http://localhost:8000/docs"
	@echo "  Frontend App:  http://localhost:8080"
	@echo "  Qdrant UI:     http://localhost:6333/dashboard"

docker-down:
	docker compose down

index-schema:
	cd backend && python -c "\
from app.rag.pipeline import NL2SQLPipeline; \
p = NL2SQLPipeline(); \
n = p.index_database_schema(); \
print(f'Indexed {n} table documents.')"

test-backend:
	cd backend && pytest tests/ -v --tb=short --asyncio-mode=auto

lint-frontend:
	cd frontend && npm run lint

clean:
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type f -name "*.pyc" -delete 2>/dev/null || true
	find backend -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/node_modules/.cache 2>/dev/null || true
	@echo "Clean complete."

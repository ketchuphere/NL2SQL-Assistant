# NL2SQL Full-Stack Project

A production-ready **Natural Language to SQL** platform with a FastAPI backend and React frontend.

```
┌────────────────────────────────────────────────────────┐
│                React Frontend (port 8080)               │
│  Schema Explorer · Chat UI · Results Table · History    │
└────────────────────────┬───────────────────────────────┘
                         │  /api/v1/* (proxied)
┌────────────────────────▼───────────────────────────────┐
│              FastAPI Backend (port 8000)                │
│  RAG Pipeline · SQL Generator · Self-Healing Executor   │
└──────────┬────────────────────────┬────────────────────┘
           │                        │
┌──────────▼──────────┐  ┌──────────▼──────────┐
│  Qdrant (port 6333) │  │ Postgres (port 5432) │
│  Schema vectors     │  │  Query history       │
└─────────────────────┘  └─────────────────────┘
```

## Quick Start

### Option A — Docker (recommended)

```bash
# 1. Configure your target database
cp backend/.env.example backend/.env
# Edit backend/.env with your OPENAI_API_KEY and TARGET_DB_* values

# 2. Start everything
make docker-up

# 3. Index your database schema
make index-schema

# 4. Open the app
open http://localhost:8080
```

### Option B — Local development

```bash
# Install dependencies
make install

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env

# Terminal 1: start backend
make dev-backend

# Terminal 2: start frontend
make dev-frontend

# Index schema (in a 3rd terminal)
make index-schema
```

## Project Structure

```
nl2sql-fullstack/
├── frontend/                   React + Vite + TypeScript + shadcn/ui
│   ├── src/
│   │   ├── lib/api.ts           API client (wired to FastAPI)
│   │   ├── store/assistant.ts   Zustand state (with session tracking)
│   │   └── components/
│   │       └── assistant/
│   │           ├── ChatView.tsx
│   │           ├── SchemaExplorer.tsx  (live schema from backend)
│   │           ├── DbStatus.tsx        (live DB status badge)
│   │           ├── Sidebar.tsx
│   │           ├── MessageBubble.tsx
│   │           ├── ResultsTable.tsx
│   │           ├── ResultChart.tsx
│   │           └── SqlBlock.tsx
│   └── vite.config.ts           Proxy: /api/v1/* → localhost:8000
│
├── backend/                    FastAPI + Python
│   ├── app/
│   │   ├── main.py              FastAPI entry point
│   │   ├── api/
│   │   │   ├── rag.py           POST /rag/query, /rag/generate
│   │   │   ├── documents.py     POST /documents/index, GET /documents/schema
│   │   │   └── health.py        GET /health
│   │   ├── rag/
│   │   │   ├── pipeline.py      RAG orchestrator
│   │   │   ├── retriever.py     Vector search + query decomposition
│   │   │   ├── generator.py     GPT-4o SQL generation (instructor)
│   │   │   └── prompt_builder.py
│   │   ├── ingestion/           Loader · Chunker · Parser
│   │   ├── embeddings/          fastembed (dense + sparse)
│   │   ├── vectorstore/         Qdrant + FlashRank reranking
│   │   ├── db/                  SQLAlchemy async ORM
│   │   ├── middleware/          Error handler · Logger · Rate limiter
│   │   ├── utils/
│   │   │   ├── sql_connectors.py  MySQL · PostgreSQL · Snowflake · SQL Server
│   │   │   └── helpers.py
│   │   └── config/settings.py   Pydantic settings
│   ├── tests/
│   ├── docker/
│   └── requirements.txt
│
├── docker-compose.yml           Full stack: backend + frontend + qdrant + postgres
└── Makefile                     Dev commands
```

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/rag/query` | NL → SQL → Execute → Results |
| `POST` | `/api/v1/rag/generate` | NL → SQL only (dry-run) |
| `GET`  | `/api/v1/rag/history` | Paginated query history |
| `POST` | `/api/v1/documents/index` | Index a database schema |
| `GET`  | `/api/v1/documents/schema` | Get full schema (used by frontend) |
| `GET`  | `/api/v1/documents/status` | Qdrant collection stats |
| `GET`  | `/health` | Liveness check |

Full interactive docs: **http://localhost:8000/docs**

## Environment Variables (backend/.env)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `TARGET_DB_TYPE` | `postgresql` \| `mysql` \| `snowflake` \| `sqlserver` |
| `TARGET_DB_HOST` | Host of the database you want to query |
| `TARGET_DB_NAME` | Database name |
| `TARGET_DB_USER` | Username |
| `TARGET_DB_PASSWORD` | Password |

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

---

## Installation & Setup

You need **3 terminals** running simultaneously after the initial setup.

---

### Step 1 — Start Infrastructure

Start Qdrant (vector store) and Postgres (metadata store) via Docker:

```bash
cd NL2SQL-Assistant
docker compose up -d qdrant postgres
```

Verify they are running:

```bash
docker compose ps
```

Both should show status **healthy** before proceeding.

---

### Step 2 — Configure Environment

```bash
cd NLSQL-Assistant
cp .env.example .env
```

Open `.env` and fill in the required fields:

```env
# ── Required ──────────────────────────────────────────
OPENAI_API_KEY=sk-your-openai-key-here

# Target database (the DB you want to query in English)
TARGET_DB_TYPE=postgresql        # mysql | postgresql | snowflake | sqlserver
TARGET_DB_HOST=localhost
TARGET_DB_PORT=5432
TARGET_DB_USER=your_db_user
TARGET_DB_PASSWORD=your_db_password
TARGET_DB_NAME=your_database

# ── Already set — change only if needed ───────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=rag_password
POSTGRES_DB=nl2sql_rag

QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

### Step 3 — Backend Setup (Terminal 1)

```bash

# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Keep this terminal running.
- API is live at: **http://localhost:8000**
- Interactive docs: **http://localhost:8000/docs**

---

### Step 4 — Frontend Setup (Terminal 2)

```bash
cd NL2SQL-Assistant/frontend

# Install Node dependencies
npm install

# Start the dev server
npm run dev
```

Keep this terminal running.
- App is live at: **http://localhost:8080**

---

### Step 5 — Index Your Database Schema (Terminal 3)

This connects to your target database, extracts its schema, and indexes it into Qdrant so the RAG pipeline can retrieve relevant tables when answering questions.

**Option A — Python script:**

```bash

python -c "
from app.rag.pipeline import NL2SQLPipeline
p = NL2SQLPipeline()
n = p.index_database_schema()
print(f'Indexed {n} table documents.')
"
```

**Option B — API call (once the backend is running):**

```bash
curl -X POST http://localhost:8000/api/v1/documents/index \
  -H "Content-Type: application/json" \
  -d '{
    "db_type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "username": "your_db_user",
    "password": "your_db_password",
    "database": "your_database"
  }'
```

Run this **once**, or again whenever your database schema changes.

---

### Step 6 — Open the App

| Service | URL |
|---------|-----|
| **Frontend app** | http://localhost:8080 |
| **Backend API docs** | http://localhost:8000/docs |
| **Qdrant dashboard** | http://localhost:6333/dashboard |

You should see:
-  Green dot in the top-right DB status badge showing your DB name + table count
-  Real tables and columns in the Schema Explorer sidebar
-  Asking a question returns live SQL + query results

---

## Running Tests

```bash
cd NL2SQL-Assistant
pytest tests/ -v --tb=short --asyncio-mode=auto
```

---

## Project Structure

```
nl2sql-fullstack/
├── frontend/                        React + Vite + TypeScript + shadcn/ui
│   ├── src/
│   │   ├── lib/api.ts               API client (wired to FastAPI)
│   │   ├── store/assistant.ts       Zustand state (with session tracking)
│   │   └── components/
│   │       └── assistant/
│   │           ├── ChatView.tsx
│   │           ├── SchemaExplorer.tsx   Live schema from backend
│   │           ├── DbStatus.tsx         Live DB connection badge
│   │           ├── Sidebar.tsx
│   │           ├── MessageBubble.tsx
│   │           ├── ResultsTable.tsx
│   │           ├── ResultChart.tsx
│   │           └── SqlBlock.tsx
│   ├── vite.config.ts               Proxy: /api/v1/* → localhost:8000
│   └── package.json
│
├── backend/                         FastAPI + Python
│   ├── app/
│   │   ├── main.py                  FastAPI entry point
│   │   ├── api/
│   │   │   ├── rag.py               POST /rag/query, /rag/generate
│   │   │   ├── documents.py         POST /documents/index, GET /documents/schema
│   │   │   └── health.py            GET /health
│   │   ├── rag/
│   │   │   ├── pipeline.py          RAG orchestrator (retrieve → generate → execute)
│   │   │   ├── retriever.py         Vector search + LLM query decomposition
│   │   │   ├── generator.py         GPT-4o SQL generation via instructor
│   │   │   └── prompt_builder.py    Dialect-aware prompt construction
│   │   ├── ingestion/               Loader · Chunker · Parser
│   │   ├── embeddings/              fastembed (dense + sparse)
│   │   ├── vectorstore/             Qdrant + FlashRank reranking
│   │   ├── db/                      SQLAlchemy async ORM (query history)
│   │   ├── middleware/              Error handler · Logger · Rate limiter
│   │   ├── utils/
│   │   │   ├── sql_connectors.py    MySQL · PostgreSQL · Snowflake · SQL Server
│   │   │   └── helpers.py
│   │   └── config/settings.py       Pydantic settings loaded from .env
│   ├── tests/
│   │   ├── test_rag.py              RAG pipeline unit tests
│   │   └── test_api.py              FastAPI endpoint tests
│   ├── docker/
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
│
├── docker-compose.yml               Runs qdrant + postgres (+ optional full stack)
└── README.md
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/rag/query` | NL → SQL → Execute → Results |
| `POST` | `/api/v1/rag/generate` | NL → SQL only (dry-run, no execution) |
| `GET` | `/api/v1/rag/history` | Paginated query history |
| `DELETE` | `/api/v1/rag/session/{id}` | Clear multi-turn conversation session |
| `POST` | `/api/v1/documents/index` | Connect a DB and index its schema |
| `GET` | `/api/v1/documents/schema` | Get full schema JSON (used by frontend) |
| `GET` | `/api/v1/documents/status` | Qdrant collection stats |
| `DELETE` | `/api/v1/documents/reset` | Drop and recreate the vector collection |
| `POST` | `/api/v1/documents/upload` | Upload a PDF/TXT data dictionary |
| `GET` | `/health` | Liveness check |

---

## Environment Variables (backend/.env)

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | — |
| `LLM_MODEL` | LLM to use for generation | `gpt-4o` |
| `TARGET_DB_TYPE` | `postgresql` \| `mysql` \| `snowflake` \| `sqlserver` | `postgresql` |
| `TARGET_DB_HOST` | Host of the database to query | `localhost` |
| `TARGET_DB_PORT` | Port | `5432` |
| `TARGET_DB_NAME` | Database name | — |
| `TARGET_DB_USER` | Username | — |
| `TARGET_DB_PASSWORD` | Password | — |
| `POSTGRES_HOST` | Internal Postgres host (metadata store) | `localhost` |
| `QDRANT_HOST` | Qdrant host | `localhost` |
| `QDRANT_COLLECTION` | Qdrant collection name | `nl2sql_schemas` |
| `RATE_LIMIT_REQUESTS` | Max requests per window | `100` |
| `RATE_LIMIT_WINDOW` | Window size in seconds | `60` |

---

## How It Works

```
User types a question
        │
        ▼
store/assistant.ts  →  POST /api/v1/rag/query
                       (passes session_id for multi-turn context)
                               │
                               ▼
                  FastAPI NL2SQL RAG Pipeline
                  ├── Retriever  →  LLM query decomposition
                  │              →  Qdrant hybrid search (dense + SPLADE sparse)
                  │              →  FlashRank cross-encoder reranking
                  │              →  Returns top-5 relevant schema chunks
                  │
                  ├── Generator  →  GPT-4o + schema context
                  │              →  instructor enforces Pydantic output schema
                  │              →  Returns SQLGenerationResult
                  │
                  └── Executor   →  Runs SQL on target database
                                 →  Self-heals: retries up to 3x on errors
                               │
                               ▼
        { generated_sql, rows, tables_used, latency, session_id }
                               │
                               ▼
              api.ts  →  AssistantPayload  →  MessageBubble
                         SQL block · Results table · Chart
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| DB status badge shows "Offline" | Make sure `uvicorn` is running on port 8000 |
| Schema Explorer shows "No schema indexed" | Run Step 5 to index your schema |
| Query returns error | Check `OPENAI_API_KEY` is correctly set in `.env` |
| CORS errors in browser | Make sure you are using `npm run dev`, not a built version |
| `422 Unprocessable Entity` | Question must be at least 3 characters long |
| Qdrant connection refused | Run `docker compose up -d qdrant` |
| Postgres connection refused | Run `docker compose up -d postgres` |
| `ModuleNotFoundError` on backend start | Run `pip install -r requirements.txt` again |
| Frontend shows blank page | Check browser console; ensure backend is on port 8000 |

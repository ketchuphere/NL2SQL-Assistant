# NL2SQL RAG Project

A production-grade **Natural Language to SQL** system built with a **Retrieval-Augmented Generation** architecture. Ask questions about your database in plain English — the system retrieves the relevant schema context and generates accurate, dialect-aware SQL using an LLM.

```
Natural Language Query
       │
       ▼
[Retriever]  ─── Qdrant hybrid search + FlashRank reranking
       │
       ▼
[Generator]  ─── GPT-4o + schema context → structured SQL via instructor
       │
       ▼
[Executor]   ─── Run against MySQL / PostgreSQL / Snowflake / SQL Server
       │
       ▼
[Self-Healer] ── On error, refine & retry (up to 3 attempts)
       │
       ▼
  JSON Results
```

---

## Project Structure

```
nl2sql-rag-project/
├── app/
│   ├── main.py                   FastAPI entry point
│   ├── api/
│   │   ├── rag.py                NL2SQL query endpoints
│   │   ├── documents.py          Schema indexing & upload endpoints
│   │   └── health.py             Health check
│   ├── middleware/
│   │   ├── error_handler.py      Global error handler
│   │   ├── logger.py             Request logger
│   │   └── rate_limiter.py       Sliding-window rate limiter
│   ├── rag/
│   │   ├── pipeline.py           Main RAG orchestrator
│   │   ├── retriever.py          Schema retrieval (vector search)
│   │   ├── generator.py          SQL generation (LLM + instructor)
│   │   └── prompt_builder.py     Prompt construction
│   ├── ingestion/
│   │   ├── loader.py             Load schema / PDF / TXT
│   │   ├── chunker.py            Split documents
│   │   └── parser.py             Clean & enrich documents
│   ├── embeddings/
│   │   └── embedder.py           Dense + sparse embeddings (fastembed)
│   ├── vectorstore/
│   │   └── vector_db.py          Qdrant vector store operations
│   ├── db/
│   │   ├── postgres.py           Async SQLAlchemy engine
│   │   └── models.py             ORM models (QueryHistory, DatabaseSource)
│   ├── logs/
│   │   ├── app.log               Application logs
│   │   └── error.log             Error logs
│   ├── config/
│   │   └── settings.py           Pydantic settings (from .env)
│   └── utils/
│       ├── sql_connectors.py     Multi-dialect SQL connector
│       └── helpers.py            Shared utilities
├── tests/
│   ├── test_rag.py               RAG pipeline unit tests
│   └── test_api.py               FastAPI endpoint tests
├── docker/
│   ├── Dockerfile                Multi-stage Docker image
│   └── docker-compose.yml        Full stack (API + Qdrant + Postgres)
├── .github/
│   └── workflows/
│       └── ci.yml                GitHub Actions CI pipeline
├── .env                          Environment variables (do not commit)
├── requirements.txt              Python dependencies
├── README.md                     This file
└── Makefile                      Dev commands
```

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/your-org/nl2sql-rag-project.git
cd nl2sql-rag-project
make install
```

### 2. Configure environment

```bash
cp .env .env.local   # edit with your actual values
```

Key variables to set:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `TARGET_DB_TYPE` | `mysql` \| `postgresql` \| `snowflake` \| `sqlserver` |
| `TARGET_DB_HOST` | Target database host |
| `TARGET_DB_USER` | Target database username |
| `TARGET_DB_PASSWORD` | Target database password |
| `TARGET_DB_NAME` | Database name to query |

### 3. Start infrastructure

```bash
make docker-up
# Starts: Qdrant (port 6333) + Postgres (port 5432)
```

### 4. Index your database schema

```bash
make index-schema
# OR via API:
curl -X POST http://localhost:8000/api/v1/documents/index \
  -H "Content-Type: application/json" \
  -d '{"db_type":"postgresql","host":"localhost","port":5432,
       "username":"user","password":"pass","database":"mydb"}'
```

### 5. Run the API

```bash
make dev   # hot-reload for development
make run   # production mode
```

API docs: **http://localhost:8000/docs**

---

## Usage Examples

### Query in natural language

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me the top 10 customers by total revenue last quarter",
    "execute": true,
    "max_rows": 100
  }'
```

Response:
```json
{
  "generated_sql": "SELECT c.name, SUM(o.amount) AS total_revenue\nFROM \"public\".\"customers\" c\nJOIN \"public\".\"orders\" o ON c.customer_id = o.customer_id\nWHERE o.created_at >= date_trunc('quarter', now() - interval '3 months')\nGROUP BY c.name\nORDER BY total_revenue DESC\nLIMIT 10",
  "rows": [...],
  "row_count": 10,
  "success": true,
  "latency": {"retrieval_ms": 52.1, "generation_ms": 820.3, "execution_ms": 28.7, "total_ms": 901.1}
}
```

### Multi-turn conversation

```bash
# First turn
curl -X POST http://localhost:8000/api/v1/rag/query \
  -d '{"question":"How many orders were placed this month?","session_id":"session-abc"}'

# Follow-up (context is preserved)
curl -X POST http://localhost:8000/api/v1/rag/query \
  -d '{"question":"Break that down by product category","session_id":"session-abc"}'
```

### Dry-run (generate SQL without executing)

```bash
curl -X POST http://localhost:8000/api/v1/rag/generate \
  -d '{"question":"What is the average order value by region?"}'
```

---

## Architecture Highlights

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Framework** | FastAPI | Async REST API with OpenAPI docs |
| **LLM** | GPT-4o via OpenAI | SQL generation |
| **Structured Output** | `instructor` | Pydantic-typed LLM responses with retry |
| **Vector Store** | Qdrant | Hybrid (dense + sparse) schema retrieval |
| **Embeddings** | fastembed + all-MiniLM-L6-v2 | Dense vector embeddings |
| **Sparse Embeddings** | SPLADE (fastembed) | BM25-style sparse retrieval |
| **Reranker** | FlashRank (ms-marco) | Cross-encoder result reranking |
| **Metadata Store** | PostgreSQL + SQLAlchemy | Query history, session tracking |
| **Self-Healing** | Multi-attempt retry | Fixes SQL errors autonomously |
| **Supported DBs** | MySQL, PostgreSQL, Snowflake, SQL Server | Target database connectors |

---

## Running Tests

```bash
make test          # all tests
make test-cov      # with HTML coverage report
```

---

## CI/CD

GitHub Actions runs on every push to `main` / `develop`:
1. **Lint** — ruff code style check
2. **Tests** — pytest with Postgres + Qdrant services
3. **Docker build** — verifies the image builds successfully

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run tests: `make test`
4. Format: `make format`
5. Open a pull request

---

## License

MIT

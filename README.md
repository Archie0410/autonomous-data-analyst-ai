# Autonomous AI Data Analyst

A production-grade, full-stack AI system that lets users upload datasets and ask
natural-language questions. An autonomous **Planner → Executor → Critic** agent
pipeline understands the question, generates and runs SQL/pandas code, validates
the result, **automatically fixes its own errors**, and returns insights with
auto-selected charts.

```
┌────────────────────┐         ┌──────────────────────────────────────────────┐
│  React + Tailwind  │  HTTPS  │  FastAPI                                     │
│  + Plotly Frontend │ ──────► │   ├─ /api/datasets   (upload, list, detail)  │
│                    │         │   ├─ /api/query      (NL → answer + chart)   │
│                    │         │   └─ /api/history    (audit trail)           │
└────────────────────┘         │                                              │
                               │  LangGraph Agent                             │
                               │   ├─ Planner  (LLM)                          │
                               │   ├─ Executor (LLM + tool calling)           │
                               │   │    ├─ run_sql(query)                     │
                               │   │    ├─ run_python(code)  ← sandboxed      │
                               │   │    └─ generate_plot(...) ← auto chart    │
                               │   └─ Critic   (LLM, JSON verdict)            │
                               │                                              │
                               │  Storage                                     │
                               │   ├─ SQLite (system + user tables)           │
                               │   └─ FAISS  (schema vector store)            │
                               └──────────────────────────────────────────────┘
```

---

## Features

### Core
- **CSV ingestion** with automatic schema detection, column sanitization, and
  preview (first 10 rows). Each dataset becomes its own SQLite table.
- **Natural-language query → SQL/Python → answer**, returning a table and an
  auto-selected chart.
- **Agent system** built on **LangGraph** with three roles:
  - **Planner** — produces a short, numbered plan from the user's question and
    the dataset schema.
  - **Executor** — uses **OpenAI function calling** to call `run_sql`,
    `run_python`, or `generate_plot`. Bounded retry loop with automatic error
    correction.
  - **Critic** — validates the final answer against the tool trace and
    rewrites it if it disagrees.
- **Tool calling** with three first-class tools:
  - `run_sql(query)` — read-only SQLite, DML/DDL blocked, automatic LIMIT.
  - `run_python(code)` — sandboxed pandas/numpy with restricted builtins,
    timeout (POSIX), and a `result` contract.
  - `generate_plot(data, chart_type, x, y, title)` — bar, line, pie, scatter,
    histogram, table, or `auto`.
- **Vector-store schema retrieval (FAISS)** — when multiple datasets are
  uploaded, the agent can pick the right one based on the question.
- **Conversation memory** for follow-ups (`"now show only top 3"`).
- **Full audit log** of every plan, tool call, and critic verdict in `query_logs`.

### Frontend
- Modern dark UI built with Tailwind, with cards, sticky header, drag-and-drop
  upload, and a chat-style transcript.
- Live agent reasoning trace (Planner / Executor / Critic / tool steps) with
  expandable input + output for every step.
- Auto-rendered tables and Plotly charts.

### Production touches
- Modular folder layout, Pydantic-typed config, loguru logging with rotation.
- Health check endpoint, FastAPI lifespan startup.
- Strict, typed Pydantic schemas for every endpoint.
- Docker images for backend (Python 3.11) and frontend (nginx) with a
  ready-to-run `docker-compose.yml`.
- Pytest smoke tests that don't require an API key.

---

## Folder structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI factory + lifespan
│   │   ├── config.py             # pydantic-settings, .env loader
│   │   ├── routes/               # /api/datasets, /api/query, /api/history
│   │   ├── services/             # ingestion, database, memory, vector_store
│   │   ├── agent/                # LangGraph graph + tools + prompts
│   │   ├── models/               # SQLAlchemy + Pydantic schemas
│   │   └── utils/                # logger, json-safe serializer
│   ├── tests/                    # pytest smoke tests
│   ├── data/                     # SQLite, uploads, FAISS index (gitignored)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/           # Header, Chat, DatasetUpload, Chart, etc.
│   │   ├── hooks/useSession.js
│   │   └── api/client.js
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── Dockerfile + nginx.conf
├── examples/
│   ├── generate_example_data.py
│   └── sample_sales.csv          # 1,200-row sales dataset
├── docker-compose.yml
└── README.md
```

---

## Getting started (local dev)

### Prerequisites
- Python 3.10 or 3.11
- Node.js 18+
- An OpenAI API key (`sk-...`)

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env and set OPENAI_API_KEY

uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Swagger docs are at
`http://localhost:8000/docs`.

### 2. Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Uploads go through the Vite dev-server proxy to
`http://localhost:8000`.

### 3. Try it

1. Generate the example dataset (already shipped at `examples/sample_sales.csv`,
   but you can regenerate with `python examples/generate_example_data.py`).
2. Drag-and-drop `examples/sample_sales.csv` onto the **Upload dataset** panel.
3. Ask the agent things like:
   - `Show top 5 customers by total revenue.`
   - `What is the monthly revenue trend over the last year? Plot it.`
   - `Which product category has the highest average discount?`
   - `Now show only the top 3.` *(follow-up — uses memory)*
   - `Compare APAC vs Europe revenue by quarter, as a grouped bar chart.`

You should see the agent's plan, tool calls, table, chart, and final answer.

---

## Running with Docker

```bash
# Set your key (or put it in a .env file at the repo root)
export OPENAI_API_KEY=sk-...

docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend:  `http://localhost:8000`

State (uploads, SQLite DB, FAISS index, logs) is persisted in named Docker
volumes (`backend-data`, `backend-logs`).

---

## API reference

| Method | Path                       | Description                                         |
|--------|----------------------------|-----------------------------------------------------|
| `GET`  | `/api/health`              | Health check.                                       |
| `POST` | `/api/datasets/upload`     | Multipart upload (`file`, optional `name`).         |
| `GET`  | `/api/datasets`            | List datasets.                                      |
| `GET`  | `/api/datasets/{id}`       | Dataset detail with column info + 10-row preview.   |
| `POST` | `/api/query`               | `{ question, dataset_id?, session_id }`.            |
| `GET`  | `/api/history`             | Recent query logs (filter by `session_id`).         |
| `GET`  | `/api/sessions/{id}/messages` | Conversation messages for a session.            |

`POST /api/query` returns:

```jsonc
{
  "success": true,
  "session_id": "abc-...",
  "question": "Top 5 customers by revenue?",
  "answer": "The top 5 customers by total revenue are ...",
  "plan": "1. ...\n2. ...",
  "steps": [
    { "step": 1, "role": "planner", "output": "..." },
    { "step": 2, "role": "tool", "tool": "run_sql", "input": {...}, "output": {...} },
    { "step": 3, "role": "executor", "output": "..." },
    { "step": 4, "role": "critic", "output": { "approved": true, ... } }
  ],
  "table": [ { "customer_name": "Alice", "revenue": 12345 }, ... ],
  "chart": { "chart_type": "bar", "x": "customer_name", "y": ["revenue"], "data": [...] }
}
```

---

## Configuration

All settings live in `backend/.env` (see `backend/.env.example`):

| Key                       | Default                              | Notes                                |
|---------------------------|--------------------------------------|--------------------------------------|
| `OPENAI_API_KEY`          | — (required for `/query`)            |                                      |
| `OPENAI_MODEL`            | `gpt-4o-mini`                        | Any chat model with tool calling.    |
| `OPENAI_EMBEDDING_MODEL`  | `text-embedding-3-small`             | Used by the FAISS schema store.      |
| `DATABASE_URL`            | `sqlite:///./data/db/analyst.db`     | SQLAlchemy URL.                      |
| `UPLOAD_DIR`              | `./data/uploads`                     |                                      |
| `VECTOR_STORE_DIR`        | `./data/vector_store`                |                                      |
| `AGENT_MAX_ITERATIONS`    | `6`                                  | Executor tool-calling loop bound.    |
| `AGENT_MAX_FIX_ATTEMPTS`  | `3`                                  | Consecutive tool-failure cap.        |
| `CORS_ORIGINS`            | `http://localhost:5173,...`          | Comma-separated.                     |
| `LOG_LEVEL`               | `INFO`                               | Loguru log level.                    |

---

## Security notes

- `run_sql` only allows `SELECT / WITH / EXPLAIN / PRAGMA`, blocks DML/DDL,
  rejects multiple statements, and injects a hard `LIMIT`.
- `run_python` runs in a restricted-globals sandbox with a minimal `__builtins__`
  whitelist (no `open`, `eval`, `__import__`, etc.) and a 15-second timeout
  (POSIX). For untrusted multi-tenant production use, also run the executor
  process in an isolated container with no network and strict CPU/memory limits.
- The CSV schema is exposed to the LLM as part of the planner/executor prompts;
  do not upload sensitive data while pointed at a third-party LLM endpoint.

---

## Tests

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests/ -v
# or, on macOS/Linux:
# .venv/bin/python -m pytest tests/ -v
```

Smoke tests cover the health endpoint, CSV upload + dataset listing, and the
SQL/Python tool guardrails. They do **not** require an OpenAI key.

---



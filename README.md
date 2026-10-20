# Data Analyst Agent

A portfolio-grade analytics workspace for natural-language analysis, SQL inspection, dataset browsing, and Text-to-SQL evaluation. The React frontend talks to a FastAPI service that executes **read-only** SQLite queries. The UI does not invent analysis results when the backend is unavailable.

This first backend version is deterministic: it maps a small set of questions to SQL templates. It does **not** require an LLM or API key.

## Architecture

```
React + TypeScript + Vite + TanStack Router
        HTTP JSON (/api/*)
Python FastAPI
        SQLGlot validator (SELECT only)
        SQLite sales.db (read-only query connections)
```

- Frontend routes and workspace UI live under `src/`.
- All frontend HTTP calls and response types are isolated in `src/services/api.ts`.
- Backend route handlers live in `backend/main.py`.
- Database initialization is in `backend/db.py` (not mixed into query execution).
- SQL validation is in `backend/sql_safety.py`.
- Read-only execution is in `backend/query.py`.
- Natural-language templates are in `backend/analyze.py`.
- Evaluation cases are in `backend/evaluation.py`.

## Run locally (Windows PowerShell)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
npm install
```

No `.env` file is required by default. The frontend reads `VITE_API_BASE_URL` if it is set, but if it is unset it falls back to `http://127.0.0.1:8000` automatically.

Start the backend in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend in a second terminal:

```powershell
npm run dev
```

Open `http://localhost:8080` to use the app. The backend listens on `http://127.0.0.1:8000` and initializes `backend/data/sales.db` on startup if it does not already contain data. The FastAPI docs are available at `http://127.0.0.1:8000/docs`.

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `DATABASE_PATH` | `backend/data/sales.db` | SQLite file location |
| `MAX_RESULT_ROWS` | `100` | Default SELECT row cap |
| `ABSOLUTE_MAX_ROWS` | `1000` | Hard cap for `max_rows` |
| `QUERY_TIMEOUT_SECONDS` | `5` | SQLite progress-handler timeout |
| `CORS_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | Allowed frontend origins |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Optional frontend API origin override |

Do not put API keys, database passwords, or other secrets in source, logs, screenshots, or Git commits. This project does not need a provider key for the current analysis path.

## API endpoints

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `GET` | `/api/health` | — | `{ status, database, dataset }` |
| `GET` | `/api/datasets` | — | `[{ id, name, description }]` |
| `GET` | `/api/schema?dataset=sales` | — | tables, columns, row counts, sample rows, relationships |
| `POST` | `/api/query` | `{ "sql": "..." }` | `{ columns, rows, row_count, execution_time_ms, status }` |
| `POST` | `/api/analyze` | `{ "question", "dataset", "max_rows" }` | answer, findings, sql, result, chart, timing, status |
| `GET` | `/api/evaluation` | — | last `EvaluationReport`, or `{}` if none |
| `POST` | `/api/evaluation/run` | `{}` | freshly computed `EvaluationReport` |

Interactive docs: `http://127.0.0.1:8000/docs`.

## Dataset schema

Synthetic retail data (seeded once, deterministic with RNG seed `42`):

- `customers(id, name, email, city, region, created_at)`
- `products(id, name, category, unit_price, stock)`
- `orders(id, customer_id, order_date, status)`
- `order_items(id, order_id, product_id, quantity, unit_price)`

Relationships: `orders.customer_id → customers.id`, `order_items.order_id → orders.id`, `order_items.product_id → products.id`.

Sales totals exclude cancelled orders and include `completed` and `shipped`.

## Supported analysis questions

The analyst maps phrases to templates, then runs them through the same validator:

- Total sales / revenue
- Monthly sales / order trend
- Top products
- Order counts by status
- Sales by category
- Top customers by order value
- Low-stock products

Questions about employees (or other missing tables) return `status: "unsupported"` with an explanation. No numbers are invented.

Chart types returned to the existing UI: `bar`, `line`, `pie`, `table`.

## SQL safety

- SQLGlot parses the statement as SQLite and inspects the AST. Keyword matching is not the security boundary.
- Only a single `SELECT` (including `WITH` CTEs and `UNION` of selects) is allowed.
- `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `PRAGMA`, stacked statements, and unsafe functions such as `load_extension` / `readfile` / `writefile` are rejected.
- Query connections open the database with `mode=ro` and `PRAGMA query_only = ON`.
- Result rows are capped. A progress handler aborts long-running queries.
- The query endpoint cannot modify the database or touch the filesystem.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm test
npm run build
```

## Frontend scripts

- `npm run dev` — local development
- `npm run build` — production build
- `npm test` — unit and routing tests

## Limitations

- Analysis is template-based, not a general text-to-SQL model.
- One bundled dataset (`sales`).
- Evaluation is a small reproducible suite (execution, correctness, unsupported questions, and SQL safety), not a 30-question industry benchmark.
- Unsafe SQL returns HTTP 400; the frontend surfaces that as a service error.

## License / secrets

Keep `.venv/`, `backend/data/*.db`, and local env files out of Git. Never commit credentials.

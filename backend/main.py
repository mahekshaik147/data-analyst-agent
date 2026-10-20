from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.analyze import analyze_question
from backend.config import CORS_ORIGINS, DATABASE_PATH, DATASET_ID, QUERY_TIMEOUT_SECONDS, clamp_max_rows
from backend.db import dataset_catalog, health_snapshot, init_database, inspect_schema, known_dataset
from backend.evaluation import current_report, run_evaluation
from backend.query import QueryExecutionError, execute_readonly
from backend.sql_safety import UnsafeSqlError


class QueryRequest(BaseModel):
    sql: str


class AnalyzeRequest(BaseModel):
    question: str
    dataset: str | None = None
    max_rows: int | None = Field(default=None, ge=1, le=1000)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database(DATABASE_PATH)
    yield


app = FastAPI(
    title="Data Analyst Agent API",
    description="Backend API for natural-language data analysis.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health")
def health_check():
    snapshot = health_snapshot(DATABASE_PATH)
    return snapshot


@app.get("/")
def root():
    return {
        "message": "Welcome to the Data Analyst Agent API.",
        "docs": "/docs",
    }


@app.get("/api/datasets")
def list_datasets():
    return dataset_catalog()


@app.get("/api/schema")
def get_schema(dataset: str | None = None):
    _require_dataset(dataset)
    return inspect_schema(DATABASE_PATH)


@app.post("/api/query")
def run_query(body: QueryRequest):
    try:
        result = execute_readonly(
            DATABASE_PATH,
            body.sql,
            max_rows=clamp_max_rows(None),
            timeout_seconds=QUERY_TIMEOUT_SECONDS,
        )
    except UnsafeSqlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QueryExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "execution_time_ms": result["execution_time_ms"],
        "status": result["status"],
    }


@app.post("/api/analyze")
def run_analyze(body: AnalyzeRequest):
    _require_dataset(body.dataset)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="A question is required.")
    return analyze_question(DATABASE_PATH, body.question, body.max_rows)


@app.get("/api/evaluation")
def get_evaluation():
    return current_report()


@app.post("/api/evaluation/run")
def post_evaluation_run():
    return run_evaluation(DATABASE_PATH)


def _require_dataset(dataset: str | None) -> None:
    if not known_dataset(dataset):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dataset '{dataset}'. Available dataset: {DATASET_ID}.",
        )

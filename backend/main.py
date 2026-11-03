from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.analyze import analyze_question
from backend.config import (
    CORS_ORIGINS,
    DATABASE_PATH,
    DATASET_ID,
    DATASETS,
    QUERY_TIMEOUT_SECONDS,
    clamp_max_rows,
    delete_uploaded_dataset,
    refresh_uploaded_datasets,
)
from backend.db import dataset_catalog, health_snapshot, import_uploaded_dataset, init_database, inspect_schema, known_dataset
from backend.evaluation import current_report, run_evaluation
from backend.query import QueryExecutionError, execute_readonly
from backend.sql_safety import UnsafeSqlError

class QueryRequest(BaseModel):
    sql: str
    dataset: str | None = None


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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
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
    refresh_uploaded_datasets()
    return dataset_catalog()


@app.post("/api/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), dataset_name: str | None = Form(None)):
    if file is None or file.filename is None:
        raise HTTPException(status_code=400, detail="A CSV file is required.")
    try:
        dataset_info = import_uploaded_dataset(file.file, dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    refresh_uploaded_datasets()
    return {
        "status": "ok",
        "dataset": {
            "id": dataset_info["id"],
            "name": dataset_info["name"],
            "description": dataset_info["description"],
            "currency": "USD",
        },
        "table_name": dataset_info["table_name"],
        "row_count": dataset_info["row_count"],
    }


@app.delete("/api/datasets/{dataset_id}")
def delete_dataset(dataset_id: str):
    try:
        result = delete_uploaded_dataset(dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        status = 403 if str(exc).lower().startswith("built-in") else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    refresh_uploaded_datasets()
    return {
        "status": "ok",
        "dataset_id": result["id"],
        "name": result["name"],
    }


@app.get("/api/schema")
def get_schema(dataset: str | None = None):
    dataset_id, path = _resolve_dataset(dataset)
    return inspect_schema(path, dataset_id)

@app.post("/api/query")
def run_query(body: QueryRequest):
    _, path = _resolve_dataset(body.dataset)
    try:
        result = execute_readonly(
            path,
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
    dataset_id, path = _resolve_dataset(body.dataset)
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="A question is required.")
    return analyze_question(path, body.question, body.max_rows, dataset_id)


@app.get("/api/evaluation")
def get_evaluation():
    return current_report()


@app.post("/api/evaluation/run")
def post_evaluation_run():
    return run_evaluation(DATABASE_PATH)


def _resolve_dataset(dataset: str | None) -> tuple[str, Path]:
    """Return (dataset_id, database_path) for the requested dataset, or raise 404."""
    refresh_uploaded_datasets()
    if dataset in (None, ""):
        dataset = DATASET_ID
    if dataset == DATASET_ID:
        return DATASET_ID, DATABASE_PATH
    config = DATASETS.get(dataset)
    if config is None or not config["path"].exists():
        available = ", ".join(
            [DATASET_ID]
            + [key for key, value in DATASETS.items() if key != DATASET_ID and value["path"].exists()]
        )
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dataset '{dataset}'. Available datasets: {available}.",
        )
    return dataset, config["path"]

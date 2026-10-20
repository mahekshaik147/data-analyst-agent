from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def reset_evaluation_state():
    from backend import evaluation

    evaluation._last_report = None
    evaluation._history.clear()


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    database = tmp_path / "sales.db"
    monkeypatch.setattr("backend.config.DATABASE_PATH", database)
    monkeypatch.setattr("backend.main.DATABASE_PATH", database)
    from backend.db import init_database

    init_database(database)
    return database


@pytest.fixture()
def client(db_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    from backend import main

    with TestClient(main.app) as test_client:
        yield test_client

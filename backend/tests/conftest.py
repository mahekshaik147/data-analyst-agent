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


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    """Redirect uploaded-dataset storage to a temp directory for every test.

    backend.config resolves upload paths from module globals (DATA_DIR,
    UPLOADS_DIR, UPLOAD_REGISTRY_PATH) and backend.db imported UPLOADS_DIR
    directly, so both modules must be patched. Without this, tests that upload
    CSV datasets write into the production registry at
    backend/data/uploads/registry.json and accumulate stale entries.
    """
    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    registry_path = uploads_dir / "registry.json"
    registry_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("backend.config.DATA_DIR", data_dir)
    monkeypatch.setattr("backend.config.UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr("backend.config.UPLOAD_REGISTRY_PATH", registry_path)
    monkeypatch.setattr("backend.db.UPLOADS_DIR", uploads_dir)


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

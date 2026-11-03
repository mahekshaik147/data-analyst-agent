import json
import os
from pathlib import Path

from backend import config as backend_config
from backend.analyze import _normalize, _pick_dimension_column
from backend.db import init_database
from backend.evaluation import run_evaluation


def test_health_and_datasets(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    payload = health.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert payload["dataset"] == "sales"

    datasets = client.get("/api/datasets")
    assert datasets.status_code == 200
    body = datasets.json()
    assert body[0]["id"] == "sales"


def test_schema_contains_tables_and_sample_rows(client):
    response = client.get("/api/schema", params={"dataset": "sales"})
    assert response.status_code == 200
    schema = response.json()
    assert schema["dataset"] == "sales"
    assert len(schema["tables"]) == 4
    products = next(table for table in schema["tables"] if table["name"] == "products")
    assert products["row_count"] > 0
    assert products["sample_rows"]
    assert any(column["primary_key"] for column in products["columns"])


def test_query_select_and_reject_write(client):
    ok = client.post("/api/query", json={"sql": "SELECT COUNT(*) AS n FROM customers", "dataset": "sales"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["columns"] == ["n"]
    assert body["rows"][0]["n"] == 32
    assert body["status"] == "ok"

    olist_ok = client.post("/api/query", json={"sql": "SELECT COUNT(*) AS n FROM orders", "dataset": "olist"})
    assert olist_ok.status_code == 200
    assert olist_ok.json()["status"] == "ok"

    blocked = client.post("/api/query", json={"sql": "DELETE FROM customers", "dataset": "sales"})
    assert blocked.status_code == 400


def test_upload_csv_dataset_registers_and_queries(client, tmp_path):
    csv_path = tmp_path / "uploaded_report.csv"
    csv_path.write_text(
        "region,sales\nNorth,120\nSouth,90\nEast,150\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/api/datasets/upload",
            files={"file": ("uploaded_report.csv", handle, "text/csv")},
            data={"dataset_name": "Uploaded sales"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    dataset_id = payload["dataset"]["id"]
    assert dataset_id != "sales"
    assert dataset_id != "olist"

    datasets = client.get("/api/datasets")
    ids = {item["id"] for item in datasets.json()}
    assert dataset_id in ids

    query = client.post(
        "/api/query",
        json={"sql": "SELECT COUNT(*) AS n FROM uploaded_data", "dataset": dataset_id},
    )
    assert query.status_code == 200
    assert query.json()["rows"][0]["n"] == 3


def test_uploaded_csv_analysis_uses_dataset_schema_for_highest_sales(client, tmp_path):
    csv_path = tmp_path / "uploaded_report.csv"
    csv_path.write_text(
        "region,sales\nNorth,120\nSouth,90\nEast,150\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/api/datasets/upload",
            files={"file": ("uploaded_report.csv", handle, "text/csv")},
            data={"dataset_name": "Uploaded sales"},
        )

    assert response.status_code == 200
    dataset_id = response.json()["dataset"]["id"]

    analysis = client.post(
        "/api/analyze",
        json={"question": "Which region has the highest sales?", "dataset": dataset_id, "max_rows": 25},
    )
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["status"] == "ok"
    sql = payload["sql"].lower()
    assert '"uploaded_data"' in sql or "from uploaded_data" in sql
    assert 'group by "region"' in sql or 'group by region' in sql
    assert 'sum("sales")' in sql or 'sum(sales)' in sql
    assert 'order_items' not in sql
    assert 'order_payments' not in sql


def test_uploaded_csv_analysis_prefers_region_for_regional_sales_and_product_for_product_sales(client, tmp_path):
    csv_path = tmp_path / "regional_sales.csv"
    csv_path.write_text(
        "region,product,sales\nNorth,Widget,120\nNorth,Gadget,95\nSouth,Widget,80\nSouth,Gadget,130\nEast,Widget,60\nEast,Gadget,70\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/api/datasets/upload",
            files={"file": ("regional_sales.csv", handle, "text/csv")},
            data={"dataset_name": "Regional product sales"},
        )

    assert response.status_code == 200
    dataset_id = response.json()["dataset"]["id"]

    region_analysis = client.post(
        "/api/analyze",
        json={"question": "Which region has the highest sales?", "dataset": dataset_id, "max_rows": 25},
    )
    assert region_analysis.status_code == 200
    region_sql = region_analysis.json()["sql"].lower()
    assert 'group by "region"' in region_sql or 'group by region' in region_sql
    assert 'sum("sales")' in region_sql or 'sum(sales)' in region_sql
    assert 'group by "product"' not in region_sql and 'group by product' not in region_sql

    product_analysis = client.post(
        "/api/analyze",
        json={"question": "Which product has the highest sales?", "dataset": dataset_id, "max_rows": 25},
    )
    assert product_analysis.status_code == 200
    product_sql = product_analysis.json()["sql"].lower()
    assert 'group by "product"' in product_sql or 'group by product' in product_sql
    assert 'sum("sales")' in product_sql or 'sum(sales)' in product_sql
    assert 'group by "region"' not in product_sql and 'group by region' not in product_sql


def test_uploaded_csv_analysis_exact_region_question_groups_by_region(client, tmp_path):
    csv_path = tmp_path / "persistence_test_region.csv"
    csv_path.write_text(
        "region,product,sales\nNorth,Laptop,120\nSouth,Phone,90\nEast,Monitor,150\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/api/datasets/upload",
            files={"file": ("persistence_test_region.csv", handle, "text/csv")},
            data={"dataset_name": "Persistence Test"},
        )

    assert response.status_code == 200
    dataset_id = response.json()["dataset"]["id"]
    schema = client.get("/api/schema", params={"dataset": dataset_id}).json()
    table = next(table for table in schema["tables"] if table["name"] == "uploaded_data")
    text = _normalize("Which region has the highest sales?")
    selected = _pick_dimension_column(table["columns"], text)
    print(f"selected_dimension_for_region_question={selected['name'] if selected else None}")
    assert selected is not None
    assert selected["name"] == "region"

    analysis = client.post(
        "/api/analyze",
        json={"question": "Which region has the highest sales?", "dataset": dataset_id, "max_rows": 25},
    )
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["status"] == "ok"
    sql = payload["sql"].lower()
    assert 'group by "region"' in sql or 'group by region' in sql
    assert 'group by "product"' not in sql and 'group by product' not in sql


def test_uploaded_csv_analysis_rejects_missing_requested_dimension_without_running_sql(client, tmp_path):
    csv_path = tmp_path / "persistence_test_missing_region.csv"
    csv_path.write_text(
        "product,category,sales\nLaptop,Electronics,120\nPhone,Electronics,90\nMonitor,Office,150\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        response = client.post(
            "/api/datasets/upload",
            files={"file": ("persistence_test_missing_region.csv", handle, "text/csv")},
            data={"dataset_name": "Persistence Test"},
        )

    assert response.status_code == 200
    dataset_id = response.json()["dataset"]["id"]

    region_question = client.post(
        "/api/analyze",
        json={"question": "Which region has the highest sales?", "dataset": dataset_id, "max_rows": 25},
    )
    assert region_question.status_code == 200
    region_body = region_question.json()
    assert region_body["status"] == "unsupported"
    assert region_body["sql"] == ""
    assert region_body["result"]["rows"] == []
    assert "region" in region_body["answer"].lower()

    product_question = client.post(
        "/api/analyze",
        json={"question": "Which product has the highest sales?", "dataset": dataset_id, "max_rows": 25},
    )
    assert product_question.status_code == 200
    product_body = product_question.json()
    assert product_body["status"] == "ok"
    product_sql = product_body["sql"].lower()
    assert 'group by "product"' in product_sql or 'group by product' in product_sql
    assert 'group by "region"' not in product_sql and 'group by region' not in product_sql


def test_sales_region_question_groups_by_customer_region(client):
    analysis = client.post(
        "/api/analyze",
        json={"question": "Which region has the highest sales?", "dataset": "sales", "max_rows": 25},
    )
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["status"] == "ok"
    sql = payload["sql"].lower()
    assert "customers" in sql
    assert "region" in sql
    assert "sum(oi.quantity * oi.unit_price)" in sql
    assert "group by c.region" in sql
    assert "order by sales desc" in sql
    assert "p.name as product" not in sql

    result = payload["result"]
    assert result["columns"] == ["region", "sales"]
    assert result["rows"]
    sales_values = [row["sales"] for row in result["rows"]]
    assert sales_values == sorted(sales_values, reverse=True)
    expected_answer = f"{result['rows'][0]['region']} is the highest-selling region with ${sales_values[0]:,.2f} in sales."
    assert payload["answer"] == expected_answer


def test_upload_tests_use_isolated_temp_registry(client):
    """Regression guard: test uploads must never touch the production registry.

    The autouse isolated_uploads fixture redirects DATA_DIR/UPLOADS_DIR/
    UPLOAD_REGISTRY_PATH (and backend.db.UPLOADS_DIR) into tmp_path.
    """
    import backend.config
    import backend.db

    production_registry = Path(__file__).resolve().parents[2] / "backend" / "data" / "uploads" / "registry.json"
    assert backend_config.UPLOAD_REGISTRY_PATH != production_registry
    assert backend_config.UPLOADS_DIR != production_registry.parent
    assert backend.db.UPLOADS_DIR == backend_config.UPLOADS_DIR

    before = production_registry.read_text(encoding="utf-8")

    csv_path = backend_config.UPLOADS_DIR / "isolation_check.csv"
    csv_path.write_text("region,sales\nNorth,10\n", encoding="utf-8")
    with csv_path.open("rb") as handle:
        upload = client.post(
            "/api/datasets/upload",
            files={"file": ("isolation_check.csv", handle, "text/csv")},
            data={"dataset_name": "Isolation check"},
        )
    assert upload.status_code == 200

    listed = {item["id"] for item in client.get("/api/datasets").json()}
    assert "isolation-check" in listed

    after = production_registry.read_text(encoding="utf-8")
    assert after == before
    assert not (production_registry.parent / "isolation-check.db").exists()


def test_olist_schema_and_analysis_endpoints(client, monkeypatch):
    db_path = Path(__file__).resolve().parents[2] / "backend" / "data" / "olist.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", db_path)
    monkeypatch.setattr("backend.config.DATABASE_PATH", db_path)

    schema = client.get("/api/schema", params={"dataset": "olist"})
    assert schema.status_code == 200
    payload = schema.json()
    assert payload["dataset"] == "olist"
    assert any(table["name"] == "orders" for table in payload["tables"])

    supported = client.post(
        "/api/analyze",
        json={"question": "What is the total order-item revenue?", "dataset": "olist", "max_rows": 25},
    )
    assert supported.status_code == 200
    result = supported.json()
    assert result["status"] == "ok"
    assert result["sql"]
    assert result["result"]["rows"]


def test_olist_payment_method_question_uses_payment_template(client, monkeypatch):
    db_path = Path(__file__).resolve().parents[2] / "backend" / "data" / "olist.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", db_path)
    monkeypatch.setattr("backend.config.DATABASE_PATH", db_path)

    response = client.post(
        "/api/analyze",
        json={"question": "What are the most common payment methods in Olist orders?", "dataset": "olist", "max_rows": 25},
    )
    assert response.status_code == 200
    payload = response.json()
    sql = payload["sql"].lower()
    assert "from order_payments" in sql
    assert "payment_type" in sql
    assert "group by payment_type" in sql
    assert "select status" not in sql
    assert "from orders" not in sql


def test_olist_order_status_question_uses_order_status_template(client, monkeypatch):
    db_path = Path(__file__).resolve().parents[2] / "backend" / "data" / "olist.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", db_path)
    monkeypatch.setattr("backend.config.DATABASE_PATH", db_path)

    response = client.post(
        "/api/analyze",
        json={"question": "Show Olist orders by status", "dataset": "olist", "max_rows": 25},
    )
    assert response.status_code == 200
    payload = response.json()
    sql = payload["sql"].lower()
    assert "from orders" in sql
    assert "order_status" in sql
    assert "group by order_status" in sql


def test_olist_payment_type_question_uses_payment_type_template(client, monkeypatch):
    db_path = Path(__file__).resolve().parents[2] / "backend" / "data" / "olist.db"
    monkeypatch.setattr("backend.main.DATABASE_PATH", db_path)
    monkeypatch.setattr("backend.config.DATABASE_PATH", db_path)

    response = client.post(
        "/api/analyze",
        json={"question": "Which payment type is used most frequently?", "dataset": "olist", "max_rows": 25},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    sql = payload["sql"].lower()
    assert "from order_payments" in sql
    assert "payment_type" in sql
    assert "group by payment_type" in sql
    assert "order by payment_count desc" in sql


def test_analyze_supported_and_unsupported(client):
    supported = client.post(
        "/api/analyze",
        json={"question": "Which five products generated the highest sales?", "dataset": "sales", "max_rows": 100},
    )
    assert supported.status_code == 200
    payload = supported.json()
    assert payload["status"] == "ok"
    assert payload["sql"]
    assert payload["result"]["rows"]
    assert payload["chart"]["type"] == "bar"
    assert payload["correction_attempts"] == 0

    unsupported = client.post(
        "/api/analyze",
        json={"question": "Which employees handled the most orders?", "dataset": "sales"},
    )
    assert unsupported.status_code == 200
    body = unsupported.json()
    assert body["status"] == "unsupported"
    assert body["sql"] == ""
    assert body["result"]["rows"] == []


def test_evaluation_runs_real_cases(db_path):
    init_database(db_path)
    report = run_evaluation(db_path)
    metrics = report["metrics"]
    assert metrics["total_test_cases"] == 16
    assert metrics["execution_success_rate"] == 1
    assert metrics["correctness_rate"] == 1
    assert metrics["safety_pass_rate"] == 1
    assert report["failures"] == []


def test_registry_relative_paths_are_stored_and_resolved(tmp_path, monkeypatch):
    data_dir = tmp_path / "backend" / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    registry_path = uploads_dir / "registry.json"
    db_path = uploads_dir / "demo-upload.db"
    db_path.write_bytes(b"stub")
    monkeypatch.setattr(backend_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(backend_config, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(backend_config, "UPLOAD_REGISTRY_PATH", registry_path)

    registry_path.write_text(
        json.dumps({"demo-upload": {"id": "demo-upload", "name": "Demo upload", "path": "uploads/demo-upload.db", "description": "Uploaded dataset: Demo upload", "currency": "USD"}}),
        encoding="utf-8",
    )

    entries = backend_config._load_uploaded_dataset_registry()
    assert "demo-upload" in entries
    assert entries["demo-upload"]["path"] == db_path
    assert registry_path.read_text(encoding="utf-8")

    second_db = uploads_dir / "second-upload.db"
    second_db.write_bytes(b"stub")

    stored = backend_config.register_uploaded_dataset("second-upload", "Second upload", second_db)
    assert Path(stored["path"]) == second_db
    assert "uploads/demo-upload.db" in registry_path.read_text(encoding="utf-8")
    assert "uploads/second-upload.db" in registry_path.read_text(encoding="utf-8")


def test_registry_legacy_windows_absolute_path_is_resolved_when_valid(tmp_path, monkeypatch):
    if os.name != "nt":
        return

    data_dir = tmp_path / "backend" / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    db_path = uploads_dir / "legacy.db"
    db_path.write_bytes(b"stub")
    registry_path = uploads_dir / "registry.json"
    legacy_path = str(db_path.resolve())

    monkeypatch.setattr(backend_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(backend_config, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(backend_config, "UPLOAD_REGISTRY_PATH", registry_path)
    registry_path.write_text(
        json.dumps({"legacy": {"id": "legacy", "name": "Legacy", "path": legacy_path, "description": "Legacy dataset", "currency": "USD"}}),
        encoding="utf-8",
    )

    entries = backend_config._load_uploaded_dataset_registry()
    assert "legacy" in entries
    assert entries["legacy"]["path"] == db_path


def test_registry_ignores_missing_database_and_rejects_outside_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "backend" / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    registry_path = uploads_dir / "registry.json"
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"outside")

    monkeypatch.setattr(backend_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(backend_config, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(backend_config, "UPLOAD_REGISTRY_PATH", registry_path)

    registry_path.write_text(
        json.dumps({
            "missing": {"id": "missing", "name": "Missing", "path": str(uploads_dir / "missing.db"), "description": "No file here", "currency": "USD"},
            "outside": {"id": "outside", "name": "Outside", "path": str(outside), "description": "Outside allowed dir", "currency": "USD"},
        }),
        encoding="utf-8",
    )

    entries = backend_config._load_uploaded_dataset_registry()
    assert "missing" not in entries
    assert "outside" not in entries
    assert backend_config._normalize_registry_path(str(outside)) is None


def test_delete_uploaded_dataset_removes_registry_and_db(client, tmp_path):
    csv_path = tmp_path / "delete_me.csv"
    csv_path.write_text(
        "region,sales\nNorth,120\nSouth,90\n",
        encoding="utf-8",
    )

    with csv_path.open("rb") as handle:
        uploaded = client.post(
            "/api/datasets/upload",
            files={"file": ("delete_me.csv", handle, "text/csv")},
            data={"dataset_name": "Delete me"},
        )

    assert uploaded.status_code == 200
    dataset_id = uploaded.json()["dataset"]["id"]

    delete_response = client.delete(f"/api/datasets/{dataset_id}")
    assert delete_response.status_code == 200
    payload = delete_response.json()
    assert payload["status"] == "ok"
    assert payload["dataset_id"] == dataset_id

    listing = client.get("/api/datasets")
    assert listing.status_code == 200
    ids = {item["id"] for item in listing.json()}
    assert dataset_id not in ids

    uploaded_db = Path(__file__).resolve().parents[2] / "backend" / "data" / "uploads" / f"{dataset_id}.db"
    assert not uploaded_db.exists()


def test_delete_uploaded_dataset_rejects_builtin_unknown_and_unsafe_ids(client, monkeypatch, tmp_path):
    sales = client.delete("/api/datasets/sales")
    assert sales.status_code == 403

    missing = client.delete("/api/datasets/ghost-dataset")
    assert missing.status_code == 404

    data_dir = tmp_path / "backend" / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    registry_path = uploads_dir / "registry.json"
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"outside")
    registry_path.write_text(
        json.dumps({"unsafe": {"id": "unsafe", "name": "Unsafe", "path": str(outside), "description": "Bad path", "currency": "USD"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("backend.config.DATA_DIR", data_dir)
    monkeypatch.setattr("backend.config.UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr("backend.config.UPLOAD_REGISTRY_PATH", registry_path)
    monkeypatch.setattr("backend.main.DATASETS", {"unsafe": {"id": "unsafe", "name": "Unsafe", "path": outside, "currency": "USD"}})
    monkeypatch.setattr("backend.config.DATASETS", {"unsafe": {"id": "unsafe", "name": "Unsafe", "path": outside, "currency": "USD"}})

    unsafe = client.delete("/api/datasets/unsafe")
    assert unsafe.status_code == 400
    assert outside.exists()


def test_delete_uploaded_dataset_handles_missing_database_without_touching_unrelated_files(client, monkeypatch, tmp_path):
    data_dir = tmp_path / "backend" / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    registry_path = uploads_dir / "registry.json"
    good_db = uploads_dir / "keep.db"
    good_db.write_bytes(b"keep")
    missing_db = uploads_dir / "missing.db"

    registry_path.write_text(
        json.dumps({
            "missing": {"id": "missing", "name": "Missing", "path": "uploads/missing.db", "description": "Missing dataset", "currency": "USD"},
            "keep": {"id": "keep", "name": "Keep", "path": "uploads/keep.db", "description": "Related dataset", "currency": "USD"},
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr("backend.config.DATA_DIR", data_dir)
    monkeypatch.setattr("backend.config.UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr("backend.config.UPLOAD_REGISTRY_PATH", registry_path)

    missing = client.delete("/api/datasets/missing")
    assert missing.status_code == 404
    assert missing_db.exists() is False
    assert good_db.exists()

    keep = client.delete("/api/datasets/keep")
    assert keep.status_code == 200
    assert not good_db.exists()


def test_evaluation_endpoints(client):
    empty = client.get("/api/evaluation")
    assert empty.status_code == 200
    assert empty.json() == {} or "metrics" not in empty.json() or empty.json() == {}

    ran = client.post("/api/evaluation/run", json={})
    assert ran.status_code == 200
    payload = ran.json()
    assert payload["metrics"]["total_test_cases"] == 16
    assert payload["metrics"]["safety_pass_rate"] == 1

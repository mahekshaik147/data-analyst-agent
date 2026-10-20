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
    ok = client.post("/api/query", json={"sql": "SELECT COUNT(*) AS n FROM customers"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["columns"] == ["n"]
    assert body["rows"][0]["n"] == 32
    assert body["status"] == "ok"

    blocked = client.post("/api/query", json={"sql": "DELETE FROM customers"})
    assert blocked.status_code == 400


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
    assert metrics["total_test_cases"] == 12
    assert metrics["execution_success_rate"] == 1
    assert metrics["correctness_rate"] == 1
    assert metrics["safety_pass_rate"] == 1
    assert report["failures"] == []


def test_evaluation_endpoints(client):
    empty = client.get("/api/evaluation")
    assert empty.status_code == 200
    assert empty.json() == {} or "metrics" not in empty.json() or empty.json() == {}

    ran = client.post("/api/evaluation/run", json={})
    assert ran.status_code == 200
    payload = ran.json()
    assert payload["metrics"]["total_test_cases"] == 12
    assert payload["metrics"]["safety_pass_rate"] == 1

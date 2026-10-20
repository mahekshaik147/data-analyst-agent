from backend.db import init_database, inspect_schema


def test_init_database_is_idempotent(tmp_path):
    path = tmp_path / "sales.db"
    init_database(path)
    init_database(path)
    schema = inspect_schema(path)
    names = {table["name"] for table in schema["tables"]}
    assert names == {"customers", "products", "orders", "order_items"}
    counts = {table["name"]: table["row_count"] for table in schema["tables"]}
    assert counts["customers"] == 32
    assert counts["products"] == 20
    assert counts["orders"] == 180
    assert counts["order_items"] > counts["orders"]
    assert all(table["sample_rows"] for table in schema["tables"])
    assert schema["relationships"]

import pytest

from backend.sql_safety import UnsafeSqlError, validate_select


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "SELECT name, city FROM customers ORDER BY name LIMIT 5",
        "WITH cte AS (SELECT id FROM orders) SELECT * FROM cte",
        "SELECT c.name FROM customers c JOIN orders o ON o.customer_id = c.id",
        "SELECT status, COUNT(*) AS n FROM orders GROUP BY status",
    ],
)
def test_allows_single_select_statements(sql):
    validated = validate_select(sql, max_rows=10)
    assert "LIMIT" in validated.sql.upper()


def test_caps_existing_limit():
    validated = validate_select("SELECT * FROM products LIMIT 5000", max_rows=25)
    assert validated.sql.upper().endswith("LIMIT 25") or "LIMIT 25" in validated.sql.upper()


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO customers (name, email, city, region, created_at) VALUES ('a','b','c','d','2024-01-01')",
        "UPDATE products SET stock = 0",
        "DELETE FROM orders",
        "DROP TABLE products",
        "ALTER TABLE products ADD COLUMN color TEXT",
        "CREATE TABLE extra (id INTEGER)",
        "ATTACH DATABASE 'other.db' AS extra",
        "PRAGMA table_info(orders)",
        "SELECT 1; SELECT 2",
        "SELECT load_extension('x')",
        "SELECT readfile('secrets.txt')",
        "",
    ],
)
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSqlError):
        validate_select(sql, max_rows=10)

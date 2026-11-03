from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp
from time import perf_counter
from typing import Any

from backend.analyze import analyze_question
from backend.query import QueryExecutionError, execute_readonly
from backend.sql_safety import UnsafeSqlError

_last_report: dict[str, Any] | None = None
_history: list[dict[str, str | int]] = []


def current_report() -> dict[str, Any]:
    return _last_report or {}


def run_evaluation(path: Path) -> dict[str, Any]:
    global _last_report
    cases = _build_cases(path)
    failures: list[dict[str, str]] = []
    difficulty_hits: dict[str, list[bool]] = {"easy": [], "medium": [], "safety": []}
    execution_flags: list[bool] = []
    correctness_flags: list[bool] = []
    safety_flags: list[bool] = []
    latencies: list[int] = []

    for case in cases:
        started = perf_counter()
        try:
            passed, error, sql = case["run"]()
        except Exception as exc:
            passed, error, sql = False, str(exc), ""
        latency = int((perf_counter() - started) * 1000)
        latencies.append(latency)
        difficulty_hits.setdefault(case["difficulty"], []).append(passed)

        kind = case["kind"]
        if kind == "execution":
            execution_flags.append(passed)
            correctness_flags.append(passed)
        elif kind == "correctness":
            execution_flags.append(passed)
            correctness_flags.append(passed)
        elif kind == "unsupported":
            correctness_flags.append(passed)
        elif kind == "safety":
            safety_flags.append(passed)

        if not passed:
            failures.append(
                {
                    "question": case["name"],
                    "name": case["name"],
                    "error": error or "Assertion failed",
                    "explanation": case["explanation"],
                    "sql": sql or "",
                }
            )

    history_entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_test_cases": len(cases),
        "status": "complete" if not failures else "complete_with_failures",
    }
    _history.append(history_entry)
    report = {
        "metrics": {
            "execution_success_rate": _rate(execution_flags),
            "correctness_rate": _rate(correctness_flags),
            "safety_pass_rate": _rate(safety_flags),
            "average_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "total_test_cases": len(cases),
        },
        "history": list(_history),
        "failures": failures,
        "difficulty": [
            {"level": level, "success_rate": _rate(results)}
            for level, results in difficulty_hits.items()
            if results
        ],
    }
    _last_report = report
    return report


def _build_cases(path: Path) -> list[dict[str, Any]]:
    olist_path = Path(__file__).resolve().parent / "data" / "olist.db"

    def analysis_case(question: str, fragment: str, check, *, dataset_id: str = "sales", dataset_path: Path | None = None):
        def run() -> tuple[bool, str | None, str]:
            result = analyze_question(dataset_path or path, question, 100, dataset_id=dataset_id)
            sql = result.get("sql") or ""
            if result.get("status") != "ok":
                return False, result.get("answer") or "Analysis did not succeed.", sql
            if fragment.lower() not in sql.lower():
                return False, "Generated SQL did not match the expected template.", sql
            problem = check(result)
            return problem is None, problem, sql

        return run

    def unsupported_case(question: str, *, dataset_id: str = "sales", dataset_path: Path | None = None):
        def run() -> tuple[bool, str | None, str]:
            result = analyze_question(dataset_path or path, question, 100, dataset_id=dataset_id)
            if result.get("status") != "unsupported":
                return False, "Expected an unsupported response.", result.get("sql") or ""
            if result.get("sql"):
                return False, "Unsupported questions must not execute SQL.", result.get("sql") or ""
            return True, None, ""

        return run

    def query_ok(sql: str):
        def run() -> tuple[bool, str | None, str]:
            result = execute_readonly(path, sql, max_rows=50, timeout_seconds=5)
            if result["status"] != "ok":
                return False, "Safe SELECT failed to execute.", sql
            return True, None, result["sql"]

        return run

    def query_rejected(sql: str):
        def run() -> tuple[bool, str | None, str]:
            try:
                execute_readonly(path, sql, max_rows=50, timeout_seconds=5)
            except UnsafeSqlError:
                return True, None, sql
            except QueryExecutionError as exc:
                return False, f"Unsafe SQL reached execution: {exc}", sql
            return False, "Unsafe SQL was accepted.", sql

        return run

    def temporary_uploaded_case(columns: list[tuple[str, str]], rows: list[tuple[Any, ...]], question: str, fragment: str, check):
        def run() -> tuple[bool, str | None, str]:
            temp_dir = Path(mkdtemp(prefix="uploaded_benchmark_"))
            temp_path = temp_dir / "uploaded_case.db"
            try:
                with sqlite3.connect(temp_path) as connection:
                    column_sql = ", ".join(f'"{name}" {db_type}' for name, db_type in columns)
                    connection.execute(f'CREATE TABLE uploaded_data ({column_sql})')
                    if rows:
                        placeholders = ", ".join("?" for _ in columns)
                        connection.executemany(
                            f"INSERT INTO uploaded_data VALUES ({placeholders})",
                            rows,
                        )
                    connection.commit()

                result = analyze_question(temp_path, question, 100, dataset_id="uploaded_benchmark_case")
                sql = result.get("sql") or ""
                if result.get("status") != "ok":
                    return False, result.get("answer") or "Uploaded dataset analysis did not succeed.", sql
                if fragment.lower() not in sql.lower():
                    return False, "Generated SQL did not match the expected uploaded-dataset template.", sql
                problem = check(result)
                return problem is None, problem, sql
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return run

    def temporary_uploaded_unsupported_case(columns: list[tuple[str, str]], rows: list[tuple[Any, ...]], question: str):
        def run() -> tuple[bool, str | None, str]:
            temp_dir = Path(mkdtemp(prefix="uploaded_benchmark_"))
            temp_path = temp_dir / "uploaded_case.db"
            try:
                with sqlite3.connect(temp_path) as connection:
                    column_sql = ", ".join(f'"{name}" {db_type}' for name, db_type in columns)
                    connection.execute(f'CREATE TABLE uploaded_data ({column_sql})')
                    if rows:
                        placeholders = ", ".join("?" for _ in columns)
                        connection.executemany(
                            f"INSERT INTO uploaded_data VALUES ({placeholders})",
                            rows,
                        )
                    connection.commit()

                result = analyze_question(temp_path, question, 100, dataset_id="uploaded_benchmark_case")
                if result.get("status") != "unsupported":
                    return False, "Expected an unsupported response for a missing uploaded dimension.", result.get("sql") or ""
                if result.get("sql"):
                    return False, "Unsupported uploaded-dataset questions must not execute SQL.", result.get("sql") or ""
                return True, None, ""
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return run

    def total_sales_check(result: dict) -> str | None:
        rows = result["result"]["rows"]
        if not rows or not rows[0].get("total_sales"):
            return "Total sales should be a positive number."
        return None

    def top_products_check(result: dict) -> str | None:
        rows = result["result"]["rows"]
        if len(rows) != 5:
            return f"Expected 5 top products, received {len(rows)}."
        sales = [row.get("sales") or 0 for row in rows]
        if sales != sorted(sales, reverse=True):
            return "Top products were not sorted by sales descending."
        return None

    def monthly_check(result: dict) -> str | None:
        if len(result["result"]["rows"]) < 2:
            return "Monthly sales should return multiple months."
        return None

    def category_check(result: dict) -> str | None:
        if not result["result"]["rows"]:
            return "Category sales returned no rows."
        return None

    def order_count_check(result: dict) -> str | None:
        total = sum(int(row.get("order_count") or 0) for row in result["result"]["rows"])
        if total <= 0:
            return "Order counts should be greater than zero."
        return None

    cases = [
        {
            "name": "Total sales",
            "kind": "execution",
            "difficulty": "easy",
            "explanation": "Natural-language total sales should compile to a SUM over order items.",
            "run": analysis_case("What is the total sales revenue?", "SUM(oi.quantity * oi.unit_price)", total_sales_check),
        },
        {
            "name": "Top five products",
            "kind": "correctness",
            "difficulty": "easy",
            "explanation": "Top-product questions should return five descending sales rows.",
            "run": analysis_case("Which five products generated the highest sales?", "ORDER BY sales DESC", top_products_check),
        },
        {
            "name": "Monthly sales",
            "kind": "execution",
            "difficulty": "medium",
            "explanation": "Monthly trend questions should group sales by year-month.",
            "run": analysis_case("What is the monthly order trend?", "strftime('%Y-%m'", monthly_check),
        },
        {
            "name": "Sales by category",
            "kind": "execution",
            "difficulty": "medium",
            "explanation": "Category questions should aggregate sales by product category.",
            "run": analysis_case("Which product categories have the highest revenue?", "p.category", category_check),
        },
        {
            "name": "Order counts",
            "kind": "execution",
            "difficulty": "easy",
            "explanation": "Order-count questions should group the orders table by status.",
            "run": analysis_case("How many orders are there?", "COUNT(*)", order_count_check),
        },
        {
            "name": "Unsupported employees question",
            "kind": "unsupported",
            "difficulty": "medium",
            "explanation": "Questions about employees should not invent a table that does not exist.",
            "run": unsupported_case("Which employees handled the most orders?"),
        },
        {
            "name": "Safe CTE select",
            "kind": "execution",
            "difficulty": "medium",
            "explanation": "A WITH clause wrapping a SELECT should be allowed.",
            "run": query_ok("WITH totals AS (SELECT COUNT(*) AS n FROM orders) SELECT n FROM totals"),
        },
        {
            "name": "Reject INSERT",
            "kind": "safety",
            "difficulty": "safety",
            "explanation": "Write statements must be rejected before execution.",
            "run": query_rejected(
                "INSERT INTO products (name, category, unit_price, stock) VALUES ('x', 'y', 1, 1)"
            ),
        },
        {
            "name": "Reject DROP",
            "kind": "safety",
            "difficulty": "safety",
            "explanation": "DDL that destroys tables must be rejected.",
            "run": query_rejected("DROP TABLE customers"),
        },
        {
            "name": "Reject multiple statements",
            "kind": "safety",
            "difficulty": "safety",
            "explanation": "Stacked queries must be rejected even if the first statement is a SELECT.",
            "run": query_rejected("SELECT 1; DROP TABLE orders"),
        },
        {
            "name": "Reject PRAGMA",
            "kind": "safety",
            "difficulty": "safety",
            "explanation": "PRAGMA statements are not allowed through the query endpoint.",
            "run": query_rejected("PRAGMA table_info(orders)"),
        },
        {
            "name": "Reject load_extension",
            "kind": "safety",
            "difficulty": "safety",
            "explanation": "Extension loading is treated as an unsafe function.",
            "run": query_rejected("SELECT load_extension('x')"),
        },
        {
            "name": "Olist payment methods",
            "kind": "execution",
            "difficulty": "medium",
            "explanation": "Olist payment-type analysis should aggregate the payment_type column from order_payments.",
            "run": analysis_case(
                "What are the most common payment methods in Olist orders?",
                "payment_type",
                lambda result: None if result["result"]["rows"] else "Olist payment method analysis returned no rows.",
                dataset_id="olist",
                dataset_path=olist_path,
            ),
        },
        {
            "name": "Olist total revenue",
            "kind": "execution",
            "difficulty": "medium",
            "explanation": "Olist revenue should sum order item prices and return a positive total.",
            "run": analysis_case(
                "What is the total order-item revenue?",
                "SUM(oi.price)",
                lambda result: None if (result["result"]["rows"] and (result["result"]["rows"][0].get("total_revenue") or 0) > 0) else "Olist total revenue should be positive.",
                dataset_id="olist",
                dataset_path=olist_path,
            ),
        },
        {
            "name": "Uploaded regional sales",
            "kind": "execution",
            "difficulty": "medium",
            "explanation": "Uploaded datasets with a region column should group sales by region and not by product.",
            "run": temporary_uploaded_case(
                [("region", "TEXT"), ("product", "TEXT"), ("sales", "REAL")],
                [("North", "Laptop", 120.0), ("South", "Phone", 90.0), ("East", "Monitor", 150.0)],
                "Which region has the highest sales?",
                "GROUP BY \"region\"",
                lambda result: None if result["result"]["rows"] else "Uploaded regional sales analysis returned no rows.",
            ),
        },
        {
            "name": "Uploaded missing region is unsupported",
            "kind": "unsupported",
            "difficulty": "medium",
            "explanation": "A request for a region dimension must be rejected when the uploaded dataset has no region column.",
            "run": temporary_uploaded_unsupported_case(
                [("product", "TEXT"), ("category", "TEXT"), ("sales", "REAL")],
                [("Laptop", "Electronics", 120.0), ("Phone", "Electronics", 90.0), ("Monitor", "Office", 150.0)],
                "Which region has the highest sales?",
            ),
        },
    ]
    return cases


def _rate(flags: list[bool]) -> float:
    if not flags:
        return 0.0
    return round(sum(1 for flag in flags if flag) / len(flags), 4)

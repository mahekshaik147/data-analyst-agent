from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
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
    def analysis_case(question: str, fragment: str, check):
        def run() -> tuple[bool, str | None, str]:
            result = analyze_question(path, question, 100)
            sql = result.get("sql") or ""
            if result.get("status") != "ok":
                return False, result.get("answer") or "Analysis did not succeed.", sql
            if fragment.lower() not in sql.lower():
                return False, "Generated SQL did not match the expected template.", sql
            problem = check(result)
            return problem is None, problem, sql

        return run

    def unsupported_case(question: str):
        def run() -> tuple[bool, str | None, str]:
            result = analyze_question(path, question, 100)
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

    return [
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
    ]


def _rate(flags: list[bool]) -> float:
    if not flags:
        return 0.0
    return round(sum(1 for flag in flags if flag) / len(flags), 4)

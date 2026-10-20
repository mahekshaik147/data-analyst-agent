from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.config import QUERY_TIMEOUT_SECONDS, clamp_max_rows
from backend.query import QueryExecutionError, execute_readonly

COMPLETED_ORDERS = "o.status IN ('completed', 'shipped')"


@dataclass(frozen=True)
class AnalysisPlan:
    intent: str
    sql: str
    chart_type: str
    chart_title: str
    x_axis: str | None
    y_axis: str | None


def analyze_question(path: Path, question: str, max_rows: int | None) -> dict:
    limit = clamp_max_rows(max_rows)
    started_sql = ""
    plan = match_question(question, limit)
    empty_result = {
        "columns": [],
        "rows": [],
        "row_count": 0,
        "execution_time_ms": 0,
        "status": "unsupported",
    }
    if plan is None:
        return {
            "answer": (
                "I can answer questions about total sales, monthly sales, top products, "
                "order counts, sales by category, top customers, and low-stock products. "
                "Try one of those topics, or inspect the dataset schema first."
            ),
            "findings": [
                "This first version uses deterministic SQL templates rather than an LLM.",
                "Unsupported questions return an honest message instead of invented numbers.",
            ],
            "sql": "",
            "result": empty_result,
            "chart": {"type": "table", "title": "No query executed"},
            "execution_time_ms": 0,
            "correction_attempts": 0,
            "status": "unsupported",
        }

    try:
        started_sql = plan.sql
        executed = execute_readonly(
            path,
            plan.sql,
            max_rows=limit,
            timeout_seconds=QUERY_TIMEOUT_SECONDS,
        )
    except QueryExecutionError as exc:
        return {
            "answer": f"The generated SQL could not be executed: {exc}",
            "findings": [],
            "sql": started_sql,
            "result": {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": 0,
                "status": "error",
            },
            "chart": {"type": "table", "title": "Query failed"},
            "execution_time_ms": 0,
            "correction_attempts": 0,
            "status": "error",
        }

    answer, findings = _summarize(plan, executed)
    return {
        "answer": answer,
        "findings": findings,
        "sql": executed["sql"],
        "result": {
            "columns": executed["columns"],
            "rows": executed["rows"],
            "row_count": executed["row_count"],
            "execution_time_ms": executed["execution_time_ms"],
            "status": executed["status"],
        },
        "chart": {
            "type": plan.chart_type,
            "title": plan.chart_title,
            "x_axis": plan.x_axis,
            "y_axis": plan.y_axis,
        },
        "execution_time_ms": executed["execution_time_ms"],
        "correction_attempts": 0,
        "status": "ok",
    }


def match_question(question: str, limit: int) -> AnalysisPlan | None:
    text = _normalize(question)
    if not text:
        return None

    if _matches(text, ["employee", "employees", "staff", "salesperson"]):
        return None

    if _matches(text, ["low stock", "lowest stock", "out of stock", "inventory"]):
        return AnalysisPlan(
            intent="low_stock",
            sql=f"""
                SELECT name AS product, stock
                FROM products
                ORDER BY stock ASC, name ASC
                LIMIT {min(10, limit)}
            """,
            chart_type="bar",
            chart_title="Products with the lowest stock",
            x_axis="product",
            y_axis="stock",
        )

    if _matches(text, ["category", "categories"]):
        return AnalysisPlan(
            intent="sales_by_category",
            sql=f"""
                SELECT p.category AS category, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS sales
                FROM order_items oi
                JOIN products p ON p.id = oi.product_id
                JOIN orders o ON o.id = oi.order_id
                WHERE {COMPLETED_ORDERS}
                GROUP BY p.category
                ORDER BY sales DESC
                LIMIT {limit}
            """,
            chart_type="pie",
            chart_title="Sales by category",
            x_axis="category",
            y_axis="sales",
        )

    if _matches(text, ["customer", "customers"]):
        top_n = 10 if "ten" in text or "10" in text else min(10, limit)
        return AnalysisPlan(
            intent="top_customers",
            sql=f"""
                SELECT c.name AS customer, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS order_value
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                JOIN customers c ON c.id = o.customer_id
                WHERE {COMPLETED_ORDERS}
                GROUP BY c.id, c.name
                ORDER BY order_value DESC
                LIMIT {top_n}
            """,
            chart_type="bar",
            chart_title="Top customers by order value",
            x_axis="customer",
            y_axis="order_value",
        )

    if _matches(text, ["monthly", "month", "trend"]):
        return AnalysisPlan(
            intent="monthly_sales",
            sql=f"""
                SELECT strftime('%Y-%m', o.order_date) AS month,
                       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS sales
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {COMPLETED_ORDERS}
                GROUP BY month
                ORDER BY month
                LIMIT {limit}
            """,
            chart_type="line",
            chart_title="Monthly sales",
            x_axis="month",
            y_axis="sales",
        )

    if _matches(text, ["top product", "highest sales", "best selling", "best-selling", "products generated"]):
        top_n = 5 if "five" in text or "5" in text else min(5, limit)
        return AnalysisPlan(
            intent="top_products",
            sql=f"""
                SELECT p.name AS product, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS sales
                FROM order_items oi
                JOIN products p ON p.id = oi.product_id
                JOIN orders o ON o.id = oi.order_id
                WHERE {COMPLETED_ORDERS}
                GROUP BY p.id, p.name
                ORDER BY sales DESC
                LIMIT {top_n}
            """,
            chart_type="bar",
            chart_title="Top products by sales",
            x_axis="product",
            y_axis="sales",
        )

    if _matches(text, ["order count", "orders", "how many order", "number of order"]):
        return AnalysisPlan(
            intent="order_counts",
            sql="""
                SELECT status, COUNT(*) AS order_count
                FROM orders
                GROUP BY status
                ORDER BY order_count DESC
            """,
            chart_type="bar",
            chart_title="Orders by status",
            x_axis="status",
            y_axis="order_count",
        )

    if _matches(text, ["total sales", "total revenue", "overall sales", "how much revenue"]):
        return AnalysisPlan(
            intent="total_sales",
            sql=f"""
                SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_sales,
                       COUNT(DISTINCT o.id) AS completed_orders
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                WHERE {COMPLETED_ORDERS}
            """,
            chart_type="table",
            chart_title="Total sales",
            x_axis=None,
            y_axis="total_sales",
        )

    return None


def _normalize(question: str) -> str:
    lowered = question.lower()
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def _matches(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _summarize(plan: AnalysisPlan, executed: dict) -> tuple[str, list[str]]:
    rows = executed["rows"]
    if not rows:
        return "The query ran successfully but returned no rows.", ["No matching records were found."]

    if plan.intent == "total_sales":
        total = rows[0].get("total_sales") or 0
        orders = rows[0].get("completed_orders") or 0
        return (
            f"Total sales from completed and shipped orders are ${total:,.2f} across {orders} orders.",
            [
                "Cancelled orders are excluded from revenue.",
                "Line-item sales are quantity multiplied by the recorded unit price.",
            ],
        )

    if plan.intent == "monthly_sales":
        peak = max(rows, key=lambda row: row.get("sales") or 0)
        return (
            f"Monthly sales cover {len(rows)} months. The peak month is {peak.get('month')} at ${peak.get('sales') or 0:,.2f}.",
            [f"{row['month']}: ${row['sales']:,.2f}" for row in rows[:5]],
        )

    if plan.intent == "top_products":
        leader = rows[0]
        return (
            f"{leader.get('product')} is the top product with ${leader.get('sales') or 0:,.2f} in sales.",
            [f"{row['product']}: ${row['sales']:,.2f}" for row in rows],
        )

    if plan.intent == "sales_by_category":
        leader = rows[0]
        return (
            f"{leader.get('category')} is the highest-revenue category at ${leader.get('sales') or 0:,.2f}.",
            [f"{row['category']}: ${row['sales']:,.2f}" for row in rows],
        )

    if plan.intent == "order_counts":
        total = sum(int(row.get("order_count") or 0) for row in rows)
        return (
            f"There are {total} orders in the dataset, grouped by status.",
            [f"{row['status']}: {row['order_count']} orders" for row in rows],
        )

    if plan.intent == "top_customers":
        leader = rows[0]
        return (
            f"{leader.get('customer')} is the top customer with ${leader.get('order_value') or 0:,.2f} in order value.",
            [f"{row['customer']}: ${row['order_value']:,.2f}" for row in rows[:5]],
        )

    if plan.intent == "low_stock":
        leader = rows[0]
        return (
            f"{leader.get('product')} currently has the lowest stock ({leader.get('stock')} units).",
            [f"{row['product']}: {row['stock']} units" for row in rows[:5]],
        )

    return "The query completed successfully.", [f"{len(rows)} rows were returned."]

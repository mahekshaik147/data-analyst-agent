from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.config import QUERY_TIMEOUT_SECONDS, clamp_max_rows
from backend.db import inspect_schema
from backend.query import QueryExecutionError, execute_readonly

COMPLETED_ORDERS = "o.status IN ('completed', 'shipped')"
OLIST_SALES_STATUSES = "o.order_status IN ('delivered', 'shipped', 'processing', 'invoiced')"


@dataclass(frozen=True)
class AnalysisPlan:
    intent: str
    sql: str
    chart_type: str
    chart_title: str
    x_axis: str | None
    y_axis: str | None
    dataset_id: str = "sales"


def analyze_question(path: Path, question: str, max_rows: int | None, dataset_id: str = "sales") -> dict:
    limit = clamp_max_rows(max_rows)
    started_sql = ""
    plan = match_question(question, limit, dataset_id, path)
    empty_result = {
        "columns": [],
        "rows": [],
        "row_count": 0,
        "execution_time_ms": 0,
        "status": "unsupported",
    }
    if plan is None:
        answer = _unsupported_answer_for_question(path, dataset_id, question)
        return {
            "answer": answer,
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


def match_question(question: str, limit: int, dataset_id: str = "sales", path: Path | None = None) -> AnalysisPlan | None:
    text = _normalize(question)
    if not text:
        return None

    if dataset_id not in {"sales", "olist"}:
        uploaded_plan = _match_uploaded_dataset_question(path=path, question=question, limit=limit, dataset_id=dataset_id)
        if uploaded_plan is not None:
            return uploaded_plan
        return None

    if dataset_id == "olist":
        if _matches(
            text,
            ["total revenue", "total order item revenue", "order item revenue", "total sales", "how much revenue"],
        ):
            return AnalysisPlan(
                intent="olist_total_revenue",
                sql=f"""
                    SELECT ROUND(SUM(oi.price), 2) AS total_revenue,
                           COUNT(*) AS order_items,
                           COUNT(DISTINCT oi.order_id) AS total_orders
                    FROM order_items oi
                    JOIN orders o ON o.order_id = oi.order_id
                    WHERE {OLIST_SALES_STATUSES}
                """,
                chart_type="table",
                chart_title="Total order-item revenue",
                x_axis=None,
                y_axis="total_revenue",
                dataset_id="olist",
            )

        if _matches(
            text,
            [
                "payment type",
                "payment types",
                "payment method",
                "payment methods",
                "most common payment",
                "most frequently used payment",
                "used most frequently",
            ],
        ):
            return AnalysisPlan(
                intent="olist_payment_methods",
                sql=f"""
                    SELECT payment_type AS payment_method,
                           COUNT(*) AS payment_count
                    FROM order_payments
                    GROUP BY payment_type
                    ORDER BY payment_count DESC, payment_type ASC
                    LIMIT {limit}
                """,
                chart_type="bar",
                chart_title="Most common payment methods",
                x_axis="payment_method",
                y_axis="payment_count",
                dataset_id="olist",
            )

        if _matches(
            text,
            [
                "order count",
                "how many orders",
                "how many order",
                "number of orders",
                "number of order",
                "order status",
                "orders by status",
                "by status",
            ],
        ):
            return AnalysisPlan(
                intent="olist_order_counts",
                sql="""
                    SELECT order_status, COUNT(*) AS order_count
                    FROM orders
                    GROUP BY order_status
                    ORDER BY order_count DESC
                """,
                chart_type="bar",
                chart_title="Orders by status",
                x_axis="order_status",
                y_axis="order_count",
                dataset_id="olist",
            )

        if _matches(text, ["monthly", "month", "trend"]):
            return AnalysisPlan(
                intent="olist_monthly_sales",
                sql=f"""
                    SELECT strftime('%Y-%m', o.order_purchase_timestamp) AS month,
                           ROUND(SUM(oi.price), 2) AS revenue
                    FROM order_items oi
                    JOIN orders o ON o.order_id = oi.order_id
                    WHERE {OLIST_SALES_STATUSES}
                    GROUP BY month
                    ORDER BY month
                    LIMIT {limit}
                """,
                chart_type="line",
                chart_title="Monthly sales trends",
                x_axis="month",
                y_axis="revenue",
                dataset_id="olist",
            )

        if _matches(text, ["category", "categories"]):
            return AnalysisPlan(
                intent="olist_category_revenue",
                sql=f"""
                    SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
                           ROUND(SUM(oi.price), 2) AS revenue
                    FROM order_items oi
                    JOIN products p ON p.product_id = oi.product_id
                    JOIN orders o ON o.order_id = oi.order_id
                    LEFT JOIN product_category_name_translation t
                      ON t.product_category_name = p.product_category_name
                    WHERE {OLIST_SALES_STATUSES}
                    GROUP BY category
                    ORDER BY revenue DESC
                    LIMIT {limit}
                """,
                chart_type="pie",
                chart_title="Revenue by product category",
                x_axis="category",
                y_axis="revenue",
                dataset_id="olist",
            )

        if _matches(text, ["top product", "highest sales", "best selling", "best-selling", "products generated", "top selling"]):
            top_n = 5 if "five" in text or "5" in text else min(5, limit)
            return AnalysisPlan(
                intent="olist_top_products",
                sql=f"""
                    SELECT p.product_id AS product, ROUND(SUM(oi.price), 2) AS sales
                    FROM order_items oi
                    JOIN products p ON p.product_id = oi.product_id
                    JOIN orders o ON o.order_id = oi.order_id
                    WHERE {OLIST_SALES_STATUSES}
                    GROUP BY p.product_id
                    ORDER BY sales DESC
                    LIMIT {top_n}
                """,
                chart_type="bar",
                chart_title="Top-selling products",
                x_axis="product",
                y_axis="sales",
                dataset_id="olist",
            )

        if _matches(text, ["average review", "review score", "rating", "reviews"]):
            return AnalysisPlan(
                intent="olist_average_review",
                sql="""
                    SELECT ROUND(AVG(review_score), 2) AS avg_review_score,
                           COUNT(*) AS reviews
                    FROM order_reviews
                    WHERE review_score IS NOT NULL
                """,
                chart_type="table",
                chart_title="Average review score",
                x_axis=None,
                y_axis="avg_review_score",
                dataset_id="olist",
            )

        if _matches(text, ["top seller", "sellers", "highest sales seller", "seller revenue"]):
            top_n = 10 if "ten" in text or "10" in text else min(10, limit)
            return AnalysisPlan(
                intent="olist_top_sellers",
                sql=f"""
                    SELECT s.seller_id AS seller, ROUND(SUM(oi.price), 2) AS revenue
                    FROM order_items oi
                    JOIN sellers s ON s.seller_id = oi.seller_id
                    JOIN orders o ON o.order_id = oi.order_id
                    WHERE {OLIST_SALES_STATUSES}
                    GROUP BY s.seller_id
                    ORDER BY revenue DESC
                    LIMIT {top_n}
                """,
                chart_type="bar",
                chart_title="Top sellers by revenue",
                x_axis="seller",
                y_axis="revenue",
                dataset_id="olist",
            )

        if _matches(text, ["average order value", "average order", "order value"]):
            return AnalysisPlan(
                intent="olist_avg_order_value",
                sql="""
                    SELECT ROUND(AVG(order_value), 2) AS avg_order_value,
                           COUNT(*) AS total_orders
                    FROM (
                        SELECT o.order_id, SUM(oi.price) AS order_value
                        FROM orders o
                        JOIN order_items oi ON oi.order_id = o.order_id
                        WHERE o.order_status IN ('delivered', 'shipped', 'processing', 'invoiced')
                        GROUP BY o.order_id
                    )
                """,
                chart_type="table",
                chart_title="Average order value",
                x_axis=None,
                y_axis="avg_order_value",
                dataset_id="olist",
            )

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

    if _matches(text, ["region", "regions"]):
        return AnalysisPlan(
            intent="sales_by_region",
            sql=f"""
                SELECT c.region AS region, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS sales
                FROM order_items oi
                JOIN orders o ON o.id = oi.order_id
                JOIN customers c ON c.id = o.customer_id
                WHERE {COMPLETED_ORDERS}
                GROUP BY c.region
                ORDER BY sales DESC
                LIMIT {limit}
            """,
            chart_type="bar",
            chart_title="Sales by region",
            x_axis="region",
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


def _match_uploaded_dataset_question(path: Path | None, question: str, limit: int, dataset_id: str) -> AnalysisPlan | None:
    if path is None:
        return None

    schema = inspect_schema(path, dataset_id)
    tables = schema.get("tables") or []
    if not tables:
        return None

    text = _normalize(question)
    table = _pick_uploaded_table(tables, text)
    if table is None:
        return None

    dimension = _pick_dimension_column(table["columns"], text)
    metric = _pick_metric_column(table["columns"], text)
    if dimension is None or metric is None:
        return None

    table_name = _quote_identifier(table["name"])
    dim_name = _quote_identifier(dimension["name"])
    metric_name = _quote_identifier(metric["name"])
    sql = (
        f'SELECT {dim_name} AS dimension_value, '
        f'ROUND(SUM({metric_name}), 2) AS total_value '
        f'FROM {table_name} '
        f'GROUP BY {dim_name} '
        f'ORDER BY total_value DESC '
        f'LIMIT {limit}'
    )
    return AnalysisPlan(
        intent="uploaded_dataset_summary",
        sql=sql,
        chart_type="bar",
        chart_title="Summary by dimension",
        x_axis="dimension_value",
        y_axis="total_value",
        dataset_id=dataset_id,
    )


def _pick_uploaded_table(tables: list[dict], text: str) -> dict | None:
    candidates = []
    for table in tables:
        columns = table.get("columns") or []
        names = [_normalize(column["name"]) for column in columns]
        if not columns:
            continue
        score = 0
        if any(name in text for name in names):
            score += 2
        if any(keyword in text for keyword in ("sales", "revenue", "amount", "total", "value", "price", "count")):
            score += 1
        if any(column["name"].lower() in {"region", "category", "state", "country", "customer", "product", "seller", "status"} for column in columns):
            score += 1
        candidates.append((score, table))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1] if candidates[0][0] > 0 else None


def _pick_dimension_column(columns: list[dict], text: str) -> dict | None:
    lowered_text = text.lower()

    requested_dimensions = _requested_dimensions(lowered_text)
    if requested_dimensions:
        for keyword in requested_dimensions:
            for column in columns:
                name = (column.get("name") or "").lower()
                if keyword in name:
                    return column
        return None

    for column in columns:
        name = (column.get("name") or "").lower()
        if any(keyword in name for keyword in ("region", "category", "state", "country", "customer", "product", "seller", "status")):
            return column

    for column in columns:
        name = (column.get("name") or "").lower()
        if (column.get("type") or "").upper() in {"TEXT", "VARCHAR"}:
            return column
    return None


def _requested_dimensions(lowered_text: str) -> list[str]:
    keyword_map = {
        "region": ["region"],
        "category": ["category"],
        "state": ["state"],
        "country": ["country"],
        "customer": ["customer"],
        "product": ["product"],
        "seller": ["seller"],
        "status": ["status"],
    }

    requested_dimensions: list[str] = []
    for _, keywords in keyword_map.items():
        if any(keyword in lowered_text for keyword in keywords):
            requested_dimensions.extend(keywords)
    return requested_dimensions


def _unsupported_answer_for_question(path: Path | None, dataset_id: str, question: str) -> str:
    if path is None or dataset_id in {"sales", "olist"}:
        return (
            "I can answer questions about total sales, monthly sales, sales by region, top products, "
            "order counts, sales by category, top customers, and low-stock products. "
            "Try one of those topics, or inspect the dataset schema first."
        )

    schema = inspect_schema(path, dataset_id)
    tables = schema.get("tables") or []
    if not tables:
        return (
            "The selected dataset does not support that question. Try a supported metric or "
            "inspect the available schema before asking for a summary by a specific dimension."
        )

    text = _normalize(question)
    requested_dimensions = _requested_dimensions(text)
    if requested_dimensions:
        table = _pick_uploaded_table(tables, text)
        if table is not None:
            available = [str(column.get("name") or "").strip() for column in (table.get("columns") or []) if str(column.get("name") or "").strip()]
            missing = []
            for landing in requested_dimensions:
                if not any(landing in (name.lower()) for name in available):
                    missing.append(landing)
            if missing:
                plural = "column" if len(missing) == 1 else "columns"
                names = ", ".join(f"'{item}'" for item in sorted(set(missing)))
                if available:
                    return (
                        f"The selected dataset does not include the requested {plural} {names}. "
                        f"Available fields are: {', '.join(available)}."
                    )
                return f"The selected dataset does not include the requested {plural} {names}."

    return (
        "The selected dataset does not support that question. Try a supported metric or inspect the "
        "available schema before asking for a summary by a specific dimension."
    )


def _pick_metric_column(columns: list[dict], text: str) -> dict | None:
    lowered_text = text.lower()
    keyword_map = {
        "sales": ["sales", "revenue", "amount", "total", "value", "price", "cost"],
        "count": ["count", "total", "qty", "quantity"],
    }

    for label, keywords in keyword_map.items():
        if not any(keyword in lowered_text for keyword in keywords):
            continue
        for column in columns:
            name = (column.get("name") or "").lower()
            column_type = (column.get("type") or "").upper()
            if any(keyword in name for keyword in keywords) and column_type in {"INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"}:
                return column

    for column in columns:
        name = (column.get("name") or "").lower()
        column_type = (column.get("type") or "").upper()
        if any(keyword in name for keyword in ("sales", "revenue", "amount", "total", "value", "price", "cost", "quantity", "qty")) and column_type in {"INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"}:
            return column
    for column in columns:
        column_type = (column.get("type") or "").upper()
        if column_type in {"INTEGER", "REAL", "NUMERIC", "FLOAT", "DOUBLE"}:
            return column
    return None


def _quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


def _matches(text: str, phrases: list[str]) -> bool:
    normalized = text.replace("-", " ")
    for phrase in phrases:
        candidates = {phrase, phrase.replace("-", " ")}
        if any(candidate in text or candidate in normalized for candidate in candidates):
            return True
    return False


def _summarize(plan: AnalysisPlan, executed: dict) -> tuple[str, list[str]]:
    rows = executed["rows"]
    if not rows:
        return "The query ran successfully but returned no rows.", ["No matching records were found."]

    if plan.dataset_id == "olist":
        if plan.intent == "olist_total_revenue":
            total = rows[0].get("total_revenue") or 0
            orders = rows[0].get("total_orders") or 0
            return (
                f"Total order-item revenue for sales-relevant Olist orders is R${total:,.2f} across {orders} orders.",
                [
                    "This definition counts delivered, shipped, processing, and invoiced orders as sales-relevant.",
                    "Revenue uses order_items.price once per item and avoids double-counting from payments or reviews.",
                ],
            )

        if plan.intent == "olist_order_counts":
            total = sum(int(row.get("order_count") or 0) for row in rows)
            return (
                f"There are {total} Olist orders in the dataset, grouped by status.",
                [f"{row['order_status']}: {row['order_count']} orders" for row in rows],
            )

        if plan.intent == "olist_monthly_sales":
            peak = max(rows, key=lambda row: row.get("revenue") or 0)
            return (
                f"Monthly Olist sales cover {len(rows)} months. The peak month is {peak.get('month')} at R${peak.get('revenue') or 0:,.2f}.",
                [f"{row['month']}: R${row['revenue']:,.2f}" for row in rows[:5]],
            )

        if plan.intent == "olist_category_revenue":
            leader = rows[0]
            return (
                f"{leader.get('category')} is the highest-revenue Olist category at R${leader.get('revenue') or 0:,.2f}.",
                [f"{row['category']}: R${row['revenue']:,.2f}" for row in rows],
            )

        if plan.intent == "olist_top_products":
            leader = rows[0]
            return (
                f"{leader.get('product')} is the top-selling Olist product with R${leader.get('sales') or 0:,.2f} in revenue.",
                [f"{row['product']}: R${row['sales']:,.2f}" for row in rows],
            )

        if plan.intent == "olist_payment_methods":
            leader = rows[0]
            return (
                f"The most common payment method is {leader.get('payment_method')} with {leader.get('payment_count')} payments.",
                [f"{row['payment_method']}: {row['payment_count']} payments" for row in rows],
            )

        if plan.intent == "olist_average_review":
            avg = rows[0].get("avg_review_score") or 0
            count = rows[0].get("reviews") or 0
            return (
                f"The average Olist review score is {avg:.2f} across {count} reviews.",
                [f"Average score: {avg:.2f} across {count} reviews"],
            )

        if plan.intent == "olist_top_sellers":
            leader = rows[0]
            return (
                f"Seller {leader.get('seller')} leads Olist revenue with R${leader.get('revenue') or 0:,.2f}.",
                [f"{row['seller']}: R${row['revenue']:,.2f}" for row in rows[:5]],
            )

        if plan.intent == "olist_avg_order_value":
            avg = rows[0].get("avg_order_value") or 0
            count = rows[0].get("total_orders") or 0
            return (
                f"The average Olist order value is R${avg:,.2f} across {count} orders.",
                [f"Average order value: R${avg:,.2f} across {count} orders"],
            )

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

    if plan.intent == "sales_by_region":
        leader = rows[0]
        return (
            f"{leader.get('region')} is the highest-selling region with ${leader.get('sales') or 0:,.2f} in sales.",
            [f"{row['region']}: ${row['sales']:,.2f}" for row in rows],
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
    
    if plan.intent == "uploaded_dataset_summary":
        leader = rows[0]
        grand_total = sum(float(row.get("total_value") or 0) for row in rows)
        return (
            f"{leader.get('dimension_value')} leads with {float(leader.get('total_value') or 0):,.2f} "
            f"out of {grand_total:,.2f} in total.",
            [f"{row['dimension_value']}: {float(row['total_value'] or 0):,.2f}" for row in rows[:5]],
        )
    return "The query completed successfully.", [f"{len(rows)} rows were returned."]

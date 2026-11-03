"""Import the Olist Brazilian E-Commerce CSVs into backend/data/olist.db.

Rerunnable: builds olist.tmp.db first and swaps it in only after validation.
Never touches sales.db. All monetary values are in BRL.
"""
import csv
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "olist_raw"
FINAL_DB = DATA_DIR / "olist.db"
TEMP_DB = DATA_DIR / "olist.tmp.db"
BATCH_SIZE = 5000

SCHEMA = """
CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix TEXT,
    customer_city TEXT,
    customer_state TEXT
);
CREATE TABLE sellers (
    seller_id TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT,
    seller_city TEXT,
    seller_state TEXT
);
CREATE TABLE products (
    product_id TEXT PRIMARY KEY,
    product_category_name TEXT,
    product_name_lenght INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);
CREATE TABLE product_category_name_translation (
    product_category_name TEXT PRIMARY KEY,
    product_category_name_english TEXT NOT NULL
);
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_status TEXT NOT NULL,
    order_purchase_timestamp TEXT,
    order_approved_at TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT
);
CREATE TABLE order_items (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id INTEGER NOT NULL,
    product_id TEXT NOT NULL REFERENCES products(product_id),
    seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date TEXT,
    price REAL NOT NULL,
    freight_value REAL NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);
CREATE TABLE order_payments (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    payment_sequential INTEGER NOT NULL,
    payment_type TEXT,
    payment_installments INTEGER,
    payment_value REAL,
    PRIMARY KEY (order_id, payment_sequential)
);
CREATE TABLE order_reviews (
    review_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    review_score INTEGER,
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TEXT,
    review_answer_timestamp TEXT
);
CREATE INDEX idx_customers_unique ON customers(customer_unique_id);
CREATE INDEX idx_customers_state ON customers(customer_state);
CREATE INDEX idx_products_category ON products(product_category_name);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(order_status);
CREATE INDEX idx_orders_purchase ON orders(order_purchase_timestamp);
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_items_seller ON order_items(seller_id);
CREATE INDEX idx_payments_type ON order_payments(payment_type);
CREATE INDEX idx_reviews_order ON order_reviews(order_id);
"""


def text(v):
    v = (v or "").strip()
    return v or None


def integer(v):
    v = (v or "").strip()
    return int(float(v)) if v else None


def real(v):
    v = (v or "").strip()
    return round(float(v), 2) if v else None


def timestamp(v):
    v = (v or "").strip()
    if not v:
        return None
    datetime.strptime(v, "%Y-%m-%d %H:%M:%S")  # raises on malformed values
    return v


# (table, csv file, [(csv column, db column, converter), ...])
TABLES = [
    ("customers", "olist_customers_dataset.csv", [
        ("customer_id", "customer_id", text),
        ("customer_unique_id", "customer_unique_id", text),
        ("customer_zip_code_prefix", "customer_zip_code_prefix", text),
        ("customer_city", "customer_city", text),
        ("customer_state", "customer_state", text),
    ]),
    ("sellers", "olist_sellers_dataset.csv", [
        ("seller_id", "seller_id", text),
        ("seller_zip_code_prefix", "seller_zip_code_prefix", text),
        ("seller_city", "seller_city", text),
        ("seller_state", "seller_state", text),
    ]),
    ("products", "olist_products_dataset.csv", [
        ("product_id", "product_id", text),
        ("product_category_name", "product_category_name", text),
        ("product_name_lenght", "product_name_lenght", integer),
        ("product_description_lenght", "product_description_lenght", integer),
        ("product_photos_qty", "product_photos_qty", integer),
        ("product_weight_g", "product_weight_g", integer),
        ("product_length_cm", "product_length_cm", integer),
        ("product_height_cm", "product_height_cm", integer),
        ("product_width_cm", "product_width_cm", integer),
    ]),
    ("product_category_name_translation", "product_category_name_translation.csv", [
        ("product_category_name", "product_category_name", text),
        ("product_category_name_english", "product_category_name_english", text),
    ]),
    ("orders", "olist_orders_dataset.csv", [
        ("order_id", "order_id", text),
        ("customer_id", "customer_id", text),
        ("order_status", "order_status", text),
        ("order_purchase_timestamp", "order_purchase_timestamp", timestamp),
        ("order_approved_at", "order_approved_at", timestamp),
        ("order_delivered_carrier_date", "order_delivered_carrier_date", timestamp),
        ("order_delivered_customer_date", "order_delivered_customer_date", timestamp),
        ("order_estimated_delivery_date", "order_estimated_delivery_date", timestamp),
    ]),
    ("order_items", "olist_order_items_dataset.csv", [
        ("order_id", "order_id", text),
        ("order_item_id", "order_item_id", integer),
        ("product_id", "product_id", text),
        ("seller_id", "seller_id", text),
        ("shipping_limit_date", "shipping_limit_date", timestamp),
        ("price", "price", real),
        ("freight_value", "freight_value", real),
    ]),
    ("order_payments", "olist_order_payments_dataset.csv", [
        ("order_id", "order_id", text),
        ("payment_sequential", "payment_sequential", integer),
        ("payment_type", "payment_type", text),
        ("payment_installments", "payment_installments", integer),
        ("payment_value", "payment_value", real),
    ]),
    ("order_reviews", "olist_order_reviews_dataset.csv", [
        ("review_id", "review_id", text),
        ("order_id", "order_id", text),
        ("review_score", "review_score", integer),
        ("review_comment_title", "review_comment_title", text),
        ("review_comment_message", "review_comment_message", text),
        ("review_creation_date", "review_creation_date", timestamp),
        ("review_answer_timestamp", "review_answer_timestamp", timestamp),
    ]),
]


def load_table(conn, table, filename, columns):
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {filename}")
    db_cols = [c[1] for c in columns]
    sql = (
        f"INSERT INTO {table} ({', '.join(db_cols)}) "
        f"VALUES ({', '.join('?' for _ in db_cols)})"
    )
    csv_rows = 0
    batch = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c[0] for c in columns if c[0] not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{filename}: missing columns {missing}")
        for row in reader:
            batch.append(tuple(conv(row[src]) for src, _, conv in columns))
            csv_rows += 1
            if len(batch) >= BATCH_SIZE:
                conn.executemany(sql, batch)
                batch.clear()
        if batch:
            conn.executemany(sql, batch)
    conn.commit()
    return csv_rows


def validate(conn, csv_counts):
    ok = True
    print("\nRow counts (CSV rows vs database rows):")
    for table, _, _ in TABLES:
        db_rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        status = "OK" if db_rows == csv_counts[table] else "MISMATCH"
        if status != "OK":
            ok = False
        print(f"  {table:32s} csv={csv_counts[table]:>8,}  db={db_rows:>8,}  {status}")

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"\nForeign key violations: {len(violations)}")
    if violations:
        ok = False
        for v in violations[:10]:
            print("  ", tuple(v))

    print("\nSample checks (BRL):")
    revenue, items = conn.execute(
        "SELECT ROUND(SUM(price), 2), COUNT(*) FROM order_items"
    ).fetchone()
    print(f"  total order-item price (all statuses): {revenue:,.2f} across {items:,} items")
    print("  orders by status:")
    for status, n in conn.execute(
        "SELECT order_status, COUNT(*) FROM orders GROUP BY order_status ORDER BY 2 DESC"
    ):
        print(f"    {status:12s} {n:>8,}")
    lo, hi = conn.execute(
        "SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp) FROM orders"
    ).fetchone()
    print(f"  purchase timestamps: {lo} to {hi}")
    return ok


def main():
    if FINAL_DB.name == "sales.db":
        sys.exit("Refusing to touch sales.db")
    if TEMP_DB.exists():
        TEMP_DB.unlink()

    conn = sqlite3.connect(TEMP_DB)
    try:
        conn.executescript(SCHEMA)
        csv_counts = {}
        for table, filename, columns in TABLES:
            csv_counts[table] = load_table(conn, table, filename, columns)
            print(f"Imported {table}: {csv_counts[table]:,} rows")
        ok = validate(conn, csv_counts)
    except Exception:
        conn.close()
        TEMP_DB.unlink(missing_ok=True)
        raise
    conn.close()

    if not ok:
        TEMP_DB.unlink(missing_ok=True)
        sys.exit("\nValidation failed; olist.db was NOT replaced.")

    os.replace(TEMP_DB, FINAL_DB)
    print(f"\nDone. Created {FINAL_DB}")


if __name__ == "__main__":
    main()
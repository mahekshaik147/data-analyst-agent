from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from random import Random

from backend.config import (
    DATASET_DESCRIPTION,
    DATASET_ID,
    DATASET_NAME,
    DATASETS,
    SAMPLE_ROW_LIMIT,
)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit_price REAL NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""

CUSTOMERS = [
    ("Ava Patel", "ava.patel@example.com", "Austin", "South"),
    ("Liam Chen", "liam.chen@example.com", "Seattle", "West"),
    ("Noah Williams", "noah.williams@example.com", "Denver", "West"),
    ("Olivia Garcia", "olivia.garcia@example.com", "Miami", "South"),
    ("Emma Johnson", "emma.johnson@example.com", "Chicago", "Midwest"),
    ("Mason Brown", "mason.brown@example.com", "Boston", "Northeast"),
    ("Sophia Martinez", "sophia.martinez@example.com", "Dallas", "South"),
    ("Isabella Nguyen", "isabella.nguyen@example.com", "San Jose", "West"),
    ("Ethan Wright", "ethan.wright@example.com", "Atlanta", "South"),
    ("Mia Thompson", "mia.thompson@example.com", "Portland", "West"),
    ("Lucas Anderson", "lucas.anderson@example.com", "Minneapolis", "Midwest"),
    ("Amelia Scott", "amelia.scott@example.com", "Philadelphia", "Northeast"),
    ("Harper Lewis", "harper.lewis@example.com", "Phoenix", "West"),
    ("Elijah Walker", "elijah.walker@example.com", "Nashville", "South"),
    ("Charlotte Hall", "charlotte.hall@example.com", "New York", "Northeast"),
    ("Henry Young", "henry.young@example.com", "Columbus", "Midwest"),
    ("Evelyn King", "evelyn.king@example.com", "Raleigh", "South"),
    ("Alexander Allen", "alexander.allen@example.com", "San Diego", "West"),
    ("Abigail Rivera", "abigail.rivera@example.com", "Tampa", "South"),
    ("James Baker", "james.baker@example.com", "Detroit", "Midwest"),
    ("Ella Adams", "ella.adams@example.com", "Baltimore", "Northeast"),
    ("Benjamin Nelson", "benjamin.nelson@example.com", "Salt Lake City", "West"),
    ("Scarlett Hill", "scarlett.hill@example.com", "Kansas City", "Midwest"),
    ("Sebastian Green", "sebastian.green@example.com", "Orlando", "South"),
    ("Grace Carter", "grace.carter@example.com", "Providence", "Northeast"),
    ("Jack Mitchell", "jack.mitchell@example.com", "Boise", "West"),
    ("Chloe Perez", "chloe.perez@example.com", "San Antonio", "South"),
    ("Daniel Roberts", "daniel.roberts@example.com", "Cleveland", "Midwest"),
    ("Lily Turner", "lily.turner@example.com", "Richmond", "South"),
    ("Matthew Phillips", "matthew.phillips@example.com", "Buffalo", "Northeast"),
    ("Zoey Campbell", "zoey.campbell@example.com", "Sacramento", "West"),
    ("Wyatt Parker", "wyatt.parker@example.com", "Omaha", "Midwest"),
]

PRODUCTS = [
    ("Aurora Headphones", "Electronics", 129.99, 48),
    ("Nimbus Laptop Stand", "Electronics", 59.50, 72),
    ("Pulse Wireless Mouse", "Electronics", 34.00, 110),
    ("Canvas Desk Lamp", "Home", 42.75, 64),
    ("Harbor Throw Blanket", "Home", 38.00, 41),
    ("Cedar Cutting Board", "Home", 27.50, 18),
    ("Trail Runner Shoes", "Sports", 96.00, 33),
    ("Summit Water Bottle", "Sports", 22.00, 140),
    ("Flex Yoga Mat", "Sports", 31.25, 55),
    ("Northwind Parka", "Apparel", 168.00, 12),
    ("Riverstone Jeans", "Apparel", 74.00, 27),
    ("Daylight Linen Shirt", "Apparel", 48.50, 39),
    ("Grove Coffee Beans", "Grocery", 16.75, 210),
    ("Citrus Sparkling Water", "Grocery", 8.50, 260),
    ("Harvest Granola", "Grocery", 9.25, 175),
    ("Atlas Backpack", "Sports", 84.00, 21),
    ("Lumen Monitor Light", "Electronics", 45.00, 16),
    ("Quilted Studio Chair", "Home", 219.00, 8),
    ("Coastal Linen Duvet", "Home", 132.00, 14),
    ("Metro Cap", "Apparel", 19.00, 90),
]


def connect_writable(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def get_dataset(dataset_id: str | None) -> dict | None:
    """Return the registry entry for a dataset, or None if unknown or its file is missing."""
    if dataset_id in (None, ""):
        dataset_id = DATASET_ID
    config = DATASETS.get(dataset_id)
    if config is None or not config["path"].exists():
        return None
    return config

def init_database(path: Path) -> None:
    connection = connect_writable(path)
    try:
        connection.executescript(SCHEMA_SQL)
        existing = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if existing == 0:
            _seed(connection)
        connection.commit()
    finally:
        connection.close()


def _seed(connection: sqlite3.Connection) -> None:
    rng = Random(42)
    start = date(2024, 10, 1)
    connection.executemany(
        "INSERT INTO customers (name, email, city, region, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (
                name,
                email,
                city,
                region,
                (start - timedelta(days=30 * (index + 1))).isoformat(),
            )
            for index, (name, email, city, region) in enumerate(CUSTOMERS)
        ],
    )
    connection.executemany(
        "INSERT INTO products (name, category, unit_price, stock) VALUES (?, ?, ?, ?)",
        PRODUCTS,
    )
    customer_ids = [row[0] for row in connection.execute("SELECT id FROM customers")]
    products = list(connection.execute("SELECT id, unit_price FROM products"))
    order_rows: list[tuple[int, str, str]] = []
    item_rows: list[tuple[int, int, int, float]] = []
    for order_id in range(1, 181):
        customer_id = rng.choice(customer_ids)
        order_date = (start + timedelta(days=rng.randint(0, 364))).isoformat()
        status = rng.choices(["completed", "shipped", "cancelled"], weights=[80, 12, 8])[0]
        order_rows.append((customer_id, order_date, status))
        for _ in range(rng.randint(1, 4)):
            product_id, unit_price = rng.choice(products)
            quantity = rng.randint(1, 5)
            item_rows.append((order_id, product_id, quantity, float(unit_price)))
    connection.executemany(
        "INSERT INTO orders (customer_id, order_date, status) VALUES (?, ?, ?)",
        order_rows,
    )
    connection.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
        item_rows,
    )

def dataset_catalog() -> list[dict[str, str]]:
    catalog = [
        {
            "id": DATASET_ID,
            "name": DATASET_NAME,
            "description": DATASET_DESCRIPTION,
            "currency": DATASETS[DATASET_ID]["currency"],
        }
    ]
    for dataset_id, config in DATASETS.items():
        if dataset_id != DATASET_ID and config["path"].exists():
            catalog.append(
                {
                    "id": dataset_id,
                    "name": config["name"],
                    "description": config["description"],
                    "currency": config["currency"],
                }
            )
    return catalog


def known_dataset(dataset: str | None) -> bool:
    return dataset in (None, "", DATASET_ID)


def inspect_schema(path: Path, dataset_id: str | None = None) -> dict:
    if dataset_id in (None, DATASET_ID):
        connection = connect_writable(path)
    else:
        connection = connect_readonly(path)
    try:
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables = []
        relationships = []
        for table_name in table_names:
            columns_info = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
            fk_by_column = {
                row["from"]: f"{row['table']}.{row['to']}" for row in foreign_keys
            }
            for row in foreign_keys:
                relationships.append(
                    {
                        "from": table_name,
                        "to": row["table"],
                        "columns": f"{row['from']} → {row['to']}",
                    }
                )
            sample_rows = [
                _serialize_row(dict(row))
                for row in connection.execute(f"SELECT * FROM {table_name} LIMIT ?", (SAMPLE_ROW_LIMIT,))
            ]
            row_count = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            tables.append(
                {
                    "name": table_name,
                    "columns": [
                        {
                            "name": column["name"],
                            "type": column["type"] or "TEXT",
                            "primary_key": bool(column["pk"]),
                            "foreign_key": fk_by_column.get(column["name"]),
                        }
                        for column in columns_info
                    ],
                    "row_count": row_count,
                    "sample_rows": sample_rows,
                }
            )
        return {
                        "dataset": dataset_id or DATASET_ID,
            "tables": tables,
            "relationships": relationships,
        }
    finally:
        connection.close()


def health_snapshot(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"status": "ok", "database": "missing", "dataset": DATASET_ID}
    connection = connect_writable(path)
    try:
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        return {
            "status": "ok",
            "database": "connected",
            "dataset": DATASET_ID,
            "tables": table_count,
        }
    finally:
        connection.close()


def _serialize_row(row: dict) -> dict:
    return {key: value for key, value in row.items()}

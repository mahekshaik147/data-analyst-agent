import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_DATABASE_PATH = DATA_DIR / "sales.db"

DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))
DATASET_ID = os.environ.get("DATASET_ID", "sales")
DATASET_NAME = os.environ.get("DATASET_NAME", "Retail sales")
DATASET_DESCRIPTION = os.environ.get(
    "DATASET_DESCRIPTION",
    "Synthetic retail sales data with customers, products, orders, and order items.",
)

MAX_RESULT_ROWS = int(os.environ.get("MAX_RESULT_ROWS", "100"))
ABSOLUTE_MAX_ROWS = int(os.environ.get("ABSOLUTE_MAX_ROWS", "1000"))
QUERY_TIMEOUT_SECONDS = float(os.environ.get("QUERY_TIMEOUT_SECONDS", "5"))
SAMPLE_ROW_LIMIT = int(os.environ.get("SAMPLE_ROW_LIMIT", "5"))

CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if origin.strip()
]


def clamp_max_rows(requested: int | None) -> int:
    value = MAX_RESULT_ROWS if requested is None else int(requested)
    return max(1, min(ABSOLUTE_MAX_ROWS, value))

    
OLIST_DATABASE_PATH = Path(
    os.environ.get("OLIST_DATABASE_PATH", str(DATA_DIR / "olist.db"))
)

# Registry of selectable datasets, keyed by dataset ID.
DATASETS = {
    DATASET_ID: {
        "id": DATASET_ID,
        "name": DATASET_NAME,
        "description": DATASET_DESCRIPTION,
        "path": DATABASE_PATH,
        "currency": "USD",
    },
    "olist": {
        "id": "olist",
        "name": "Olist Brazilian e-commerce",
        "description": (
            "Public Brazilian e-commerce data (2016-2018): orders, items, payments, "
            "reviews, products, sellers. Amounts are in Brazilian reais (BRL)."
        ),
        "path": OLIST_DATABASE_PATH,
        "currency": "BRL",
    },
}

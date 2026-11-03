import json
import os
import re
from pathlib import Path, PureWindowsPath

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
UPLOAD_REGISTRY_PATH = UPLOADS_DIR / "registry.json"
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
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))

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


def sanitize_dataset_id(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "dataset").lower()).strip("-")
    return cleaned or "dataset"


OLIST_DATABASE_PATH = Path(
    os.environ.get("OLIST_DATABASE_PATH", str(DATA_DIR / "olist.db"))
)


def _data_dir_root() -> Path:
    return DATA_DIR.resolve(strict=False)


def _is_within_data_dir(path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(_data_dir_root())
        return True
    except ValueError:
        return False


def _normalize_registry_path(raw_path: str | Path | None) -> Path | None:
    if raw_path is None:
        return None

    raw_value = str(raw_path).strip()
    if not raw_value:
        return None

    candidate: Path
    windows_path = PureWindowsPath(raw_value)
    if windows_path.drive or raw_value.startswith("\\\\") or raw_value.startswith("/") and "\\" in raw_value:
        if os.name == "nt":
            candidate = Path(raw_value)
        else:
            candidate = Path(raw_value.replace("\\", "/"))
    else:
        candidate = Path(raw_value)

    if not candidate.is_absolute():
        candidate = (DATA_DIR / candidate).resolve(strict=False)
    else:
        candidate = candidate.resolve(strict=False)

    if not _is_within_data_dir(candidate):
        return None
    return candidate


def _serialize_registry_path(raw_path: str | Path | None) -> str:
    candidate = _normalize_registry_path(raw_path)
    if candidate is None:
        return ""
    try:
        return candidate.relative_to(_data_dir_root()).as_posix()
    except ValueError:
        return candidate.as_posix()


def _write_registry_manifest(manifest: dict[str, dict]) -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    serializable_manifest = {
        entry_id: {
            **config,
            "path": _serialize_registry_path(config.get("path", "")),
        }
        for entry_id, config in manifest.items()
        if isinstance(config, dict)
    }
    temp_path = UPLOAD_REGISTRY_PATH.with_name(f"{UPLOAD_REGISTRY_PATH.name}.tmp")
    temp_path.write_text(json.dumps(serializable_manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, UPLOAD_REGISTRY_PATH)


def _build_default_datasets() -> dict[str, dict]:
    return {
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


def _load_uploaded_dataset_registry() -> dict[str, dict]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if not UPLOAD_REGISTRY_PATH.exists():
        return {}
    try:
        payload = json.loads(UPLOAD_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}

    datasets: dict[str, dict] = {}
    migrated = False
    for dataset_id, config in payload.items():
        if not isinstance(config, dict):
            continue
        raw_path = config.get("path", "")
        path = _normalize_registry_path(raw_path)
        if path is None or not path.exists():
            continue
        normalized_path = _serialize_registry_path(path)
        if raw_path and str(raw_path).strip() != normalized_path:
            config["path"] = normalized_path
            migrated = True
        datasets[str(dataset_id)] = {
            "id": str(dataset_id),
            "name": str(config.get("name", dataset_id)),
            "description": str(config.get("description", "Uploaded dataset.")),
            "path": path,
            "currency": str(config.get("currency", "USD")),
        }

    if migrated:
        _write_registry_manifest(payload)
    return datasets


def refresh_uploaded_datasets() -> dict[str, dict]:
    DATASETS.clear()
    DATASETS.update(_build_default_datasets())
    DATASETS.update(_load_uploaded_dataset_registry())
    return DATASETS


def register_uploaded_dataset(dataset_id: str, name: str, path: Path, description: str = "Uploaded dataset") -> dict:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_uploaded_dataset_registry()

    resolved_path = _normalize_registry_path(path)
    if resolved_path is None or not _is_within_data_dir(resolved_path):
        raise ValueError("Uploaded dataset path is outside the configured data directory.")

    existing_names = {
        str(config.get("name", ""))
        for config in manifest.values()
        if isinstance(config, dict) and config.get("name")
    }
    display_name = name
    counter = 2
    while display_name in existing_names:
        display_name = f"{name} ({counter})"
        counter += 1

    manifest[dataset_id] = {
        "id": dataset_id,
        "name": display_name,
        "description": description,
        "path": resolved_path,
        "currency": "USD",
    }
    _write_registry_manifest(manifest)
    return refresh_uploaded_datasets()[dataset_id]


def delete_uploaded_dataset(dataset_id: str) -> dict:
    dataset_key = str(dataset_id or "").strip()
    if not dataset_key:
        raise KeyError("Dataset ID is required.")
    if dataset_key in {"sales", "olist"}:
        raise ValueError("Built-in datasets cannot be deleted.")

    manifest = _load_uploaded_dataset_registry()
    entry = manifest.get(dataset_key)
    if entry is None:
        fallback = DATASETS.get(dataset_key)
        if isinstance(fallback, dict) and dataset_key not in {"sales", "olist"}:
            fallback_path = fallback.get("path")
            fallback_candidate = _normalize_registry_path(fallback_path)
            if fallback_candidate is None or not _is_within_data_dir(fallback_candidate):
                raise ValueError("Uploaded dataset path is outside the configured data directory and cannot be deleted.")
            raise KeyError(f"Unknown dataset '{dataset_key}'.")
        raise KeyError(f"Unknown dataset '{dataset_key}'.")
    if not isinstance(entry, dict):
        raise ValueError(f"Dataset '{dataset_key}' is invalid.")

    raw_path = entry.get("path")
    candidate = _normalize_registry_path(raw_path)
    if candidate is None or not _is_within_data_dir(candidate):
        raise ValueError("Uploaded dataset path is outside the configured data directory and cannot be deleted.")
    if candidate == UPLOAD_REGISTRY_PATH or candidate == UPLOADS_DIR or candidate == _data_dir_root():
        raise ValueError("The selected path is not a dataset database file.")
    if candidate.parent.resolve(strict=False) != UPLOADS_DIR.resolve(strict=False):
        raise ValueError("Uploaded dataset databases must remain inside the uploads directory.")
    if candidate.suffix.lower() != ".db":
        raise ValueError("Only uploaded SQLite database files can be deleted.")
    if not candidate.exists():
        raise FileNotFoundError(f"Dataset '{dataset_key}' database file is missing.")
    if not candidate.is_file():
        raise ValueError("The selected dataset path is not a file.")

    try:
        candidate.unlink()
    except OSError as exc:
        raise OSError(f"Could not delete dataset '{dataset_key}'.") from exc

    del manifest[dataset_key]
    _write_registry_manifest(manifest)
    return {
        "id": dataset_key,
        "name": str(entry.get("name", dataset_key)),
        "path": candidate,
    }


DATASETS = _build_default_datasets()
DATASETS.update(_load_uploaded_dataset_registry())

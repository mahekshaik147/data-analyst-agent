from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from backend.sql_safety import UnsafeSqlError, validate_select


class QueryExecutionError(RuntimeError):
    """Raised when a validated query cannot be executed."""


def execute_readonly(
    path: Path,
    sql: str,
    max_rows: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    validated = validate_select(sql, max_rows=max_rows)
    connection = _open_readonly(path)
    try:
        _install_timeout(connection, timeout_seconds)
        cursor = connection.execute(validated.sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description or []]
        serialized = [_serialize_row(columns, row) for row in rows]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "columns": columns,
            "rows": serialized,
            "row_count": len(serialized),
            "execution_time_ms": elapsed_ms,
            "status": "ok",
            "sql": validated.sql,
        }
    except UnsafeSqlError:
        raise
    except sqlite3.OperationalError as exc:
        message = str(exc)
        if "interrupted" in message.lower():
            raise QueryExecutionError("Query exceeded the configured timeout.") from exc
        raise QueryExecutionError(f"Query failed: {message}") from exc
    except sqlite3.Error as exc:
        raise QueryExecutionError(f"Query failed: {exc}") from exc
    finally:
        connection.close()


def _open_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise QueryExecutionError("The dataset database is not available.")
    uri = path.resolve().as_posix()
    connection = sqlite3.connect(f"file:{uri}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _install_timeout(connection: sqlite3.Connection, timeout_seconds: float) -> None:
    deadline = time.perf_counter() + max(0.05, timeout_seconds)

    def progress_handler() -> int:
        return 1 if time.perf_counter() > deadline else 0

    connection.set_progress_handler(progress_handler, 1000)


def _serialize_row(columns: list[str], row: sqlite3.Row) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for column in columns:
        value = row[column]
        if isinstance(value, bytes):
            payload[column] = value.decode("utf-8", errors="replace")
        else:
            payload[column] = value
    return payload

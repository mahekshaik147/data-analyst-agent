from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

ALLOWED_ROOTS = (exp.Select, exp.Union)
FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Merge,
    exp.Copy,
    exp.TruncateTable,
    exp.Grant,
    exp.Set,
    exp.Use,
    exp.Analyze,
    exp.Refresh,
)
FORBIDDEN_FUNCTIONS = {
    "load_extension",
    "readfile",
    "writefile",
    "eval",
    "zipfile",
}
FORBIDDEN_TABLES = {
    "sqlite_dbpage",
    "sqlite_dbaux",
    "sqlite_temp_master",
    "sqlite_stat4",
    "dbstat",
}


class UnsafeSqlError(ValueError):
    """Raised when a SQL statement is rejected by the safety validator."""


@dataclass(frozen=True)
class ValidatedSql:
    original: str
    sql: str
    ast: exp.Expression


def validate_select(sql: str, max_rows: int) -> ValidatedSql:
    if sql is None or not str(sql).strip():
        raise UnsafeSqlError("SQL is required.")
    text = str(sql).strip()
    if "\x00" in text:
        raise UnsafeSqlError("SQL contains invalid characters.")

    try:
        statements = sqlglot.parse(text, read="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise UnsafeSqlError(f"SQL could not be parsed: {exc}") from exc

    statements = [statement for statement in statements if statement is not None]
    if not statements:
        raise UnsafeSqlError("SQL did not contain a statement.")
    if len(statements) != 1:
        raise UnsafeSqlError("Only a single SQL statement is allowed.")

    ast = statements[0]
    if not isinstance(ast, ALLOWED_ROOTS):
        raise UnsafeSqlError("Only read-only SELECT statements are allowed.")

    _reject_forbidden_nodes(ast)
    _reject_forbidden_functions(ast)
    _reject_forbidden_tables(ast)

    limited = _apply_row_limit(ast, max_rows)
    rendered = limited.sql(dialect="sqlite")
    return ValidatedSql(original=text, sql=rendered, ast=limited)


def _reject_forbidden_nodes(ast: exp.Expression) -> None:
    for node in ast.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise UnsafeSqlError(f"Statement type '{node.key}' is not allowed.")


def _reject_forbidden_functions(ast: exp.Expression) -> None:
    for node in ast.find_all(exp.Func, exp.Anonymous):
        name = _function_name(node)
        if name in FORBIDDEN_FUNCTIONS:
            raise UnsafeSqlError(f"Function '{name}' is not allowed.")


def _function_name(node: exp.Expression) -> str:
    raw = getattr(node, "name", None) or getattr(node, "this", None)
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raw = getattr(raw, "name", None) or str(raw)
    return str(raw).lower()


def _reject_forbidden_tables(ast: exp.Expression) -> None:
    for table in ast.find_all(exp.Table):
        name = (table.name or "").lower()
        catalog = (table.catalog or "").lower()
        db = (table.db or "").lower()
        if name.startswith("pragma_"):
            raise UnsafeSqlError("PRAGMA table functions are not allowed.")
        if name in FORBIDDEN_TABLES:
            raise UnsafeSqlError(f"Table '{name}' is not allowed.")
        if catalog not in {"", "main"} or db not in {"", "main"}:
            raise UnsafeSqlError("Queries may only read the primary database.")


def _apply_row_limit(ast: exp.Expression, max_rows: int) -> exp.Expression:
    if isinstance(ast, exp.Union):
        return exp.select("*").from_(ast.subquery(alias="limited_query")).limit(max_rows)

    current = _existing_limit(ast)
    if current is None:
        return ast.limit(max_rows)
    return ast.limit(min(current, max_rows))


def _existing_limit(ast: exp.Expression) -> int | None:
    limit = ast.args.get("limit")
    if limit is None:
        return None
    expression = None
    if isinstance(limit, exp.Limit):
        expression = limit.args.get("expression") or limit.expression or limit.this
    else:
        expression = limit
    try:
        if isinstance(expression, exp.Literal):
            return int(expression.this)
        return int(str(expression))
    except (TypeError, ValueError):
        return None

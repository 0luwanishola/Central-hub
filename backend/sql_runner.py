"""Sandboxed SQLite execution for learning challenges.

Two modes:
  - ``readonly``: SELECT / WITH / EXPLAIN / VALUES only (the classic learner sandbox).
  - ``scratch``: the same, plus DDL/DML and transaction control on the disposable
    in-memory database, for schema design and transaction lessons.

Always blocked for learners: ATTACH/DETACH (no filesystem access), PRAGMA, extension
loading, and a small denylist of legacy footgun functions.
"""

import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional

READONLY = "readonly"
SCRATCH = "scratch"

_BLOCKED_FUNCTIONS = {"load_extension", "fts3_tokenizer", "readfile", "writefile", "edit", "eval"}

_READ_STARTS = ("SELECT", "WITH", "EXPLAIN", "VALUES")
_SCRATCH_STARTS = _READ_STARTS + (
    "CREATE",
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "REPLACE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "RELEASE",
    "ANALYZE",
    "REINDEX",
)

_MAX_SOURCE = 5_000


class SqlRunError(Exception):
    """A safe, learner-facing error from the SQL sandbox."""

    def __init__(self, message: str, line: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.line = line


@dataclass
class StatementResult:
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)


@dataclass
class SqlOutcome:
    statements: list[StatementResult]

    @property
    def result(self) -> Optional[StatementResult]:
        """The statement the UI should present: the last one that returned columns."""
        for statement in reversed(self.statements):
            if statement.columns:
                return statement
        return self.statements[-1] if self.statements else None

    def executed(self) -> list[dict]:
        return [
            {"sql": statement.sql, "columns": statement.columns, "row_count": len(statement.rows)}
            for statement in self.statements
        ]


def _strip_leading_comments(statement: str) -> str:
    while True:
        if statement.startswith("--"):
            newline = statement.find("\n")
            statement = "" if newline < 0 else statement[newline + 1:].lstrip()
        elif statement.startswith("/*"):
            end = statement.find("*/", 2)
            if end < 0:
                return statement
            statement = statement[end + 2:].lstrip()
        else:
            return statement


def _starts_allowed(statement: str, mode: str) -> bool:
    head = _strip_leading_comments(statement).lstrip()
    match = re.match(r"(?i)([A-Za-z]+)", head)
    if not match:
        return False
    keyword = match.group(1).upper()
    if mode == SCRATCH:
        return keyword in _SCRATCH_STARTS
    return keyword in _READ_STARTS


def split_statements(source: str) -> list[str]:
    """Split a script into statements using SQLite's own completeness checker."""
    statements: list[str] = []
    buffer = ""
    for char in source:
        buffer += char
        if char == ";" and sqlite3.complete_statement(buffer):
            candidate = buffer.strip()
            if candidate.strip(";").strip():
                statements.append(candidate)
            buffer = ""
    remainder = buffer.strip()
    if remainder and remainder.strip(";").strip():
        statements.append(remainder)
    return statements


def _authorizer(mode: str):
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ}
    if hasattr(sqlite3, "SQLITE_RECURSIVE"):
        allowed.add(sqlite3.SQLITE_RECURSIVE)
    if mode == SCRATCH:
        for name in (
            "SQLITE_INSERT",
            "SQLITE_UPDATE",
            "SQLITE_DELETE",
            "SQLITE_CREATE_TABLE",
            "SQLITE_DROP_TABLE",
            "SQLITE_CREATE_INDEX",
            "SQLITE_DROP_INDEX",
            "SQLITE_CREATE_VIEW",
            "SQLITE_DROP_VIEW",
            "SQLITE_ALTER_TABLE",
            "SQLITE_SAVEPOINT",
            "SQLITE_TRANSACTION",
            "SQLITE_REINDEX",
            "SQLITE_ANALYZE",
            "SQLITE_CREATE_TEMP_TABLE",
            "SQLITE_DROP_TEMP_TABLE",
            "SQLITE_CREATE_TEMP_INDEX",
            "SQLITE_DROP_TEMP_INDEX",
            "SQLITE_CREATE_TEMP_VIEW",
            "SQLITE_DROP_TEMP_VIEW",
        ):
            action = getattr(sqlite3, name, None)
            if action is not None:
                allowed.add(action)

    def authorize(action, first, second, database, trigger):
        if action in allowed:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            name = str(second or first or "").lower()
            if name not in _BLOCKED_FUNCTIONS:
                return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return authorize


def _translate_error(exc: sqlite3.Error) -> str:
    message = str(exc)
    lowered = message.lower()
    if "not authorized" in lowered:
        return "That statement or function is not allowed in this workspace."
    if "interrupted" in lowered:
        return "That query is doing too much work. Try a simpler query."
    if "syntax error" in lowered:
        return f"SQL needs a fix: {message}"
    return f"SQL needs a fix: {message}"


def execute(
    connection: sqlite3.Connection,
    source: str,
    *,
    mode: str = READONLY,
    row_cap: int = 100,
    step_cap: int = 20_000,
    time_cap_ms: int = 1_500,
) -> SqlOutcome:
    """Run learner SQL against a seeded connection. Raises SqlRunError on failure."""
    if not source.strip():
        raise SqlRunError("Write a SQL query first.")
    if len(source) > _MAX_SOURCE:
        raise SqlRunError(f"Keep SQL under {_MAX_SOURCE:,} characters.")

    statements = split_statements(source)
    if not statements:
        raise SqlRunError("Write a SQL query first.")
    if mode != SCRATCH and len(statements) > 1:
        raise SqlRunError("This workspace runs one statement at a time.")

    for statement in statements:
        if not _starts_allowed(statement, mode):
            if mode == SCRATCH:
                raise SqlRunError("This lesson accepts SELECT queries plus schema changes (CREATE, INSERT, UPDATE, DELETE).")
            raise SqlRunError("This SQL workspace accepts read-only SELECT queries.")

    if hasattr(connection, "enable_load_extension"):
        connection.enable_load_extension(False)
    if hasattr(connection, "setlimit"):
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100_000_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 64)
    connection.set_authorizer(_authorizer(mode))

    ops = 0
    started = time.monotonic()

    def guard() -> int:
        nonlocal ops
        ops += 5_000
        if ops > step_cap:
            return 1
        if (time.monotonic() - started) * 1000 > time_cap_ms:
            return 1
        return 0

    connection.set_progress_handler(guard, 5_000)
    results: list[StatementResult] = []
    try:
        for statement in statements:
            cursor = connection.execute(statement)
            columns = [item[0] for item in (cursor.description or [])]
            rows = [list(row) for row in cursor.fetchmany(row_cap + 1)] if columns else []
            if len(rows) > row_cap:
                raise SqlRunError(f"This lesson limits query results to {row_cap:,} rows.")
            results.append(StatementResult(statement, columns, rows))
    except sqlite3.Error as exc:
        raise SqlRunError(_translate_error(exc)) from None
    finally:
        connection.set_progress_handler(None, 0)
    return SqlOutcome(results)


def run_check_queries(connection: sqlite3.Connection, queries: list[dict]) -> list[dict]:
    """Evaluate scratch-mode state predicates against the learner's database.

    Each query entry: {"query": "SELECT ...", "expect": value} or {"query": "...", "expect_rows": [...]}.
    Constraint probes: {"rejected_insert": "INSERT ..."} passes when the write fails.
    """
    outcome = []
    for entry in queries:
        if "rejected_insert" in entry:
            try:
                connection.execute(entry["rejected_insert"])
            except sqlite3.Error:
                outcome.append({"entry": entry, "passed": True, "got": None})
            else:
                outcome.append({"entry": entry, "passed": False, "got": "the write was accepted"})
            continue
        try:
            value = connection.execute(entry["query"]).fetchone()[0]
        except sqlite3.Error as exc:
            outcome.append({"entry": entry, "passed": False, "got": f"query failed: {exc}"})
            continue
        expected = entry.get("expect", entry.get("expect_rows"))
        outcome.append({"entry": entry, "passed": value == expected, "got": value})
    return outcome

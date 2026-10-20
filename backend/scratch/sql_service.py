"""SQL Scratch execution over a persistent, disposable SQLite workspace."""

import json
import math
import re
import sqlite3
import time
from typing import Optional

try:
    from .. import sql_runner
except ImportError:  # pragma: no cover - top-level backend imports
    import sql_runner

from . import limits, sql_workspaces
from .errors import ScratchError


class _Guard:
    """Progress-handler guard for both wall-clock and step caps."""

    def __init__(self) -> None:
        self.ops = 0
        self.started = time.monotonic()
        self.timed_out = False
        self.step_limited = False

    def __call__(self) -> int:
        self.ops += 5_000
        if self.ops > limits.SQL_STEP_CAP:
            self.step_limited = True
            return 1
        if (time.monotonic() - self.started) * 1000 > limits.SQL_TIME_CAP_MS:
            self.timed_out = True
            return 1
        return 0


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


def _statement_kind(statement: str) -> str:
    head = _strip_leading_comments(statement).lstrip()
    words = re.findall(r"(?i)[A-Za-z]+", head)
    if not words:
        return "STATEMENT"
    first = words[0].upper()
    if first in {"CREATE", "DROP", "ALTER"} and len(words) > 1:
        return f"{first} {words[1].upper()}"
    return first


def _safe_text(value, limit: int = limits.SQL_MAX_CELL_CHARS) -> tuple[str, bool]:
    text = str(value)
    if len(text) > limit:
        return text[:limit], True
    return text, False


def _safe_value(value) -> tuple[object, bool]:
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value, False
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value), False
        return value, False
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        size = len(value)
        return f"<binary {size} bytes>", False
    return _safe_text(value)


def _json_size(value) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    )


def _apply_connection_guards(connection: sqlite3.Connection) -> None:
    if hasattr(connection, "enable_load_extension"):
        connection.enable_load_extension(False)
    if hasattr(connection, "setlimit"):
        for name, value in (
            ("SQLITE_LIMIT_LENGTH", max(1_000_000, limits.SQL_MAX_RESPONSE_BYTES)),
            ("SQLITE_LIMIT_COLUMN", limits.SQL_MAX_COLUMNS),
            ("SQLITE_LIMIT_ATTACHED", 0),
            ("SQLITE_LIMIT_SQL_LENGTH", 100_000),
        ):
            action = getattr(sqlite3, name, None)
            if action is not None:
                try:
                    connection.setlimit(action, value)
                except (sqlite3.Error, AttributeError):
                    pass
    if hasattr(connection, "setconfig"):
        for name, value in (
            ("SQLITE_DBCONFIG_DEFENSIVE", 1),
            ("SQLITE_DBCONFIG_TRUSTED_SCHEMA", 0),
            ("SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION", 0),
        ):
            action = getattr(sqlite3, name, None)
            if action is not None:
                try:
                    connection.setconfig(action, value)
                except (sqlite3.Error, AttributeError, ValueError):
                    pass


def _workspace_limit_label() -> str:
    max_bytes = limits.SQL_WORKSPACE_MAX_BYTES
    if max_bytes >= 1024 * 1024 and max_bytes % (1024 * 1024) == 0:
        return f"{max_bytes // (1024 * 1024)} MB"
    if max_bytes >= 1024 and max_bytes % 1024 == 0:
        return f"{max_bytes // 1024} KB"
    return f"{max_bytes} bytes"


def _translate_error(exc: sqlite3.Error, guard: _Guard) -> tuple[str, str]:
    message = str(exc)
    lowered = message.lower()
    if guard.timed_out:
        return (
            f"This script was stopped after {limits.SQL_TIME_CAP_MS / 1000:g} seconds. "
            "Try a smaller query or add a narrower filter.",
            "timeout",
        )
    if guard.step_limited:
        return (
            "This script did too much work. Try a smaller query, narrower filter, or fewer rows.",
            "step_limit",
        )
    if "database or disk is full" in lowered or "database full" in lowered:
        return (
            f"This workspace reached its {_workspace_limit_label()} limit. "
            "Delete large rows or reset the workspace.",
            "quota",
        )
    if "not authorized" in lowered:
        return (
            "That statement or function is not available in this workspace. "
            "Scratch allows SELECT plus ordinary table and data changes.",
            "policy",
        )
    if "database is locked" in lowered:
        return ("The workspace is busy. Wait for the current run to finish and try again.", "busy")
    if "no such table" in lowered or "syntax error" in lowered or "no such column" in lowered:
        return (f"SQL needs a fix: {message}", "sql")
    if "constraint failed" in lowered or "constraint" in lowered:
        return (f"SQL needs a fix: {message}", "sql")
    if "unable to open database file" in lowered or "disk i/o error" in lowered:
        return ("The workspace file is unavailable. Create a new workspace.", "workspace")
    return (f"SQL needs a fix: {message}", "sql")


def _empty_run_response(
    workspace_id: str,
    workspace: dict,
    started: float,
    statements: list[dict],
    *,
    status: str,
    error: Optional[str],
    error_statement: Optional[int],
    error_kind: Optional[str],
    truncated: bool,
) -> dict:
    rows = sum(len(statement.get("rows", [])) for statement in statements)
    affected = sum(int(statement.get("affected_rows") or 0) for statement in statements)
    return {
        "workspace_id": workspace_id,
        "status": status,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "statements": statements,
        "summary": {
            "statements": len(statements),
            "rows": rows,
            "affected_rows": affected,
            "truncated": truncated,
        },
        "error": error,
        "error_statement": error_statement,
        "error_kind": error_kind,
        "truncated": truncated,
        "workspace": workspace,
    }


def run_script(learner_id: str, workspace_id: str, source: str) -> dict:
    try:
        statements = sql_runner.validate_workspace_script(
            source,
            max_statements=limits.SQL_MAX_STATEMENTS,
            max_source=limits.SQL_MAX_SOURCE,
        )
    except sql_runner.SqlRunError as exc:
        raise ScratchError(422, exc.message) from None

    with sql_workspaces.workspace_session(learner_id, workspace_id) as workspace:
        started = time.perf_counter()
        db_path = sql_workspaces.workspace_db_path(workspace)
        try:
            if not db_path.is_file():
                raise ScratchError(
                    500,
                    "The SQL workspace file is unavailable. Create a new workspace.",
                )
            if db_path.stat().st_size > limits.SQL_WORKSPACE_MAX_BYTES:
                raise ScratchError(
                    409,
                    f"This workspace reached its {_workspace_limit_label()} limit. "
                    "Reset the workspace to start again.",
                )
        except OSError as exc:
            raise ScratchError(500, "The SQL workspace file is unavailable. Create a new workspace.") from exc

        try:
            connection = sqlite3.connect(str(db_path), timeout=5.0, isolation_level=None)
        except sqlite3.Error as exc:
            raise ScratchError(500, "The SQL workspace could not be opened. Create a new workspace.") from exc

        results: list[dict] = []
        response_truncated = False
        used_bytes = 4_096
        guard = _Guard()
        committed = False
        current_index: Optional[int] = None
        error_message: Optional[str] = None
        error_statement: Optional[int] = None
        error_kind: Optional[str] = None

        try:
            try:
                _apply_connection_guards(connection)
                connection.execute("PRAGMA foreign_keys = ON")
                row = connection.execute("PRAGMA page_size").fetchone()
                page_size = int(row[0]) if row and row[0] else 4096
                max_pages = max(1, limits.SQL_WORKSPACE_MAX_BYTES // page_size)
                connection.execute(f"PRAGMA max_page_count = {max_pages}")
            except (sqlite3.Error, ValueError, OverflowError) as exc:
                raise ScratchError(
                    500,
                    "The SQL workspace could not be prepared. Try again or create a new workspace.",
                ) from exc

            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.Error as exc:
                message, kind = _translate_error(exc, guard)
                raise ScratchError(409 if kind == "busy" else 500, message) from exc

            connection.set_progress_handler(guard, 5_000)
            connection.set_authorizer(sql_runner.workspace_authorizer())

            try:
                for index, statement in enumerate(statements):
                    current_index = index
                    before_changes = connection.total_changes
                    cursor = connection.execute(statement)
                    columns = [str(item[0])[:128] for item in (cursor.description or [])]
                    raw_rows = cursor.fetchmany(limits.SQL_MAX_ROWS + 1) if columns else []
                    statement_truncated = len(raw_rows) > limits.SQL_MAX_ROWS
                    if statement_truncated:
                        raw_rows = raw_rows[: limits.SQL_MAX_ROWS]
                        response_truncated = True
                    affected_rows = max(0, connection.total_changes - before_changes)

                    payload = {
                        "index": index,
                        "kind": _statement_kind(statement),
                        "columns": columns,
                        "rows": [],
                        "affected_rows": affected_rows,
                        "truncated": statement_truncated,
                    }
                    used_bytes += _json_size(payload)
                    if used_bytes > limits.SQL_MAX_RESPONSE_BYTES:
                        payload["truncated"] = True
                        response_truncated = True
                    else:
                        for row in raw_rows:
                            safe_row = []
                            row_truncated = False
                            for value in row:
                                safe, cell_truncated = _safe_value(value)
                                safe_row.append(safe)
                                row_truncated = row_truncated or cell_truncated
                            # Account for the comma that separates this row from the
                            # previous one in the serialized response.
                            row_size = _json_size(safe_row) + 1
                            if used_bytes + row_size > limits.SQL_MAX_RESPONSE_BYTES:
                                payload["truncated"] = True
                                response_truncated = True
                                break
                            used_bytes += row_size
                            payload["rows"].append(safe_row)
                            if row_truncated:
                                payload["truncated"] = True
                                response_truncated = True
                    results.append(payload)

                connection.set_authorizer(None)
                connection.commit()
                committed = True
                sql_workspaces.touch(workspace)
            except sqlite3.Error as exc:
                error_message, error_kind = _translate_error(exc, guard)
                error_statement = current_index
            finally:
                connection.set_progress_handler(None, 0)
                try:
                    connection.set_authorizer(None)
                except sqlite3.Error:
                    pass
                if not committed:
                    try:
                        connection.rollback()
                    except sqlite3.Error:
                        pass
        finally:
            connection.close()

        workspace_meta = sql_workspaces.workspace_metadata(workspace)
        if committed:
            return _empty_run_response(
                workspace_id,
                workspace_meta,
                started,
                results,
                status="completed",
                error=None,
                error_statement=None,
                error_kind=None,
                truncated=response_truncated,
            )
        status = "timeout" if guard.timed_out else "error"
        return _empty_run_response(
            workspace_id,
            workspace_meta,
            started,
            results,
            status=status,
            error=error_message or "SQL needs a fix: the script could not be completed.",
            error_statement=error_statement,
            error_kind=error_kind or ("timeout" if guard.timed_out else "sql"),
            truncated=response_truncated,
        )

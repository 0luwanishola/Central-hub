"""Server-owned limits for both Scratch workspaces.

The client never supplies these values. Keep all initial limits in one place so
the API, UI copy, and tests cannot drift apart.
"""

# Python: same environment and subprocess as the python_real challenge runner.
PYTHON_MAX_SOURCE = 5_000
PYTHON_TIMEOUT_SECONDS = 5.0
PYTHON_MAX_STDOUT = 20_000
PYTHON_MAX_STDERR = 20_000
PYTHON_MAX_FILES = 10
PYTHON_MAX_FILE_BYTES = 64 * 1024
PYTHON_MAX_TOTAL_FILE_BYTES = 256 * 1024
PYTHON_MAX_FILENAME = 128

# SQL: persistent, disposable SQLite workspace over a server-owned file.
SQL_MAX_SOURCE = 5_000
SQL_MAX_STATEMENTS = 50
SQL_MAX_ROWS = 100
SQL_MAX_CELL_CHARS = 4_000
SQL_MAX_COLUMNS = 64
SQL_MAX_RESPONSE_BYTES = 1_048_576
SQL_TIME_CAP_MS = 2_000
SQL_STEP_CAP = 2_000_000
SQL_WORKSPACE_TTL_SECONDS = 60 * 60
SQL_WORKSPACE_MAX_BYTES = 25 * 1024 * 1024
SQL_WORKSPACES_PER_LEARNER = 3


def python_limits() -> dict:
    return {
        "timeout_seconds": PYTHON_TIMEOUT_SECONDS,
        "max_source_characters": PYTHON_MAX_SOURCE,
        "max_stdout_characters": PYTHON_MAX_STDOUT,
        "max_stderr_characters": PYTHON_MAX_STDERR,
        "max_files": PYTHON_MAX_FILES,
        "max_file_bytes": PYTHON_MAX_FILE_BYTES,
        "max_total_file_bytes": PYTHON_MAX_TOTAL_FILE_BYTES,
    }


def sql_limits() -> dict:
    return {
        "max_source_characters": SQL_MAX_SOURCE,
        "max_statements": SQL_MAX_STATEMENTS,
        "max_rows_per_statement": SQL_MAX_ROWS,
        "max_cell_characters": SQL_MAX_CELL_CHARS,
        "max_response_bytes": SQL_MAX_RESPONSE_BYTES,
        "time_cap_ms": SQL_TIME_CAP_MS,
        "step_cap": SQL_STEP_CAP,
        "workspace_max_bytes": SQL_WORKSPACE_MAX_BYTES,
        "workspaces_per_learner": SQL_WORKSPACES_PER_LEARNER,
        "idle_ttl_seconds": SQL_WORKSPACE_TTL_SECONDS,
    }

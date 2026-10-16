"""Real-Python runner: executes learner code in an isolated subprocess.

Design notes:
  - ``sys.executable -I`` (isolated mode): no PYTHON* environment variables, no
    user site-packages, and the scratch directory is the working directory.
  - Every attempt gets a fresh scratch directory, removed afterwards.
  - File fixtures and the Python <-> SQLite bridge database are generated into
    the scratch directory before the run; ``DB_PATH`` is injected for bridge
    lessons (the file is created read-only).
  - This is a best-effort sandbox for a local single-user app, not an OS-level
    security boundary. A static screen blocks the most destructive modules and
    operations with a friendly message.
"""

import ast
import csv
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

if __package__:
    from . import datasets
else:
    import datasets

_DEFAULT_TIMEOUT = 5.0
_MAX_OUTPUT = 20_000
_MAX_FILE_READ = 100_000
_SENTINEL = "__CQ_RESULT__"

_BLOCKED_IMPORTS = {"subprocess", "shutil", "ctypes", "socket", "multiprocessing", "signal", "winreg", "pty"}
_BLOCKED_ATTRS = {
    ("os", "system"), ("os", "popen"), ("os", "remove"), ("os", "unlink"), ("os", "rmdir"),
    ("os", "removedirs"), ("os", "rename"), ("os", "replace"), ("os", "chmod"), ("os", "kill"),
    ("os", "startfile"),
}

_HARNESS = r'''
import io, json, sys, time, traceback

code_path = sys.argv[1]
db_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None

with open(code_path, "r", encoding="utf-8") as handle:
    source = handle.read()

scope = {"__name__": "__main__", "__file__": code_path}
if db_path:
    scope["DB_PATH"] = db_path

out = io.StringIO()
err = io.StringIO()
started = time.perf_counter()
error = None
line = None

old_out, old_err = sys.stdout, sys.stderr
sys.stdout, sys.stderr = out, err
try:
    exec(compile(source, "learner.py", "exec"), scope)
except SystemExit:
    pass
except BaseException as exc:
    error = f"{type(exc).__name__}: {exc}"
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == "learner.py":
            line = frame.lineno
            break
finally:
    sys.stdout, sys.stderr = old_out, old_err
    duration_ms = int((time.perf_counter() - started) * 1000)

payload = {
    "output": out.getvalue(),
    "stderr": err.getvalue(),
    "error": error,
    "error_line": line,
    "duration_ms": duration_ms,
}
sys.__stdout__.write("__CQ_RESULT__" + json.dumps(payload) + "\n")
sys.__stdout__.flush()
'''


class PythonRunError(Exception):
    """A safe, learner-facing error from the real-Python runner."""

    def __init__(self, message: str, line: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.line = line


def screen_source(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise PythonRunError(f"Syntax error: {exc.msg}.", line=exc.lineno) from None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _BLOCKED_IMPORTS:
                    raise PythonRunError(f"The '{alias.name}' module is not available in this sandbox.", line=node.lineno)
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in _BLOCKED_IMPORTS:
            raise PythonRunError(f"The '{node.module}' module is not available in this sandbox.", line=node.lineno)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            value = node.func.value
            if isinstance(value, ast.Name) and (value.id, node.func.attr) in _BLOCKED_ATTRS:
                raise PythonRunError(f"'{value.id}.{node.func.attr}()' is not available in this sandbox.", line=node.lineno)


def _write_fixture(scratch: Path, fixture: dict) -> list[str]:
    name = fixture["file"]
    target = scratch / name
    if "content" in fixture:
        target.write_text(fixture["content"], encoding="utf-8", newline="")
        return [name]
    connection = datasets.connect(fixture["dataset"], fixture.get("size", "small"))
    try:
        cursor = connection.execute(fixture["query"])
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchall()
    finally:
        connection.close()
    if fixture.get("format") == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows([list(row) for row in rows])
        target.write_text(buffer.getvalue(), encoding="utf-8", newline="")
    else:
        lines = ["\t".join(str(column) for column in columns)]
        lines.extend("\t".join("" if value is None else str(value) for value in row) for row in rows)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return [name]


def run_python(
    source: str,
    *,
    timeout_s: float = _DEFAULT_TIMEOUT,
    dataset: Optional[dict] = None,
    fixtures: Optional[list[dict]] = None,
) -> dict:
    """Run learner code. Returns output, error, duration, and created files."""
    screen_source(source)

    scratch = Path(tempfile.mkdtemp(prefix="cq_py_"))
    try:
        (scratch / "learner.py").write_text(source, encoding="utf-8")
        (scratch / "harness.py").write_text(_HARNESS, encoding="utf-8")
        seeded = {"learner.py", "harness.py"}

        db_path = ""
        if dataset:
            db_file = scratch / "learning.db"
            datasets.write_dataset_file(dataset["id"], dataset.get("size", "small"), db_file)
            db_path = str(db_file)
            seeded.add("learning.db")

        for fixture in fixtures or []:
            seeded.update(_write_fixture(scratch, fixture))

        command = [sys.executable, "-I", str(scratch / "harness.py"), str(scratch / "learner.py"), db_path]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=scratch,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired:
            return {
                "output": "",
                "error": f"This program was stopped after {timeout_s:g} seconds. Check for an endless loop.",
                "error_line": None,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "files": {},
                "timed_out": True,
            }

        payload = None
        for line in reversed(completed.stdout.splitlines()):
            if line.startswith(_SENTINEL):
                try:
                    payload = __import__("json").loads(line[len(_SENTINEL):])
                except ValueError:
                    payload = None
                break
        if payload is None:
            return {
                "output": "",
                "error": "The sandbox could not run that program. Try a smaller, simpler version.",
                "error_line": None,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "files": {},
                "timed_out": False,
            }

        files: dict[str, str] = {}
        for path in scratch.iterdir():
            if path.name in seeded or not path.is_file():
                continue
            if path.stat().st_size > _MAX_FILE_READ:
                continue
            try:
                files[path.name] = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

        return {
            "output": payload["output"][:_MAX_OUTPUT],
            "error": payload["error"],
            "error_line": payload["error_line"],
            "duration_ms": payload["duration_ms"],
            "files": files,
            "timed_out": False,
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

"""Real-Python runner: executes learner code in an isolated subprocess.

Design notes:
  - ``sys.executable -I`` (isolated mode): no PYTHON* environment variables, no
    user site-packages, and the scratch directory is the working directory.
  - Every attempt gets a fresh scratch directory, removed afterwards.
  - File fixtures and the Python <-> SQLite bridge database are generated into
    the scratch directory before the run; ``DB_PATH`` is injected for bridge
    lessons (the file is created read-only).
  - Challenge grading and learner-owned Python Scratch share this engine. Scratch
    adds a strict artifact adapter; no second execution engine exists.
  - This is a best-effort sandbox for a local single-user app, not an OS-level
    security boundary. A static screen blocks the most destructive modules and
    operations with a friendly message.
"""

import ast
import csv
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

if __package__:
    from . import datasets
else:
    import datasets

_DEFAULT_TIMEOUT = 5.0
_MAX_OUTPUT = 20_000
_STDERR_LIMIT = 20_000
_MAX_FILE_READ = 100_000
# Parent-side caps are a second line of defence for code that writes directly to
# the process file descriptors instead of through the harness's sys.stdout.
_MAX_PARENT_CAPTURE = 64 * 1024
_MAX_SCRATCH_FILES = 10
_MAX_SCRATCH_FILE_BYTES = 64 * 1024
_MAX_SCRATCH_TOTAL_BYTES = 256 * 1024
_MAX_SCRATCH_FILENAME = 128

_BLOCKED_IMPORTS = {"subprocess", "shutil", "ctypes", "socket", "multiprocessing", "signal", "winreg", "pty"}
_BLOCKED_ATTRS = {
    ("os", "system"), ("os", "popen"), ("os", "remove"), ("os", "unlink"), ("os", "rmdir"),
    ("os", "removedirs"), ("os", "rename"), ("os", "replace"), ("os", "chmod"), ("os", "kill"),
    ("os", "startfile"), ("os", "link"), ("os", "symlink"), ("os", "open"), ("os", "fdopen"),
    ("Path", "link_to"), ("Path", "hardlink_to"), ("Path", "symlink_to"),
}

_HARNESS = r'''
import io, json, sys, time, traceback

code_path = sys.argv[1]
db_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
result_path = sys.argv[3] if len(sys.argv) > 3 else None
MAX_OUTPUT = 20000


class LimitedBuffer(io.TextIOBase):
    """A text sink that keeps child memory bounded even for noisy programs."""

    def __init__(self, limit):
        self.limit = limit
        self._parts = []
        self._size = 0
        self.truncated = False

    def write(self, value):
        if not isinstance(value, str):
            value = str(value)
        remaining = max(0, self.limit - self._size)
        if remaining:
            chunk = value[:remaining]
            self._parts.append(chunk)
            self._size += len(chunk)
        if len(value) > remaining:
            self.truncated = True
        return len(value)

    def flush(self):
        pass

    def writable(self):
        return True

    def getvalue(self):
        return "".join(self._parts)


with open(code_path, "r", encoding="utf-8") as handle:
    source = handle.read()

scope = {"__name__": "__main__", "__file__": code_path}
if db_path:
    scope["DB_PATH"] = db_path

out = LimitedBuffer(MAX_OUTPUT)
err = LimitedBuffer(MAX_OUTPUT)
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
    "output_truncated": out.truncated,
    "stderr_truncated": err.truncated,
    "error": error,
    "error_line": line,
    "duration_ms": duration_ms,
}
if result_path:
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
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


def _drain_pipe(stream, buffer: bytearray, state: dict, key: str) -> None:
    """Read a child stream continuously so its pipe can never block the child."""
    try:
        while True:
            chunk = stream.read(65_536)
            if not chunk:
                break
            remaining = _MAX_PARENT_CAPTURE - len(buffer)
            if remaining > 0:
                buffer.extend(chunk[:remaining])
            if len(chunk) > remaining:
                state[key] = True
    finally:
        try:
            stream.close()
        except OSError:
            pass


def _run_process(command: list[str], cwd: Path, timeout_s: float) -> dict:
    """Run with bounded parent capture instead of unbounded ``capture_output``."""
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
        )
    except OSError as exc:
        raise PythonRunError("The Python runner could not start.") from exc

    stdout = bytearray()
    stderr = bytearray()
    truncated = {"stdout": False, "stderr": False}
    readers = [
        threading.Thread(target=_drain_pipe, args=(process.stdout, stdout, truncated, "stdout"), daemon=True),
        threading.Thread(target=_drain_pipe, args=(process.stderr, stderr, truncated, "stderr"), daemon=True),
    ]
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    finally:
        for reader in readers:
            reader.join(timeout=5)

    return {
        "stdout": bytes(stdout).decode("utf-8", "replace"),
        "stderr": bytes(stderr).decode("utf-8", "replace"),
        "stdout_truncated": truncated["stdout"],
        "stderr_truncated": truncated["stderr"],
        "timed_out": timed_out,
    }


def _read_text_artifact(path: Path, size: int) -> tuple[Optional[str], bool]:
    """Return (text, truncated), or (None, False) for a non-text file.

    Read at most one file cap so a huge generated file cannot first consume
    parent memory and only then be rejected. NUL bytes are treated as a binary
    signal; without that check, arbitrary binary data that happens to decode as
    UTF-8 would be returned as text.
    """
    limit = _MAX_SCRATCH_FILE_BYTES
    truncated = size > limit
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
        if b"\x00" in raw:
            return None, False
        if truncated:
            # Do not let a byte split in the middle of a UTF-8 sequence turn a
            # text file into a false binary result.
            for trim in range(0, 4):
                try:
                    return raw[: len(raw) - trim].decode("utf-8"), True
                except UnicodeDecodeError:
                    continue
            return None, False
        return raw.decode("utf-8"), False
    except (UnicodeDecodeError, OSError):
        return None, False


def _collect_scratch_files(scratch: Path, seeded: set[str]) -> tuple[list[dict], list[dict]]:
    """Collect bounded, non-seeded text artifacts from one run directory."""
    scratch_root = scratch.resolve()
    files: list[dict] = []
    skipped: list[dict] = []
    total_bytes = 0

    for path in sorted(scratch.iterdir(), key=lambda item: item.name):
        if path.name in seeded or not path.is_file():
            continue
        if path.is_symlink() or path.resolve().parent != scratch_root:
            skipped.append({"name": path.name[: _MAX_SCRATCH_FILENAME], "reason": "Not a regular file in this run."})
            continue
        if len(path.name) > _MAX_SCRATCH_FILENAME:
            skipped.append({"name": path.name[: _MAX_SCRATCH_FILENAME], "reason": "Filename is too long."})
            continue
        if len(files) >= _MAX_SCRATCH_FILES:
            skipped.append({"name": path.name, "reason": "The per-run file count limit was reached."})
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"name": path.name, "reason": "The file could not be read."})
            continue
        text, truncated = _read_text_artifact(path, size)
        if text is None:
            skipped.append({"name": path.name, "reason": "Only UTF-8 text files are returned."})
            continue
        encoded = text.encode("utf-8")
        remaining = _MAX_SCRATCH_TOTAL_BYTES - total_bytes
        if remaining <= 0:
            skipped.append({"name": path.name, "reason": "The total artifact size limit was reached."})
            continue
        if len(encoded) > remaining:
            text = encoded[:remaining].decode("utf-8", "ignore")
            encoded = text.encode("utf-8")
            truncated = True
        total_bytes += len(encoded)
        files.append({"name": path.name, "content": text, "truncated": truncated, "size_bytes": size})

    return files, skipped


def _execute(
    source: str,
    *,
    timeout_s: float,
    dataset: Optional[dict],
    fixtures: Optional[list[dict]],
    scratch_file_report: bool,
) -> dict:
    screen_source(source)

    scratch = Path(tempfile.mkdtemp(prefix="cq_py_"))
    try:
        learner_path = scratch / "learner.py"
        harness_path = scratch / "harness.py"
        result_path = scratch / "result.json"
        learner_path.write_text(source, encoding="utf-8")
        harness_path.write_text(_HARNESS, encoding="utf-8")
        seeded = {"learner.py", "harness.py", "result.json"}

        db_path = ""
        if dataset:
            db_file = scratch / "learning.db"
            datasets.write_dataset_file(dataset["id"], dataset.get("size", "small"), db_file)
            db_path = str(db_file)
            seeded.add("learning.db")

        for fixture in fixtures or []:
            seeded.update(_write_fixture(scratch, fixture))

        command = [
            sys.executable,
            "-I",
            str(harness_path),
            str(learner_path),
            db_path,
            str(result_path),
        ]
        started = time.perf_counter()
        process = _run_process(command, scratch, timeout_s)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if process["timed_out"]:
            return {
                "stdout": process["stdout"],
                "stderr": process["stderr"],
                "error": f"This program was stopped after {timeout_s:g} seconds. Check for an endless loop.",
                "error_line": None,
                "duration_ms": elapsed_ms,
                "timed_out": True,
                "output_truncated": process["stdout_truncated"],
                "stderr_truncated": process["stderr_truncated"],
                "files": {},
                "file_artifacts": [],
                "skipped_files": [],
            }

        payload = None
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = None
        if not isinstance(payload, dict):
            return {
                "stdout": process["stdout"],
                "stderr": process["stderr"],
                "error": "The sandbox could not run that program. Try a smaller, simpler version.",
                "error_line": None,
                "duration_ms": elapsed_ms,
                "timed_out": False,
                "output_truncated": process["stdout_truncated"],
                "stderr_truncated": process["stderr_truncated"],
                "files": {},
                "file_artifacts": [],
                "skipped_files": [],
            }

        legacy_files: dict[str, str] = {}
        file_artifacts: list[dict] = []
        skipped_files: list[dict] = []
        if scratch_file_report:
            file_artifacts, skipped_files = _collect_scratch_files(scratch, seeded)
        else:
            for path in scratch.iterdir():
                if path.name in seeded or not path.is_file() or path.is_symlink():
                    continue
                if path.resolve().parent != scratch.resolve():
                    continue
                try:
                    if path.stat().st_size > _MAX_FILE_READ:
                        continue
                    legacy_files[path.name] = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

        output = str(payload.get("output") or "")
        stderr = str(payload.get("stderr") or "")
        # The harness already caps these, but keep the public result bounded even
        # if a future harness changes.
        output_truncated = bool(payload.get("output_truncated")) or len(output) > _MAX_OUTPUT
        stderr_truncated = bool(payload.get("stderr_truncated")) or len(stderr) > _STDERR_LIMIT
        return {
            "stdout": output[:_MAX_OUTPUT],
            "stderr": stderr[:_STDERR_LIMIT],
            "error": payload.get("error"),
            "error_line": payload.get("error_line"),
            "duration_ms": int(payload.get("duration_ms") or elapsed_ms),
            "timed_out": False,
            "output_truncated": output_truncated,
            "stderr_truncated": stderr_truncated,
            "files": legacy_files,
            "file_artifacts": file_artifacts,
            "skipped_files": skipped_files,
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def run_python(
    source: str,
    *,
    timeout_s: float = _DEFAULT_TIMEOUT,
    dataset: Optional[dict] = None,
    fixtures: Optional[list[dict]] = None,
) -> dict:
    """Run learner code for challenge grading. Returns output, error, duration, and created files."""
    result = _execute(
        source,
        timeout_s=timeout_s,
        dataset=dataset,
        fixtures=fixtures,
        scratch_file_report=False,
    )
    return {
        "output": result["stdout"],
        "stderr": result["stderr"],
        "error": result["error"],
        "error_line": result["error_line"],
        "duration_ms": result["duration_ms"],
        "files": result["files"],
        "timed_out": result["timed_out"],
        "output_truncated": result["output_truncated"],
        "stderr_truncated": result["stderr_truncated"],
    }


def run_python_scratch(source: str, *, timeout_s: float = _DEFAULT_TIMEOUT) -> dict:
    """Run an arbitrary Python script and return the Scratch-shaped raw result.

    The caller owns request validation and response shaping. This wrapper does
    not load a dataset, fixtures, or challenge metadata, and it never touches
    learning progress.
    """
    return _execute(
        source,
        timeout_s=timeout_s,
        dataset=None,
        fixtures=None,
        scratch_file_report=True,
    )

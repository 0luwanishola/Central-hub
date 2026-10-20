"""Python Scratch: validate and run arbitrary scripts without challenge grading."""

from uuid import uuid4

try:
    from .. import python_runner
except ImportError:  # pragma: no cover - top-level backend imports
    import python_runner

from . import limits
from .errors import ScratchError


def _diagnostic_result(run_id: str, message: str, line: int | None = None) -> dict:
    lowered = message.lower()
    if lowered.startswith("syntax error"):
        kind = "syntax"
    elif "not available in this sandbox" in lowered:
        kind = "sandbox"
    else:
        kind = "request"
    return {
        "run_id": run_id,
        "status": "error",
        "stdout": "",
        "stderr": "",
        "error": message,
        "error_line": line,
        "error_kind": kind,
        "duration_ms": 0,
        "timed_out": False,
        "truncated": False,
        "files": [],
        "skipped_files": [],
        "limits": limits.python_limits(),
    }


def run_scratch(code: str, run_id: str | None = None) -> dict:
    """Run one complete Python script in a fresh subprocess.

    No learner id, track, challenge, dataset, fixture, or timeout is accepted
    from the client. The server owns every limit.
    """
    if not code.strip():
        raise ScratchError(422, "Write some Python code first.")
    if len(code) > limits.PYTHON_MAX_SOURCE:
        raise ScratchError(422, f"Keep Python under {limits.PYTHON_MAX_SOURCE:,} characters.")

    normalized_run_id = (run_id or "").strip() or str(uuid4())
    if len(normalized_run_id) > 80:
        raise ScratchError(422, "The run id must be 80 characters or fewer.")

    try:
        result = python_runner.run_python_scratch(
            code,
            timeout_s=limits.PYTHON_TIMEOUT_SECONDS,
        )
    except python_runner.PythonRunError as exc:
        if exc.message.startswith("The Python runner could not start"):
            raise ScratchError(500, "The Python runner could not start. Try again.") from exc
        return _diagnostic_result(normalized_run_id, exc.message, exc.line)
    except OSError as exc:
        raise ScratchError(500, "The Python workspace could not be prepared. Try again.") from exc

    files = result.get("file_artifacts", [])
    skipped = result.get("skipped_files", [])
    output_truncated = bool(result.get("output_truncated"))
    stderr_truncated = bool(result.get("stderr_truncated"))
    file_truncated = any(item.get("truncated") for item in files)
    timed_out = bool(result.get("timed_out"))
    error = result.get("error")

    if timed_out:
        status = "timeout"
    elif error:
        status = "error"
    else:
        status = "completed"

    if timed_out:
        error_kind = "timeout"
    elif error:
        lowered = str(error).lower()
        if "syntax error" in lowered:
            error_kind = "syntax"
        elif "not available in this sandbox" in lowered:
            error_kind = "sandbox"
        else:
            error_kind = "runtime"
    else:
        error_kind = None

    return {
        "run_id": normalized_run_id,
        "status": status,
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "error": error,
        "error_line": result.get("error_line"),
        "error_kind": error_kind,
        "duration_ms": result.get("duration_ms", 0),
        "timed_out": timed_out,
        "truncated": output_truncated or stderr_truncated or file_truncated,
        "files": files,
        "skipped_files": skipped,
        "limits": limits.python_limits(),
    }

"""Server-owned SQLite files for learner-owned SQL Scratch workspaces.

V1 is deliberately process-local: the registry, ownership, expiry, and locks
live in this module. That matches the single local API process. Do not run
multiple API workers against it until the registry is moved to a shared store.
"""

import contextlib
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

try:
    from .. import datasets, learning
except ImportError:  # pragma: no cover - top-level backend imports
    import datasets
    import learning

from . import limits
from .errors import ScratchError

_DEFAULT_ROOT = Path(tempfile.gettempdir()) / "central_hub" / "sql_scratch"
_DB_NAME = "workspace.sqlite3"
_WORKSPACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")

_registry_lock = threading.RLock()
_workspaces: dict[str, "Workspace"] = {}
_learner_workspaces: dict[str, set[str]] = {}
_root_override: Optional[Path] = None


@dataclass
class Workspace:
    workspace_id: str
    learner_id: str
    base: str
    base_name: str
    directory: Path
    db_path: Path
    created_at: float
    last_used: float
    lock: threading.RLock = field(default_factory=threading.RLock)
    deleted: bool = False


def configure_root(root: Path) -> None:
    """Test hook: choose a root and reset process-local workspace state."""
    global _root_override
    with _registry_lock:
        _root_override = Path(root)
        _workspaces.clear()
        _learner_workspaces.clear()


def _root() -> Path:
    if _root_override is not None:
        return _root_override
    configured = os.getenv("CQ_SCRATCH_SQL_ROOT")
    return Path(configured).expanduser() if configured else _DEFAULT_ROOT


def _remove_path(path: Path) -> None:
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    except OSError:
        pass


def initialize(root: Path | None = None) -> None:
    """Start clean: old files are inaccessible after a restart, so remove them."""
    global _root_override
    if root is not None:
        _root_override = Path(root)
    root_path = _root()
    with _registry_lock:
        _workspaces.clear()
        _learner_workspaces.clear()
        try:
            root_path.mkdir(parents=True, exist_ok=True)
            try:
                root_path.chmod(0o700)
            except OSError:
                pass
            for child in list(root_path.iterdir()):
                _remove_path(child)
        except OSError:
            # The create path will surface a clear workspace error if the root
            # still cannot be prepared.
            pass


def _expired(workspace: Workspace, now: Optional[float] = None) -> bool:
    return (now or time.time()) - workspace.last_used >= limits.SQL_WORKSPACE_TTL_SECONDS


def _metadata(workspace: Workspace, now: Optional[float] = None) -> dict:
    current = now or time.time()
    remaining = max(0, int(workspace.last_used + limits.SQL_WORKSPACE_TTL_SECONDS - current))
    return {
        "workspace_id": workspace.workspace_id,
        "base": workspace.base,
        "base_name": workspace.base_name,
        "expires_in_seconds": remaining,
        "idle_ttl_seconds": limits.SQL_WORKSPACE_TTL_SECONDS,
        "limits": limits.sql_limits(),
    }


def _resolve_base(base: str) -> tuple[str, str]:
    value = (base or "").strip()
    if value == "blank":
        return "blank", "Blank SQLite database"
    if not value or len(value) > 64:
        raise ScratchError(422, "Choose a blank workspace or a registered dataset.")
    try:
        dataset = datasets.get(value)
    except datasets.UnknownDataset:
        raise ScratchError(422, "That dataset is not available as a scratch base.") from None
    return dataset.id, dataset.name


def _seed_database(base: str, path: Path) -> None:
    if base == "blank":
        connection = sqlite3.connect(path)
        try:
            connection.execute("PRAGMA page_size = 4096")
            connection.execute("PRAGMA user_version = 0")
            connection.commit()
        finally:
            connection.close()
    else:
        datasets.write_dataset_file(base, "small", path, read_only=False)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _remove_database_files(db_path: Path) -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        _remove_path(Path(f"{db_path}{suffix}"))


def _remove_from_registry(workspace: Workspace) -> None:
    _workspaces.pop(workspace.workspace_id, None)
    owned = _learner_workspaces.get(workspace.learner_id)
    if owned is not None:
        owned.discard(workspace.workspace_id)
        if not owned:
            _learner_workspaces.pop(workspace.learner_id, None)
    workspace.deleted = True


def cleanup_expired(now: Optional[float] = None) -> None:
    """Remove idle workspaces. A busy workspace is skipped until its run ends."""
    current = now or time.time()
    with _registry_lock:
        candidates = [workspace for workspace in _workspaces.values() if _expired(workspace, current)]
    for workspace in candidates:
        acquired = workspace.lock.acquire(blocking=False)
        if not acquired:
            continue
        try:
            with _registry_lock:
                if workspace.deleted or not _expired(workspace, current):
                    continue
                _remove_from_registry(workspace)
            _remove_path(workspace.directory)
        finally:
            workspace.lock.release()


def create_workspace(learner_id: str, base: str) -> dict:
    normalized_id = learning.normalize_learner_id(learner_id)
    if normalized_id is None:
        raise ScratchError(404, "Learning profile not found. Refresh the page to start a new profile.")
    base_id, base_name = _resolve_base(base)

    cleanup_expired()
    with _registry_lock:
        owned = _learner_workspaces.get(normalized_id, set())
        active = [
            workspace_id
            for workspace_id in owned
            if workspace_id in _workspaces and not _workspaces[workspace_id].deleted
        ]
        if len(active) >= limits.SQL_WORKSPACES_PER_LEARNER:
            raise ScratchError(
                409,
                f"You already have {limits.SQL_WORKSPACES_PER_LEARNER} active SQL workspaces. "
                "Delete one or wait for it to expire before creating another.",
            )
        workspace_id = secrets.token_urlsafe(32)
        root_path = _root()
        try:
            root_path.mkdir(parents=True, exist_ok=True)
            directory = root_path / f"ws-{workspace_id}"
            directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        except OSError as exc:
            raise ScratchError(500, "The SQL workspace could not be created. Try again.") from exc

        db_path = directory / _DB_NAME
        try:
            _seed_database(base_id, db_path)
        except ScratchError:
            _remove_path(directory)
            raise
        except Exception as exc:
            _remove_path(directory)
            raise ScratchError(
                500,
                "The selected SQL workspace base could not be prepared. Try a blank workspace or another dataset.",
            ) from exc
        now = time.time()
        workspace = Workspace(
            workspace_id=workspace_id,
            learner_id=normalized_id,
            base=base_id,
            base_name=base_name,
            directory=directory,
            db_path=db_path,
            created_at=now,
            last_used=now,
        )
        _workspaces[workspace_id] = workspace
        _learner_workspaces.setdefault(normalized_id, set()).add(workspace_id)
        return _metadata(workspace, now)


def _lookup(learner_id: str, workspace_id: str) -> Workspace:
    normalized_id = learning.normalize_learner_id(learner_id)
    if normalized_id is None or not _WORKSPACE_ID_PATTERN.match(workspace_id or ""):
        raise ScratchError(404, "That SQL workspace is not available. Create a new workspace.")
    with _registry_lock:
        workspace = _workspaces.get(workspace_id)
        if workspace is None or workspace.learner_id != normalized_id:
            # Unknown and another learner's token deliberately share one response.
            raise ScratchError(404, "That SQL workspace is not available. Create a new workspace.")
        return workspace


@contextlib.contextmanager
def workspace_session(learner_id: str, workspace_id: str) -> Iterator[Workspace]:
    """Serialize run/reset/delete against one workspace, not the whole process."""
    workspace = _lookup(learner_id, workspace_id)
    workspace.lock.acquire()
    try:
        if workspace.deleted:
            raise ScratchError(404, "That SQL workspace is not available. Create a new workspace.")
        if _expired(workspace):
            raise ScratchError(410, "That SQL workspace has expired. Create a new workspace.")
        yield workspace
    finally:
        workspace.lock.release()


def workspace_db_path(workspace: Workspace) -> Path:
    """Resolve only a server-owned database below the scratch root."""
    root_path = _root().resolve()
    try:
        directory = workspace.directory.resolve(strict=True)
    except OSError as exc:
        raise ScratchError(500, "The SQL workspace file is unavailable. Create a new workspace.") from exc
    if directory.parent != root_path or directory.is_symlink():
        raise ScratchError(500, "The SQL workspace file is unavailable. Create a new workspace.")
    db_path = directory / _DB_NAME
    if db_path.is_symlink():
        raise ScratchError(500, "The SQL workspace file is unavailable. Create a new workspace.")
    try:
        resolved = db_path.resolve(strict=False)
    except OSError as exc:
        raise ScratchError(500, "The SQL workspace file is unavailable. Create a new workspace.") from exc
    if resolved.parent != directory:
        raise ScratchError(500, "The SQL workspace file is unavailable. Create a new workspace.")
    return resolved


def touch(workspace: Workspace) -> None:
    workspace.last_used = time.time()


def workspace_metadata(workspace: Workspace) -> dict:
    return _metadata(workspace)


def reset_workspace(learner_id: str, workspace_id: str) -> dict:
    with workspace_session(learner_id, workspace_id) as workspace:
        db_path = workspace_db_path(workspace)
        _remove_database_files(db_path)
        try:
            _seed_database(workspace.base, db_path)
        except Exception as exc:
            raise ScratchError(
                500,
                "The workspace could not be reset to its base. Try again or create a new workspace.",
            ) from exc
        touch(workspace)
        return _metadata(workspace)


def delete_workspace(learner_id: str, workspace_id: str) -> dict:
    workspace = _lookup(learner_id, workspace_id)
    with workspace.lock:
        if workspace.deleted:
            raise ScratchError(404, "That SQL workspace is not available. Create a new workspace.")
        with _registry_lock:
            _remove_from_registry(workspace)
        _remove_path(workspace.directory)
        return {"workspace_id": workspace_id, "deleted": True}


def list_bases() -> list[dict]:
    return [
        {"id": dataset.id, "name": dataset.name, "summary": dataset.summary}
        for dataset in datasets.DATASETS.values()
    ]

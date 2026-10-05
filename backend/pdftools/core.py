"""Shared plumbing for the PDF tools.

Every PDF tool does the same four things: accept one or more uploads, write them
to a temp directory, transform them, and hand the result back as a download. Only
the transform differs, so each tool module supplies just that and everything else
lives here.

Two decisions worth knowing before changing this module:

**Uploads are streamed to disk, never buffered in memory.** These are this app's
first file uploads and a PDF can be far larger than anything else it handles.
``save_uploads`` writes in chunks and checks the budget as it goes, so an
oversized file is rejected part-way instead of after the whole thing was read.

**Results are passed back as a download token, not streamed through the POST.**
Legacy htmx requests receive a small HTML fragment containing a link to
``GET /api/pdf/download/{token}``. Standalone clients request JSON with that same
download URL and the filename. Both let the browser handle the final download.

Inputs are deleted as soon as processing finishes. Results live until they are
downloaded or ``RESULTS_TTL`` expires, so ``cleanup_stale()`` runs on every new
request rather than trusting a background sweeper to still be alive.
"""

from __future__ import annotations

import secrets
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from fastapi.responses import FileResponse, HTMLResponse, Response
from starlette.background import BackgroundTask

# A total cap across all files in one request. Generous for the merge and image
# tools, low enough that a single request cannot exhaust the disk.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

# How long a processed result stays downloadable before it is swept up.
RESULTS_TTL = 600  # seconds

_CHUNK = 256 * 1024


class ToolError(Exception):
    """A problem with the user's input. The message is shown on the page."""


@dataclass
class Result:
    """A finished file waiting to be downloaded."""

    path: Path
    download_name: str
    created: float
    media_type: str = "application/pdf"


@dataclass
class Draft:
    """An uploaded PDF being previewed, before the tool has run on it.

    The signature tool needs this: the user picks a file, previews a page to decide
    where the signature goes, and only then runs the tool. That is three requests,
    and re-uploading the PDF for the last one would mean putting a potentially large
    file across the wire twice.
    """

    path: Path
    filename: str
    created: float


# Processed results, keyed by an unguessable token.
#
# This is module-level mutable state on purpose: the download is a separate request
# from the upload that produced it, so the two have to meet somewhere. The warning
# about module-level state elsewhere in this codebase applies to values passed
# *within* a request, not to a deliberate cross-request store like this one (the
# provider response caches are the same pattern). Entries are never mutated after
# being added, and the dict is only touched by the one event-loop thread, so no
# lock is needed.
_results: dict[str, Result] = {}

# Same reasoning, different lifecycle: a draft is consumed by the tool run that
# finishes the job, and swept on the same TTL if the user walks away.
_drafts: dict[str, Draft] = {}


def remove_tree(path: Path) -> None:
    """Delete a temp directory, ignoring anything already gone."""
    shutil.rmtree(path, ignore_errors=True)


def cleanup_stale() -> None:
    """Delete results and drafts nobody came back for. Called per request."""
    cutoff = time.time() - RESULTS_TTL
    for token in [t for t, item in _results.items() if item.created < cutoff]:
        item = _results.pop(token, None)
        if item is not None:
            remove_tree(item.path.parent)
    for token in [t for t, item in _drafts.items() if item.created < cutoff]:
        item = _drafts.pop(token, None)
        if item is not None:
            remove_tree(item.path.parent)


def new_workspace() -> Path:
    """A temp directory for one request's inputs and results."""
    return Path(tempfile.mkdtemp(prefix="pdftool-"))


def store_draft(source: Path, filename: str) -> str:
    """Hold an upload for a later request. Returns its token.

    Takes ownership of ``source`` and its parent directory, same as ``store_result``.
    """
    cleanup_stale()
    token = secrets.token_urlsafe(16)
    _drafts[token] = Draft(path=source, filename=filename, created=time.time())
    return token


def find_draft(token: str) -> Optional[Draft]:
    return _drafts.get(token)


def take_draft(token: str) -> Optional[Draft]:
    """Fetch a draft and remove it, so a previewed file is signed at most once."""
    return _drafts.pop(token, None)


def put_draft(token: str, draft: Draft) -> None:
    """Return a taken draft to the store.

    Used when a run fails after the draft was claimed: a mistyped width should not
    cost the user their upload and the preview they already positioned on. The
    original timestamp goes back with it, so the TTL is not silently extended.
    """
    _drafts[token] = draft


def store_result(source: Path, download_name: str, media_type: str = "application/pdf") -> str:
    """Keep ``source`` downloadable and return its token.

    This takes ownership of ``source`` and its parent directory: whoever called it
    must not delete that tree afterwards.
    """
    cleanup_stale()
    token = secrets.token_urlsafe(16)
    _results[token] = Result(
        path=source,
        download_name=download_name,
        created=time.time(),
        media_type=media_type,
    )
    return token


def find_result(token: str) -> Optional[Result]:
    return _results.get(token)


def take_result(token: str) -> Optional[Result]:
    """Fetch a result and remove it, so a link works only once."""
    return _results.pop(token, None)


class Budget:
    """Tracks bytes written so one request cannot exceed ``MAX_UPLOAD_BYTES``."""

    def __init__(self, limit: int = MAX_UPLOAD_BYTES) -> None:
        self.limit = limit
        self.used = 0

    def spend(self, count: int) -> None:
        self.used += count
        if self.used > self.limit:
            raise ToolError(
                f"That upload is too large. The limit is "
                f"{self.limit // (1024 * 1024)} MB for all files in one request."
            )


async def save_upload(upload, destination: Path, budget: Budget) -> Path:
    """Stream one upload to ``destination``, enforcing ``budget`` as it goes."""
    written = 0
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(_CHUNK)
            if not chunk:
                break
            budget.spend(len(chunk))
            out.write(chunk)
            written += len(chunk)
    if written == 0:
        raise ToolError(f"{upload.filename or 'A file'} is empty.")
    return destination


async def save_uploads(
    uploads: Iterable,
    folder: Path,
    suffixes: Iterable[str],
    budget: Optional[Budget] = None,
) -> list[Path]:
    """Save every upload into ``folder``, checking each has an accepted suffix.

    Files keep their own names because the tools build download names from them:
    splitting ``invoice.pdf`` should not produce ``00-split.zip``. Only genuinely
    repeated names get a counter, and the folder is private to this request, so
    nothing outside it can collide.

    The suffix check is a usability guard, not a security one: the real validation
    is whether the bytes actually parse as a PDF.
    """
    allowed = {s.lower() for s in suffixes}
    budget = budget or Budget()

    uploads = [u for u in uploads if u and u.filename]
    if not uploads:
        raise ToolError("Choose at least one file.")

    saved: list[Path] = []
    for upload in uploads:
        name = Path(upload.filename or "").name
        suffix = Path(name).suffix.lower()
        if suffix not in allowed:
            wanted = ", ".join(sorted(allowed))
            raise ToolError(f"{name or 'That file'} is not one of: {wanted}.")
        saved.append(await save_upload(upload, folder / _unique_name(folder, name), budget))

    return saved


# Leaves room for the counter suffix that _unique_name may add.
_MAX_STEM = 120


def _unique_name(folder: Path, name: str) -> str:
    """``name`` if free in ``folder``, otherwise ``name`` with a counter."""
    path = Path(name)
    stem = path.stem[:_MAX_STEM] or "file"
    candidate = f"{stem}{path.suffix}"

    if not (folder / candidate).exists():
        return candidate

    for counter in range(2, 100):
        numbered = f"{stem}-{counter}{path.suffix}"
        if not (folder / numbered).exists():
            return numbered

    raise ToolError("Too many files with the same name.")


def error_response(message: str) -> HTMLResponse:
    """Render a message inside the tool panel instead of replacing the page."""
    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return HTMLResponse(f'<div class="pdf-error" role="alert">{safe}</div>', status_code=400)


def download_response(result: Result) -> Response:
    """Stream a stored result as an attachment, deleting it once sent."""
    return FileResponse(
        path=result.path,
        filename=result.download_name,
        media_type=result.media_type,
        # Runs only after the body has been sent, so a cancelled or failed
        # download does not delete a file a retry might still want.
        background=BackgroundTask(remove_tree, result.path.parent),
    )

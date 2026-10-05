"""Page-level PDF tools: merging, splitting and reorganising pages.

These three share most of their logic, so they live together. Each exposes a
``run(inputs, params) -> (path, download_name)`` function; ``pdftools/__init__.py``
maps tool ids onto them.

All three take a single output path and write to it in one pass, so a failure part
way through cannot leave a half-written file looking complete.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from .core import ToolError


def _open(path: Path, password: str = "") -> PdfReader:
    """Open a PDF, turning pypdf's errors into messages a user can act on."""
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            # An empty password is common and legitimate, so try it before giving up.
            if not reader.decrypt(password or ""):
                raise ToolError(
                    f"{path.name} is password protected. Remove the password first, "
                    "or use the Unlock PDF tool."
                )
        return reader
    except PdfReadError as exc:
        raise ToolError(f"{path.name} could not be read as a PDF ({exc}).") from exc
    except OSError as exc:
        raise ToolError(f"{path.name} could not be opened ({exc}).") from exc


def _parse_range(spec: str, total: int, what: str) -> list[int]:
    """Parse ``"1-3, 5, 8-"`` into 0-based indexes.

    Ranges are inclusive and 1-based; an open end runs to the end of the document.
    Whitespace is ignored and reversed ranges are rejected rather than silently
    swapped, since ``5-1`` is far more likely to be a typo than an intent.
    """
    wanted: list[int] = []
    for chunk in (part.strip() for part in spec.split(",")):
        if not chunk:
            continue
        match = re.fullmatch(r"(\d+)\s*(?:-\s*(\d+)?)?", chunk)
        if not match:
            raise ToolError(f"{what} '{chunk}' is not a page or range.")

        first = int(match.group(1))
        if "-" in chunk:
            # An open end such as "8-" runs to the last page.
            last = int(match.group(2)) if match.group(2) else total
        else:
            last = first

        if first < 1 or last < 1:
            raise ToolError(f"{what} must start at page 1.")
        if first > last:
            raise ToolError(f"{what} '{chunk}' runs backwards.")
        if first > total:
            raise ToolError(f"{what} '{chunk}' is past the end; the document has {total} pages.")

        wanted.extend(range(first - 1, min(last, total)))

    if not wanted:
        raise ToolError(f"No pages selected for {what}.")
    return wanted


def _write(writer: PdfWriter, output: Path) -> None:
    """Write the writer to ``output``, replacing anything already there."""
    output.unlink(missing_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)


def _copy_pages(reader: PdfReader, indexes: Sequence[int], writer: PdfWriter) -> None:
    for index in indexes:
        writer.add_page(reader.pages[index])


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


def merge(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Concatenate several PDFs, in the order they were chosen."""
    if len(inputs) < 2:
        raise ToolError("Choose at least two PDFs to merge.")

    writer = PdfWriter()
    added = 0
    for path in inputs:
        reader = _open(path)
        for page in reader.pages:
            writer.add_page(page)
            added += 1

    if added == 0:
        raise ToolError("Those PDFs contain no pages.")

    _write(writer, output)
    return "merged.pdf"


def split(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Split one PDF per selected page, as a ZIP.

    Splitting "every page" is only useful as separate files, so the result is
    zipped. Per-range extraction, where the pages stay together, is the page
    organiser's job instead.
    """
    if len(inputs) != 1:
        raise ToolError("Choose exactly one PDF to split.")

    spec = (params.get("pages") or "").strip()
    if not spec:
        raise ToolError("Enter the pages to split, for example 1-3 or 1,4,7.")

    source = inputs[0]
    reader = _open(source)
    total = len(reader.pages)
    indexes = _parse_range(spec, total, "Page")

    stem = source.stem or "document"

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for index in indexes:
            writer = PdfWriter()
            writer.add_page(reader.pages[index])
            # pypdf 6 has no __bytes__, so serialise through a buffer explicitly.
            buffer = io.BytesIO()
            writer.write(buffer)
            archive.writestr(f"{stem}-page-{index + 1}.pdf", buffer.getvalue())

    return f"{stem}-split.zip"


def organise(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Keep, reorder, rotate and delete pages in one pass.

    ``pages`` is the new order, so ``"3,1,2"`` puts page 3 first. Anything not
    listed is dropped, which is what makes this both the reorder and the delete
    tool - there is no separate "delete pages" step to get out of sync.
    ``rotate`` is applied per page number and accepts ``90``, ``180``, ``270`` or
    a leading ``-`` to turn anticlockwise.
    """
    if len(inputs) != 1:
        raise ToolError("Choose exactly one PDF.")

    spec = (params.get("pages") or "").strip()
    if not spec:
        raise ToolError("Enter the pages to keep, in the order you want them. "
                        "For example 1,3,2 or 2-4.")

    source = inputs[0]
    reader = _open(source)
    total = len(reader.pages)
    indexes = _parse_range(spec, total, "Page")

    rotations = _parse_rotations(params.get("rotate") or "", total)

    writer = PdfWriter()
    for index in indexes:
        page = reader.pages[index]
        degrees = rotations.get(index + 1)
        if degrees:
            page.rotate(degrees)
        writer.add_page(page)

    _write(writer, output)
    return f"{source.stem or 'document'}-organised.pdf"


def _parse_rotations(spec: str, total: int) -> dict[int, int]:
    """Parse ``"1=90, 3=-90"`` into ``{page_number: degrees}``."""
    rotations: dict[int, int] = {}
    for chunk in (part.strip() for part in spec.split(",")):
        if not chunk:
            continue
        if "=" not in chunk:
            raise ToolError(f"Rotation '{chunk}' should look like 1=90 or 3=-90.")
        page_raw, _, degrees_raw = chunk.partition("=")
        try:
            page = int(page_raw.strip())
            degrees = int(degrees_raw.strip())
        except ValueError as exc:
            raise ToolError(f"Rotation '{chunk}' should look like 1=90 or 3=-90.") from exc

        if not 1 <= page <= total:
            raise ToolError(f"Rotation refers to page {page}, but the document has {total}.")
        if degrees not in (90, 180, 270, -90, -180, -270):
            raise ToolError(f"Rotation for page {page} must be 90, 180 or 270.")
        rotations[page] = degrees

    return rotations

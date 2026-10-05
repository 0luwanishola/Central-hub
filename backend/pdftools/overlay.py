"""Shared helpers for the tools that draw something onto a page.

Add Text, Add Image and Watermark are the same operation with different ink: build
a one-page reportlab layer, merge it over the chosen pages, write the result. Only
the drawing differs, so the page geometry, the merge loop and the form-value
parsing live here.

**Placement is by margin box, not raw coordinates.** Each page has a margin inset
from its edges, and a nine-way position names a corner, edge or centre of the area
left over inside that margin. The content's own size is subtracted before the
anchor is resolved, so a long line of text at ``bottom-right`` still lands inside
the margin rather than hanging off the page. This is why these tools have no X and
Y fields: they would be coordinates with no feedback, which is exactly the problem
the signature tool's click-to-place preview exists to solve.
"""

from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

from pypdf import PdfReader, PdfWriter

from .core import ToolError

# Fonts reportlab ships with. No font files to bundle, and every PDF reader has
# them, so the output stays small and portable.
FONTS = {
    "Helvetica": "Helvetica",
    "Helvetica-Bold": "Helvetica-Bold",
    "Times": "Times-Roman",
    "Times-Bold": "Times-Bold",
    "Courier": "Courier",
}

# (fraction across, fraction up) of the area inside the margin box.
POSITIONS = {
    "top-left": (0.0, 1.0),
    "top-centre": (0.5, 1.0),
    "top-right": (1.0, 1.0),
    "middle-left": (0.0, 0.5),
    "centre": (0.5, 0.5),
    "middle-right": (1.0, 0.5),
    "bottom-left": (0.0, 0.0),
    "bottom-centre": (0.5, 0.0),
    "bottom-right": (1.0, 0.0),
}


# ---------------------------------------------------------------------------
# Form values
# ---------------------------------------------------------------------------


def pick(params: dict, key: str, choices: dict, default: str) -> str:
    """The value of ``key`` if it is one of ``choices``, else ``default``.

    Silently falling back beats erroring on a value the user picked from a menu
    we rendered ourselves; a mismatch there means the two drifted apart, not that
    the user did something wrong.
    """
    value = (params.get(key) or "").strip()
    return value if value in choices else default


def number(
    params: dict,
    key: str,
    default: float,
    low: float,
    high: float,
    label: str = "",
) -> float:
    """A float field clamped to a range. Blank means the default."""
    raw = (params.get(key) or "").strip()
    label = label or key.replace("_", " ")
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ToolError(f"{label.capitalize()} must be a number, not '{raw}'.") from exc
    return max(low, min(high, value))


def integer(params: dict, key: str, default: int, low: int, high: int) -> int:
    return int(number(params, key, default, low, high))


def colour(params: dict, key: str = "colour", default: tuple = (0.0, 0.0, 0.0)):
    """A ``#rrggbb`` or ``#rgb`` field as reportlab's 0-1 float triple.

    Alpha is kept separate because reportlab applies it to the whole drawing
    state rather than to a colour.
    """
    raw = (params.get(key) or "").strip().lstrip("#")
    if not raw:
        return default
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
        raise ToolError(f"Colour must be a hex value like #1a2b3c, not '{params.get(key)}'.")
    return tuple(int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))


def opacity(params: dict, key: str = "opacity", default: float = 1.0) -> float:
    """An opacity field. Accepts a percentage or a fraction."""
    raw = (params.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ToolError(f"Opacity must be a number, not '{raw}'.") from exc
    if value > 1.0:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def text(params: dict, key: str, label: str, required: bool = True) -> str:
    value = (params.get(key) or "").strip()
    if required and not value:
        raise ToolError(f"Enter the {label}.")
    return value


def one_input(inputs: Sequence, what: str) -> "Path":
    """Exactly one uploaded PDF, with a message that says which tool."""
    if len(inputs) != 1:
        raise ToolError(f"Choose exactly one {what}.")
    return inputs[0]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


def anchor(
    position: str,
    margin: float,
    page_width: float,
    page_height: float,
    content_width: float,
    content_height: float,
) -> tuple:
    """Bottom-left point for ``content_width`` x ``content_height`` at ``position``.

    Everything is measured inside the margin box. If the content is wider than
    that box the available width goes negative and the left margin wins, which
    keeps the result on the page instead of mirroring it off the edge.
    """
    fx, fy = POSITIONS[position]
    usable_width = max(0.0, page_width - 2 * margin - content_width)
    usable_height = max(0.0, page_height - 2 * margin - content_height)
    return margin + fx * usable_width, margin + fy * usable_height


def overlay_page(width: float, height: float, draw: Callable) -> PdfReader:
    """A single-page PDF the same size as the target page, with ``draw`` applied.

    ``draw(canvas, width, height)`` receives the bare reportlab canvas; the caller
    sets its own colours, fonts and alpha.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    import io

    buffer = io.BytesIO()
    pdf = rl_canvas.Canvas(buffer, pagesize=(width, height))
    # A reportlab page carries no margin, but the default paragramming state can
    # still emit a stray fill; an explicit save-state keeps the caller's drawing
    # isolated from the canvas defaults.
    pdf.saveState()
    try:
        draw(pdf, width, height)
    finally:
        pdf.restoreState()
        pdf.showPage()
        pdf.save()

    buffer.seek(0)
    return PdfReader(buffer)


def apply_overlay(
    reader: PdfReader,
    indexes: Sequence[int],
    draw: Callable,
    output,
    on_page: Optional[Callable] = None,
) -> int:
    """Merge a freshly drawn layer onto each page in ``indexes``.

    The layer is drawn per page rather than once, because a page's size decides
    where a margin-relative position lands. ``draw`` is called as
    ``draw(canvas, width, height, page_number)`` where the page number is 1-based,
    so a tool that varies its content per page can.

    Pages are merged in place on the reader and the writer takes them in document
    order, so the output keeps the original page sequence — the unselected pages
    are copied through untouched.
    """
    writer = PdfWriter()
    wanted = set(indexes)
    drawn = 0

    for position, page in enumerate(reader.pages):
        number = position + 1
        if position in wanted:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            layer = overlay_page(width, height, lambda pdf, w, h, n=number: draw(pdf, w, h, n))
            page.merge_page(layer.pages[0])
            drawn += 1
            if on_page is not None:
                on_page(number)
        writer.add_page(page)

    output.unlink(missing_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)

    return drawn
"""The core Edit tools: Add Text, Add Image, Watermark and Edit Metadata.

These share ``overlay.py``'s placement and merge machinery. What each one does
inside the draw callback is the whole of its own logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from pypdf import PdfReader

from .core import ToolError
from .organise import _open, _parse_range, _write
from .overlay import (
    FONTS,
    POSITIONS,
    anchor,
    apply_overlay,
    colour,
    number,
    one_input,
    opacity,
    pick,
    text as field,
)

# Margin default in points (72 to the inch), so 36 is half an inch.
DEFAULT_MARGIN = 36.0


def _pages(reader: PdfReader, params: dict) -> list:
    """Selected page indexes. An empty page field means the whole document."""
    spec = (params.get("pages") or "").strip()
    total = len(reader.pages)
    return list(range(total)) if not spec else _parse_range(spec, total, "Page")


def _rotation(params: dict, key: str, default: float) -> float:
    """A rotation in degrees, anticlockwise positive.

    Any angle is allowed rather than just the right-angle multiples: a watermark
    wants 45 degrees, and a diagonal "SAMPLE" stamp over a form wants 30. The form
    offers the common ones but the field takes whatever is typed.
    """
    return number(params, key, default, -360, 360, "rotation")


def _suffix(path: Path, label: str) -> str:
    return f"{path.stem or 'document'}-{label}.pdf"


# ---------------------------------------------------------------------------
# Add Text
# ---------------------------------------------------------------------------


def add_text(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Stamp text onto the chosen pages at a margin-relative position.

    Blank lines in the input are kept, so a multi-line stamp lands as typed. The
    line height is fixed at 1.2x the font size rather than measured, which keeps
    the height estimate used for placement honest.
    """
    source = one_input(inputs, "PDF")
    reader = _open(source)
    indexes = _pages(reader, params)

    content = (params.get("text") or "")
    if not content.strip():
        raise ToolError("Enter the text to add.")

    font_name = pick(params, "font", FONTS, "Helvetica")
    font = FONTS[font_name]
    size = number(params, "size", 24, 4, 200, "font size")
    fill = colour(params)
    position = pick(params, "position", POSITIONS, "bottom-right")
    margin = number(params, "margin", DEFAULT_MARGIN, 0, 200, "margin")
    rotation = _rotation(params, "rotation", 0)

    lines = content.splitlines() or [""]
    line_height = size * 1.2

    from reportlab.pdfbase.pdfmetrics import stringWidth

    widest = max(stringWidth(line, font, size) for line in lines) if lines else 0.0
    box_width = widest
    box_height = line_height * len(lines)

    def draw(canvas, width, height, _page_number):
        canvas.setFont(font, size)
        canvas.setFillColorRGB(*fill)
        x, y = anchor(position, margin, width, height, box_width, box_height)

        if rotation:
            # Rotate about the anchor so the block turns in place instead of
            # swinging across the page as the rotation changes.
            canvas.translate(x, y)
            canvas.rotate(rotation)
            canvas.translate(-x, -y)

        for index, line in enumerate(lines):
            canvas.drawString(x, y + box_height - line_height * (index + 1), line)

    apply_overlay(reader, indexes, draw, output)
    return _suffix(source, "stamped")


# ---------------------------------------------------------------------------
# Add Image
# ---------------------------------------------------------------------------

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def add_image(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Place an uploaded image on the chosen pages.

    Both files arrive through the same form field, so the PDF and the image are
    told apart by suffix rather than by position in the list.

    The image is scaled to a percentage of the page width and keeps its aspect
    ratio. An image taller than the area inside the margins is scaled down to fit,
    because a logo that runs off the bottom of the page is never what was wanted.
    """
    source, logo = _one_pdf_and_image(inputs)
    reader = _open(source)
    indexes = _pages(reader, params)

    scale = number(params, "width", 25, 1, 100, "image width")
    position = pick(params, "position", POSITIONS, "top-right")
    margin = number(params, "margin", DEFAULT_MARGIN, 0, 200, "margin")
    alpha = opacity(params, "opacity", 1.0)

    from reportlab.lib.utils import ImageReader

    picture = ImageReader(str(logo))

    def draw(canvas, width, height, _page_number):
        draw_width = width * scale / 100.0
        ratio = picture.getSize()[1] / picture.getSize()[0]
        draw_height = draw_width * ratio
        if draw_height > height - 2 * margin:
            # Too tall at the requested width, so back off on width instead.
            draw_height = max(0.0, height - 2 * margin)
            draw_width = draw_height / ratio if ratio else draw_width
        x, y = anchor(position, margin, width, height, draw_width, draw_height)

        if alpha < 1.0:
            canvas.saveState()
            canvas.setFillAlpha(alpha)
        # mask="auto" uses a PNG's own alpha channel; a JPEG simply has none.
        canvas.drawImage(picture, x, y, draw_width, draw_height, mask="auto")
        if alpha < 1.0:
            canvas.restoreState()

    apply_overlay(reader, indexes, draw, output)
    return _suffix(source, "with-image")


def _one_pdf_and_image(inputs: Sequence[Path]) -> tuple:
    """Exactly one PDF and one image from a single upload field."""
    pdfs = [p for p in inputs if p.suffix.lower() == ".pdf"]
    images = [p for p in inputs if p.suffix.lower() in IMAGE_SUFFIXES]

    if len(pdfs) != 1:
        raise ToolError("Choose exactly one PDF.")
    if not images:
        raise ToolError("Choose a PNG or JPEG image to place.")
    if len(images) > 1:
        raise ToolError("Place one image at a time.")
    return pdfs[0], images[0]


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------


def watermark(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Stamp repeated diagonal text across the chosen pages.

    Unlike Add Text this is centred and centred on the page proper, because that
    is what a watermark is: a fixed mark over the middle, not content in a corner.
    """
    source = one_input(inputs, "PDF")
    reader = _open(source)
    indexes = _pages(reader, params)

    content = field(params, "text", "watermark text")
    font_name = pick(params, "font", FONTS, "Helvetica-Bold")
    font = FONTS[font_name]
    size = number(params, "size", 56, 6, 300, "font size")
    fill = colour(params, "colour", (0.5, 0.5, 0.5))
    alpha = opacity(params, "opacity", 0.3)
    rotation = _rotation(params, "rotation", 45)

    from reportlab.pdfbase.pdfmetrics import stringWidth

    text_width = stringWidth(content, font, size)

    def draw(canvas, width, height, _page_number):
        canvas.saveState()
        canvas.setFillColorRGB(*fill)
        if alpha < 1.0:
            canvas.setFillAlpha(alpha)

        canvas.translate(width / 2.0, height / 2.0)
        canvas.rotate(rotation)
        # Centre on the glyphs, not the baseline, or it sits low once rotated.
        canvas.setFont(font, size)
        canvas.drawString(-text_width / 2.0, -size / 2.0, content)
        canvas.restoreState()

    apply_overlay(reader, indexes, draw, output)
    return _suffix(source, "watermarked")


# ---------------------------------------------------------------------------
# Edit Metadata
# ---------------------------------------------------------------------------

# (PDF dictionary key, form field name, label shown in the form)
META_FIELDS = [
    ("/Title", "title", "Title"),
    ("/Author", "author", "Author"),
    ("/Subject", "subject", "Subject"),
    ("/Keywords", "keywords", "Keywords"),
    ("/Creator", "creator", "Creator"),
    ("/Producer", "producer", "Producer"),
]


def metadata(inputs: Sequence[Path], params: dict, output: Path) -> str:
    """Set document information fields.

    A blank field means *leave it alone* rather than *clear it*, so submitting the
    form with one box filled cannot silently wipe the rest of the document's
    metadata. That also means this tool cannot blank a field — it can only add or
    change one.
    """
    source = one_input(inputs, "PDF")
    reader = _open(source)

    updates = {
        key: params[name].strip()
        for key, name, _ in META_FIELDS
        if params.get(name, "").strip()
    }

    if not updates:
        raise ToolError(
            "Fill in at least one field. Blank fields are left as they are, so "
            "there is nothing to change."
        )

    writer = _clone(source, reader)
    existing = dict(writer.metadata or {})
    existing.update(updates)
    writer.add_metadata({k: v for k, v in existing.items() if v})

    _write(writer, output)
    return _suffix(source, "metadata")


def _clone(source: Path, reader: PdfReader):
    """A writer carrying every page, plus the original AcroForm if there is one.

    Building a writer page by page drops the form dictionary, and several tools
    fail on the missing ``/AcroForm`` afterwards. Cloning keeps the document
    structure intact so editing metadata cannot break a form.
    """
    from pypdf import PdfWriter

    writer = PdfWriter()
    try:
        writer.clone_document_from_reader(reader)
    except Exception as exc:  # noqa: BLE001 - fall back, the raise below reports it
        raise ToolError(f"{source.name} could not be copied ({exc}).") from exc
    return writer
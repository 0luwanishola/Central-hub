"""Sign PDF: place a drawn or uploaded signature onto a chosen page.

This tool does not follow the one-request pattern the other PDF tools use, because
placement needs feedback the user has to see before they can decide:

1. ``POST /api/pdf/pdf-sign/preview`` takes the PDF, keeps it as a draft and returns
   a rendered page image plus the page count.
2. ``GET /api/pdf/pdf-sign/preview/{token}`` re-renders a different page.
3. ``POST /api/pdf/pdf-sign/apply`` takes the draft token, the signature image and
   the click position, and produces the signed PDF.

Keeping the PDF as a draft between those requests is why the flow is worth three
round trips: otherwise the file goes over the wire a second time to sign it.

**Placement is sent as a fraction of the page, not as points.** The browser
records where the user clicked as a fraction across and down the preview image,
which is independent of the image's pixel size, the browser zoom and the display
scale. The server multiplies by the real page size, so a signature placed on a
phone lands in the same spot on the page as one placed on a desktop.
"""

from __future__ import annotations

import base64
import binascii
import io
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .core import ToolError
from .organise import _open

# Render scale for the preview. 2 is enough to aim by and keeps the PNG small
# enough to send on a phone.
PREVIEW_SCALE = 2.0

# An upper bound on the decoded signature. A drawn signature is a few KB; this only
# exists so a hand-crafted data URL cannot exhaust memory.
MAX_SIGNATURE_BYTES = 4 * 1024 * 1024

_DATA_URL = re.compile(r"^data:image/(png|jpeg|jpg);base64,(.+)$", re.DOTALL)


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def describe_page(path: Path, page_number: int) -> dict:
    """Everything the browser needs to turn a click into PDF coordinates.

    Returns the page size in points, the rendered size in pixels and the page
    count. The click is later turned into a fraction, so the pixel size is only
    used to keep the preview's aspect ratio honest in the markup.
    """
    import pypdfium2 as pdfium

    reader = _open(path)
    total = len(reader.pages)

    if not 1 <= page_number <= total:
        raise ToolError(f"Page {page_number} does not exist; the document has {total}.")

    page = reader.pages[page_number - 1]
    if page.rotation:
        # Placement maths below works in the page's unrotated user space. A rotated
        # page would put the signature somewhere the user did not click, and
        # silently correcting for it is worse than saying so.
        raise ToolError(
            f"Page {page_number} is rotated. Use Organise Pages to remove the "
            "rotation, then sign it."
        )

    width = float(page.mediabox.width)
    height = float(page.mediabox.height)

    document = pdfium.PdfDocument(str(path))
    try:
        rendered = document[page_number - 1].render(scale=PREVIEW_SCALE)
        image = rendered.to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    finally:
        document.close()

    return {
        "png": buffer.getvalue(),
        "page": page_number,
        "pages": total,
        # PDF user-space units, origin at the bottom-left of the page.
        "width_pt": width,
        "height_pt": height,
        "pixel_width": image.width,
        "pixel_height": image.height,
    }


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def decode_signature(data_url: str) -> bytes:
    """Decode the data URL the browser produced from the canvas or an upload."""
    match = _DATA_URL.match((data_url or "").strip())
    if not match:
        raise ToolError(
            "Add a signature first: draw one on the pad or upload an image of it."
        )

    payload = match.group(2)
    if len(payload) > MAX_SIGNATURE_BYTES * 4 // 3:
        raise ToolError("That signature image is too large. Try a smaller one.")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ToolError("The signature image could not be read.") from exc

    if not raw:
        raise ToolError("The signature image is empty. Draw or upload one again.")
    return raw


def signature_image(data_url: str) -> Image.Image:
    """The decoded signature, cropped to its non-transparent pixels.

    A canvas pad and a phone photo both carry a border of empty space. Placing that
    empty space as if it were ink makes the signature appear to float away from
    the click point, so the transparent margin is trimmed first.
    """
    raw = decode_signature(data_url)

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ToolError("That file is not a usable PNG or JPEG image.") from exc

    if image.mode not in ("RGBA", "LA", "RGB"):
        image = image.convert("RGBA")

    alpha = image.convert("RGBA").getchannel("A")
    box = alpha.getbbox()
    if not box:
        # Fully transparent: there is nothing to stamp.
        raise ToolError("That signature image is blank. Draw or upload one again.")

    trimmed = image.convert("RGBA").crop(box)
    return trimmed


def _fraction(raw: str, label: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"No position chosen yet — click the page where the signature goes.") from exc
    if not 0.0 <= value <= 1.0:
        raise ToolError(f"{label} is outside the page.")
    return value


def apply_signature(
    source: Path,
    data_url: str,
    page_number: int,
    across: str,
    down: str,
    width_percent: str,
    output: Path,
) -> str:
    """Stamp the signature onto one page at the clicked position.

    The click sets the signature's **top-left corner**, which is what people mean
    when they point at a spot on a page. Width is a percentage of the page, and
    the height follows from the image's own aspect ratio.

    The signature is scaled to fit inside the page if a large width would push it
    over the bottom edge, so it always lands fully on the paper.
    """
    image = signature_image(data_url)

    reader = _open(source)
    total = len(reader.pages)
    try:
        page = int(page_number)
    except (TypeError, ValueError) as exc:
        raise ToolError(f"Page '{page_number}' is not a number.") from exc

    if not 1 <= page <= total:
        raise ToolError(f"Page {page} does not exist; the document has {total}.")

    target = reader.pages[page - 1]
    if target.rotation:
        raise ToolError(
            f"Page {page} is rotated. Use Organise Pages to remove the rotation, "
            "then sign it."
        )

    page_width = float(target.mediabox.width)
    page_height = float(target.mediabox.height)

    x_fraction = _fraction(across, "That position")
    y_fraction = _fraction(down, "That position")

    try:
        width_share = float(width_percent) / 100.0
    except (TypeError, ValueError) as exc:
        raise ToolError(f"Width '{width_percent}' is not a number.") from exc
    if not 0.01 <= width_share <= 1.0:
        raise ToolError("Signature width must be between 1 and 100 percent.")

    draw_width = page_width * width_share
    ratio = image.height / image.width if image.width else 1.0
    draw_height = draw_width * ratio

    if draw_height > page_height:
        draw_height = page_height
        draw_width = draw_height / ratio if ratio else draw_width

    # The click is the top-left corner, measured downwards from the top of the
    # page; PDF user space measures upwards from the bottom, hence the flip.
    x = x_fraction * page_width
    y_from_top = y_fraction * page_height
    y = page_height - y_from_top - draw_height
    # Keep the whole stamp on the paper even if the click was near an edge.
    x = max(0.0, min(x, page_width - draw_width))
    y = max(0.0, min(y, page_height - draw_height))

    from reportlab.lib.utils import ImageReader
    from pypdf import PdfWriter

    from .overlay import overlay_page

    layer = overlay_page(
        page_width,
        page_height,
        lambda canvas, w, h: canvas.drawImage(
            ImageReader(image), x, y, draw_width, draw_height, mask="auto"
        ),
    )
    target.merge_page(layer.pages[0])

    writer = PdfWriter()
    writer.add_page(target)
    output.unlink(missing_ok=True)
    with output.open("wb") as handle:
        writer.write(handle)

    return f"{Path(source).stem or 'document'}-signed.pdf"
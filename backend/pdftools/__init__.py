"""PDF tools for Central Hub.

Each tool is described in the main ``TOOLS`` catalog in ``backend/main.py`` and
implemented here. The two are joined by tool id: ``HANDLERS`` maps an id to the
function that does the work, and a tool with no entry here shows the standard
"coming soon" placeholder instead of failing.

Adding a tool is three steps:

1. Add the entry to ``TOOLS`` in ``backend/main.py`` so it appears in the catalog.
2. Write a ``run(inputs, params, output) -> str`` function in a module here. It
   receives the uploaded files already written to disk as ``Path`` objects, the
   form fields as a plain dict, and the path to write the result to; it returns
   the filename to download it under. Raise ``ToolError`` for anything the user
   can fix.
3. Register it in ``HANDLERS`` below.
4. Write the tool's page markup as a fragment under
   ``backend/templates/pdf/``, named after the tool id.

A tool whose work needs more than one request is not registered here at all; it
gets bespoke routes in ``main.py`` and is listed in ``PDF_CUSTOM_ROUTES``.
"""

from . import edit, organise, sign
from .core import (
    MAX_UPLOAD_BYTES,
    RESULTS_TTL,
    ToolError,
    cleanup_stale,
    download_response,
    error_response,
    find_draft,
    find_result,
    new_workspace,
    put_draft,
    remove_tree,
    save_uploads,
    store_draft,
    store_result,
    take_draft,
    take_result,
)

# Tool id -> (module function, accepted upload suffixes)
#
# Suffixes are listed per tool because the image tools accept PNG and JPEG while
# everything else is PDF-only.
HANDLERS = {
    "pdf-merge": (organise.merge, (".pdf",)),
    "pdf-split": (organise.split, (".pdf",)),
    "pdf-page-organiser": (organise.organise, (".pdf",)),
    "pdf-add-text": (edit.add_text, (".pdf",)),
    "pdf-add-image": (edit.add_image, (".pdf", ".png", ".jpg", ".jpeg")),
    "pdf-watermark": (edit.watermark, (".pdf",)),
    "pdf-metadata": (edit.metadata, (".pdf",)),
}

__all__ = [
    "HANDLERS",
    "MAX_UPLOAD_BYTES",
    "RESULTS_TTL",
    "ToolError",
    "cleanup_stale",
    "download_response",
    "edit",
    "error_response",
    "find_draft",
    "find_result",
    "new_workspace",
    "organise",
    "put_draft",
    "remove_tree",
    "save_uploads",
    "sign",
    "store_draft",
    "store_result",
    "take_draft",
    "take_result",
]

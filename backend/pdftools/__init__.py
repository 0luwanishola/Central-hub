"""PDF transformations and shared upload/result helpers for the React app."""

from . import edit, organise, sign
from .core import (
    MAX_UPLOAD_BYTES,
    RESULTS_TTL,
    ToolError,
    cleanup_stale,
    download_response,
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

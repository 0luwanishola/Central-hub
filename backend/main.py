import asyncio
import base64
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

if __package__:
    # Support ``python -m backend.main`` from the project root.
    from . import pdftools
    from . import learning
    from .providers import (
        DOMESTIC,
        INTERNATIONAL,
        NotFound,
        ProviderError,
        active_provider,
        clock_label,
        clean_scope,
        has_score,
        is_live,
        kickoff_label,
        provider_for,
    )
else:
    # Also support ``python main.py`` / ``uvicorn main:app`` from backend/.
    import pdftools
    import learning
    from providers import (
        DOMESTIC,
        INTERNATIONAL,
        NotFound,
        ProviderError,
        active_provider,
        clock_label,
        clean_scope,
        has_score,
        is_live,
        kickoff_label,
        provider_for,
    )

# Shown in the UI so it is obvious which source a result came from.
PROVIDER_LABELS = {
    "espn": "ESPN",
    "apifootball": "API-Football",
}


class RequestBodyTooLarge(Exception):
    """Raised before an oversized request body is handed to a form parser."""


class RequestBodyLimitMiddleware:
    """Count incoming request bytes before multipart uploads can be spooled."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        raw_length = headers.get(b"content-length")
        try:
            declared_length = int(raw_length) if raw_length else None
        except ValueError:
            declared_length = None

        received = 0

        async def limited_receive():
            nonlocal received
            if declared_length is not None and declared_length > self.max_bytes:
                raise RequestBodyTooLarge()
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLarge()
            return message

        await self.app(scope, limited_receive, send)


def provider_name(provider) -> str:
    return PROVIDER_LABELS.get(getattr(provider, "PREFIX", ""), "the provider")


def resolve_day(day: Optional[str]) -> str:
    """The requested day as ``YYYY-MM-DD``, falling back to today.

    ``day`` arrives from the query string and is interpolated into a provider URL,
    so it is parsed rather than passed through.
    """
    if day:
        try:
            return date.fromisoformat(day).isoformat()
        except ValueError:
            pass
    return date.today().isoformat()


def shift_day(iso_day: str, days: int) -> str:
    """The day ``days`` before/after ``iso_day``, for the date stepper."""
    return (date.fromisoformat(iso_day) + timedelta(days=days)).isoformat()


# Section headings for the two coverage groups, in display order.
GROUP_LABELS = ((DOMESTIC, "Domestic leagues"), (INTERNATIONAL, "International"))


def group_matches(matches: list, scope: str) -> list:
    """Split matches into display sections.

    With ``scope=all`` the two coverage groups get their own headings, which is what
    distinguishes national-team fixtures from league fixtures at a glance. Under a
    single scope the filter already says it, so the matches stay flat.
    """
    if scope != "all":
        return [(None, matches)]
    return [
        (label, [m for m in matches if m.get("group") == group])
        for group, label in GROUP_LABELS
        if any(m.get("group") == group for m in matches)
    ]

BASE_DIR = Path(__file__).parent

# Provider credentials live in backend/.env, never in the repo or the browser.
load_dotenv(BASE_DIR / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """One shared HTTP client for outbound provider calls."""
    learning.initialize_learning_store()
    app.state.http = httpx.AsyncClient(timeout=15.0)
    async def expire_pdf_files():
        while True:
            await asyncio.sleep(60)
            pdftools.cleanup_stale()

    cleanup_task = asyncio.create_task(expire_pdf_files())
    try:
        yield
    finally:
        cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
        await app.state.http.aclose()


app = FastAPI(title="Central Hub", lifespan=lifespan)


class LearningSessionRequest(BaseModel):
    learner_id: Optional[str] = None


class LearningAnswerRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)
    track: str = Field(min_length=1, max_length=20)
    level: int = Field(ge=0, le=10)
    choice: int = Field(ge=0, le=2)


class LearningCodeRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)
    track: str = Field(min_length=1, max_length=20)
    level: int = Field(ge=0, le=10)
    code: str = Field(max_length=5_000)

# The standalone Vite app uses a separate origin during development. Keep these
# origins explicit; production origins belong in deployment configuration.
frontend_origins = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
)
# The form parser spools uploaded files before the PDF layer can enforce its
# per-file budget. Limit the complete request body first, with room for form fields.
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_bytes=pdftools.MAX_UPLOAD_BYTES + 1024 * 1024,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in frontend_origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Created on startup so the mount below cannot fail when the directory is absent
# from a fresh checkout (it holds no assets yet, so it is not always tracked).
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Tool registry - add your utilities here
#
# PDF entries carry two optional keys:
#   "ready"    - True when the tool has an implementation in backend/pdftools/.
#   "requires" - an external program or credential the tool cannot work without.
#                Only set this on tools that are deliberately deferred, so the
#                placeholder can say why it is not available.
TOOLS = [
    {"id": "json-formatter", "name": "JSON Formatter", "description": "Format, validate, and minify JSON", "icon": "📝", "category": "data"},
    {"id": "base64-encoder", "name": "Base64 Encoder/Decoder", "description": "Encode/decode Base64 strings", "icon": "🔐", "category": "encoding"},
    {"id": "hash-generator", "name": "Hash Generator", "description": "Generate MD5, SHA1, SHA256 hashes", "icon": "🔑", "category": "crypto"},
    {"id": "uuid-generator", "name": "UUID Generator", "description": "Generate v1, v4, v7 UUIDs", "icon": "🆔", "category": "generators"},
    {"id": "timestamp-converter", "name": "Timestamp Converter", "description": "Convert between Unix time and human dates", "icon": "⏰", "category": "time"},
    {"id": "regex-tester", "name": "Regex Tester", "description": "Test and debug regular expressions", "icon": "🔍", "category": "text"},
    {"id": "color-picker", "name": "Color Picker", "description": "Pick and convert colors (HEX, RGB, HSL)", "icon": "🎨", "category": "design"},
    {"id": "qr-generator", "name": "QR Code Generator", "description": "Generate QR codes from text/URLs", "icon": "📱", "category": "generators"},
    {"id": "live-score", "name": "LiveScore", "description": "Live football scores with scorers, assists and lineups", "icon": "⚽", "category": "sports", "ready": True},

    # --- PDFs ---------------------------------------------------------------
    # The category grid is built from this catalog, including PDF tools.
    # --- organise -----------------------------------------------------------
    {"id": "pdf-merge", "name": "Merge PDFs", "description": "Combine several PDFs into one, in order", "icon": "📎", "category": "pdf", "ready": True},
    {"id": "pdf-split", "name": "Split PDF", "description": "Pull pages out into separate PDFs, zipped", "icon": "✂️", "category": "pdf", "ready": True},
    {"id": "pdf-page-organiser", "name": "Organise Pages", "description": "Reorder, rotate and delete pages", "icon": "🔀", "category": "pdf", "ready": True},
    {"id": "pdf-page-numbers", "name": "Add Page Numbers", "description": "Stamp page numbers in a chosen position", "icon": "🔢", "category": "pdf"},

    # --- convert -------------------------------------------------------------
    {"id": "pdf-to-images", "name": "PDF to Images", "description": "Render pages to PNG or JPEG", "icon": "🖼", "category": "pdf"},
    {"id": "images-to-pdf", "name": "Images to PDF", "description": "Turn PNG or JPEG files into a PDF", "icon": "📸", "category": "pdf"},
    {"id": "pdf-to-text", "name": "Extract PDF Text", "description": "Pull the text out to a plain file", "icon": "📄", "category": "pdf"},
    {"id": "pdf-to-word", "name": "PDF to Word", "description": "Convert to an editable .docx", "icon": "📝", "category": "pdf", "requires": "LibreOffice"},
    {"id": "pdf-to-excel", "name": "PDF to Excel", "description": "Convert tables to .xlsx", "icon": "📊", "category": "pdf", "requires": "LibreOffice"},
    {"id": "word-to-pdf", "name": "Word to PDF", "description": "Convert .docx and .odt to PDF", "icon": "📄", "category": "pdf", "requires": "LibreOffice"},
    {"id": "pdf-ocr", "name": "OCR Scanned PDF", "description": "Make a scanned PDF searchable", "icon": "👁", "category": "pdf", "requires": "Tesseract"},

    # --- edit ----------------------------------------------------------------
    {"id": "pdf-add-text", "name": "Add Text", "description": "Stamp text onto a page", "icon": "🅰", "category": "pdf"},
    {"id": "pdf-add-image", "name": "Add Image or Logo", "description": "Place an image on a page", "icon": "🖼", "category": "pdf"},
    {"id": "pdf-watermark", "name": "Add Watermark", "description": "Overlay diagonal text across pages", "icon": "💧", "category": "pdf"},
    {"id": "pdf-annotate", "name": "Highlight and Annotate", "description": "Mark up text and add notes", "icon": "🖊", "category": "pdf"},
    {"id": "pdf-redact", "name": "Redact Text", "description": "Black out text permanently", "icon": "⬛", "category": "pdf"},
    {"id": "pdf-fill-forms", "name": "Fill PDF Forms", "description": "Complete AcroForm fields", "icon": "📋", "category": "pdf"},
    {"id": "pdf-metadata", "name": "Edit PDF Metadata", "description": "View or change title, author and subject", "icon": "🏷", "category": "pdf"},

    # --- sign ----------------------------------------------------------------
    {"id": "pdf-sign", "name": "Sign PDF", "description": "Draw, type or upload a signature", "icon": "✍", "category": "pdf"},
    {"id": "pdf-request-signatures", "name": "Request Signatures", "description": "Prepare a document for others to sign", "icon": "📨", "category": "pdf"},
    {"id": "pdf-certificate-sign", "name": "Digital Signature", "description": "Cryptographically sign with a certificate", "icon": "🛡", "category": "pdf", "requires": "a certificate or signing service"},
    {"id": "pdf-verify-signature", "name": "Verify Signatures", "description": "Check whether a signature is intact", "icon": "🔏", "category": "pdf", "requires": "a certificate or signing service"},

    # --- optimise ------------------------------------------------------------
    {"id": "pdf-compress", "name": "Compress PDF", "description": "Shrink file size without ghostscript", "icon": "🗜", "category": "pdf"},
    {"id": "pdf-compress-small", "name": "Compress PDF (Small)", "description": "Aggressive compression via Ghostscript", "icon": "📉", "category": "pdf", "requires": "Ghostscript"},
    {"id": "pdf-repair", "name": "Repair PDF", "description": "Rebuild a damaged or unreadable file", "icon": "🛠", "category": "pdf"},

    # --- secure --------------------------------------------------------------
    {"id": "pdf-protect", "name": "Encrypt PDF", "description": "Add a password and set permissions", "icon": "🔒", "category": "pdf"},
    {"id": "pdf-unlock", "name": "Remove PDF Password", "description": "Strip an open password you know", "icon": "🔓", "category": "pdf"},

    # --- compare -------------------------------------------------------------
    {"id": "pdf-compare", "name": "Compare PDFs", "description": "Show what changed between two versions", "icon": "🔍", "category": "pdf"},
]

CATEGORIES = sorted(set(t["category"] for t in TOOLS))

# Lightweight utilities run in the browser. Provider backed and PDF tools stay
# on the API, with the catalog carrying the execution mode for the frontend.
CLIENT_TOOL_IDS = {
    "json-formatter",
    "base64-encoder",
    "hash-generator",
    "uuid-generator",
    "timestamp-converter",
    "regex-tester",
    "color-picker",
    "qr-generator",
}
for _tool in TOOLS:
    if _tool["id"] in CLIENT_TOOL_IDS:
        _tool["execution"] = "client"
        _tool["ready"] = True
    elif _tool["id"] == "live-score" or _tool["id"] in pdftools.HANDLERS:
        _tool["execution"] = "api"
        _tool["ready"] = True
    else:
        _tool.setdefault("ready", False)
        _tool["execution"] = "unavailable"

# Category key used by the legacy /pdf compatibility redirect.
PDF_CATEGORY = "pdf"

# PDF tools that have a real page, mapped to the file types the browser should
# offer in the picker. A tool id in here means backend/templates/pdf/<id>.html
# exists, and /tool/{tool_id} serves it instead of the shared placeholder.
PDF_PAGES = {
    "pdf-merge": ".pdf,application/pdf",
    "pdf-split": ".pdf,application/pdf",
    "pdf-page-organiser": ".pdf,application/pdf",
    "pdf-add-text": ".pdf,application/pdf",
    "pdf-add-image": ".pdf,application/pdf,.png,.jpg,.jpeg",
    "pdf-watermark": ".pdf,application/pdf",
    "pdf-metadata": ".pdf,application/pdf",
    "pdf-sign": ".pdf,application/pdf",
}

CATEGORY_ICONS = {
    "crypto": "🔑",
    "data": "🗂",
    "design": "🎨",
    "encoding": "🔐",
    "generators": "✨",
    "pdf": "📄",
    "sports": "⚽",
    "text": "🔍",
    "time": "⏰",
}


def get_category_icon(category: str) -> str:
    """Icon for a category, used by the sidebar in the page templates."""
    return CATEGORY_ICONS.get(category, "🧰")


def category_url(category: str) -> str:
    """Build the dashboard URL for any catalog category."""
    return f"/?category={category}"


templates.env.globals["category_url"] = category_url
templates.env.globals["get_category_icon"] = get_category_icon
templates.env.globals["clock_label"] = clock_label
templates.env.globals["has_score"] = has_score
templates.env.globals["kickoff_label"] = kickoff_label


def filter_by_category(category: Optional[str]) -> list:
    if not category or category == "all":
        return TOOLS
    return [t for t in TOOLS if t["category"] == category]


def count_ready(tools: list) -> int:
    return sum(1 for t in tools if t.get("ready"))


def _form_int(form, key: str, default: int) -> int:
    """An integer form field, falling back when it is blank or not a number.

    A page number arriving as an empty string should not become a 500. The field is
    a number input the user can clear, and a cleared field means "as asked for".
    """
    raw = str(form.get(key) or "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def render(request: Request, page: str, content: str, context: dict):
    """Serve a full page normally, but only the swappable fragment to htmx.

    htmx sets HX-Request on every request it makes. Returning the whole
    document for those would let it inject a second copy of the layout into
    #main-content, so those requests get the content fragment instead.
    """
    if request.headers.get("hx-request") == "true":
        return templates.TemplateResponse(request, content, context)
    return templates.TemplateResponse(request, page, context)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, category: Optional[str] = None):
    active = category or "all"
    tools = filter_by_category(active)
    return render(
        request,
        page="dashboard.html",
        content="dashboard_content.html",
        context={
            "tools": tools,
            "ready_count": count_ready(tools),
            # Full catalog is kept separate so the sidebar can still show the
            # per-category totals while a filter is applied.
            "all_tools": TOOLS,
            "categories": CATEGORIES,
            "category": active,
            "current_category": active,
        },
    )


@app.get("/pdf", response_class=HTMLResponse)
async def legacy_pdf_hub():
    """Keep old bookmarks working while showing PDF in the regular category grid."""
    return RedirectResponse(f"/?category={PDF_CATEGORY}", status_code=303)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    context = {
        "categories": CATEGORIES,
        "all_tools": TOOLS,
        "current_category": "settings",
    }
    return render(
        request,
        page="settings.html",
        content="settings_content.html",
        context=context,
    )

@app.get("/tool/live-score", response_class=HTMLResponse)
async def live_score_page(
    request: Request, day: Optional[str] = None, scope: Optional[str] = None
):
    """LiveScore board. Provider failures are shown in the page, not raised.

    ``day`` selects which day's fixtures to show and ``scope`` narrows to the
    domestic or international competitions, so past and upcoming matches are both
    reachable from the page itself rather than only by editing the URL.

    NOTE: this route must stay ABOVE /tool/{tool_id}. Starlette matches routes in
    declaration order, so the catch-all would otherwise claim "live-score" and
    render the generic placeholder page.
    """
    matches: list = []
    error: Optional[str] = None
    provider = active_provider()
    day = resolve_day(day)
    scope = clean_scope(scope)

    try:
        matches = await provider.fixtures_for_day(request.app.state.http, day, scope)
    except ProviderError as exc:
        error = str(exc)

    sections = group_matches(matches, scope)

    return render(
        request,
        page="live_score.html",
        content="live_score_content.html",
        context={
            "matches": matches,
            "sections": sections,
            "grouped": scope == "all",
            "error": error,
            "day": day,
            "today": date.today().isoformat(),
            "prev_day": shift_day(day, -1),
            "next_day": shift_day(day, 1),
            "scope": scope,
            "live_count": sum(1 for m in matches if is_live(m)),
            "provider": provider_name(provider),
            "categories": CATEGORIES,
            "all_tools": TOOLS,
            "current_category": "sports",
        },
    )


@app.get("/match/{fixture_id}", response_class=HTMLResponse)
async def match_page(request: Request, fixture_id: str):
    """Match detail: scoreline, event timeline and lineups.

    The id carries its provider prefix, so this resolves the right module rather
    than whichever provider happens to be configured.
    """
    error: Optional[str] = None
    match: Optional[dict] = None
    provider = provider_for(fixture_id)

    try:
        match = await provider.match_detail(request.app.state.http, fixture_id)
    except NotFound:
        return HTMLResponse("Match not found", status_code=404)
    except ProviderError as exc:
        error = str(exc)

    return render(
        request,
        page="match.html",
        content="match_content.html",
        context={
            "match": match,
            "fixture_id": fixture_id,
            "error": error,
            "provider": provider_name(provider),
            "categories": CATEGORIES,
            "all_tools": TOOLS,
            # A match belongs to no category, so no sidebar entry is highlighted.
            "current_category": None,
        },
    )


# NOTE: keep this catch-all BELOW any specific /tool/<name> route. Starlette
# matches routes in declaration order, so a specific route declared after this
# one would never be reached.
@app.get("/tool/{tool_id}", response_class=HTMLResponse)
async def tool_page(request: Request, tool_id: str):
    tool = next((t for t in TOOLS if t["id"] == tool_id), None)
    if not tool:
        return HTMLResponse("Tool not found", status_code=404)

    # A PDF tool gets its own fragment listing exactly which files and options it
    # needs; everything else falls through to the shared placeholder.
    content = f"pdf/{tool_id}.html" if tool_id in PDF_PAGES else "tool_content.html"
    return render(
        request,
        page="tool.html",
        content=content,
        context={
            "tool": tool,
            "categories": CATEGORIES,
            "all_tools": TOOLS,
            "accept": PDF_PAGES.get(tool_id),
            "multiple": tool_id == "pdf-merge",
            "current_category": tool["category"],
        },
    )


@app.get("/api/tools")
async def api_tools(category: Optional[str] = None):
    # Keep the legacy Jinja catalog's old readiness badges compatible while the
    # standalone app receives availability based on its browser/API handlers.
    response = []
    for tool in filter_by_category(category):
        public_tool = dict(tool)
        public_tool["ready"] = public_tool["execution"] in {"client", "api"}
        response.append(public_tool)
    return response


@app.post("/api/learning/session")
def api_learning_session(payload: LearningSessionRequest):
    """Resume or create an anonymous learning profile for this browser."""
    return learning.create_or_restore_session(payload.learner_id)


@app.post("/api/learning/answer")
def api_learning_answer(payload: LearningAnswerRequest):
    """Check one Code Quest answer and persist first-time completions."""
    try:
        return learning.submit_answer(payload.learner_id, payload.track, payload.level, payload.choice)
    except learning.LearningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/api/learning/code")
def api_learning_code(payload: LearningCodeRequest):
    """Run a guided Code Quest solution in its restricted language runner."""
    try:
        return learning.submit_code(payload.learner_id, payload.track, payload.level, payload.code)
    except learning.LearningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/api/live")
async def api_live(day: Optional[str] = None, scope: Optional[str] = None):
    """Normalised scoreboard as JSON, same shape the page renders."""
    provider = active_provider()
    day = resolve_day(day)
    scope = clean_scope(scope)
    try:
        matches = await provider.fixtures_for_day(app.state.http, day, scope)
    except ProviderError as exc:
        return {
            "provider": provider_name(provider),
            "day": day,
            "scope": scope,
            "error": str(exc),
            "matches": [],
        }
    return {
        "provider": provider_name(provider),
        "day": day,
        "scope": scope,
        "matches": matches,
    }


@app.get("/api/match/{fixture_id}")
async def api_match(fixture_id: str):
    """Match detail as JSON: scoreline, events and lineups."""
    provider = provider_for(fixture_id)
    try:
        return await provider.match_detail(app.state.http, fixture_id)
    except NotFound:
        return JSONResponse({"error": "Match not found"}, status_code=404)
    except ProviderError as exc:
        return {"provider": provider_name(provider), "error": str(exc)}


# --------------------------------------------------------------------------
# PDF tools
# --------------------------------------------------------------------------

def _pdf_wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "").lower()


def _pdf_error(request: Request, message: str, status_code: int = 400):
    if _pdf_wants_json(request):
        return JSONResponse({"detail": message}, status_code=status_code)
    response = pdftools.error_response(message)
    response.status_code = status_code
    return response


@app.exception_handler(RequestBodyTooLarge)
async def request_body_too_large(request: Request, _exc: RequestBodyTooLarge):
    return _pdf_error(
        request,
        "That request is too large. The limit is 100 MB for files, plus up to 1 MB for form data.",
        status_code=413,
    )


def _pdf_result(request: Request, download_name: str, token: str):
    if _pdf_wants_json(request):
        return JSONResponse(
            {
                "download_url": f"/api/pdf/download/{token}",
                "filename": download_name,
                "expires_in_seconds": pdftools.RESULTS_TTL,
            }
        )
    return templates.TemplateResponse(
        request, "pdf/result.html", {"download_name": download_name, "token": token}
    )

# Tools with bespoke routes instead of one run(inputs, params, output) handler.
#
# Signing needs three requests -- preview the page, page through to the right one,
# then apply -- so it cannot fit the single-request shape the generic route below
# assumes. Listing it here keeps the check that every tool id in PDF_PAGES has
# somewhere to go.
PDF_CUSTOM_ROUTES = {"pdf-sign"}

# Every tool with a page must have somewhere for its form to POST. A pdf/ fragment
# that posts to a handler that does not exist only fails once someone uses it.
assert PDF_PAGES.keys() <= (pdftools.HANDLERS.keys() | PDF_CUSTOM_ROUTES), (
    "PDF_PAGES entries with no handler: "
    f"{sorted(PDF_PAGES.keys() - pdftools.HANDLERS.keys() - PDF_CUSTOM_ROUTES)}"
)

# The download route is declared first so "download" can never be read as a tool id.
@app.get("/api/pdf/download/{token}")
async def download_pdf_result(request: Request, token: str):
    """Serve a finished PDF, once. The token is consumed by this request."""
    result = pdftools.take_result(token)
    if result is None:
        if _pdf_wants_json(request):
            return JSONResponse(
                {"detail": "That download has expired or was already used."},
                status_code=404,
            )
        return HTMLResponse(
            "That download has expired or was already used. Run the tool again.",
            status_code=404,
        )
    return pdftools.download_response(result)


# The three signing routes are declared above POST /api/pdf/{tool_id} for clarity.
# They do not actually collide with it: each has two path segments after /api/pdf,
# where the generic route has one.

@app.post("/api/pdf/pdf-sign/preview", response_class=HTMLResponse)
async def pdf_sign_preview(request: Request):
    """Keep the uploaded PDF as a draft and return a rendered page to aim at.

    This does not stream a PNG back on its own because the response also carries
    the whole placement form. The image is inlined as a data URL, which keeps the
    fragment self-contained: htmx can swap it in without a second request, and the
    form it brings along already knows the page count and page size.
    """
    form = await request.form()
    uploads = [v for v in form.getlist("files") if isinstance(v, UploadFile)]

    workspace = pdftools.new_workspace()
    try:
        saved = await pdftools.save_uploads(uploads, workspace, (".pdf",))
        page = _form_int(form, "page", 1)

        described = await run_in_threadpool(pdftools.sign.describe_page, saved[0], page)

        # The draft owns its tree from here; nothing else may delete it.
        token = pdftools.store_draft(saved[0], saved[0].name)

        return templates.TemplateResponse(
            request,
            "pdf/signature_preview.html",
            {
                "token": token,
                "page": described["page"],
                "pages": described["pages"],
                "image": base64.b64encode(described["png"]).decode("ascii"),
                "width_pt": round(described["width_pt"], 1),
                "height_pt": round(described["height_pt"], 1),
            },
        )

    except pdftools.ToolError as exc:
        pdftools.remove_tree(workspace)
        return pdftools.error_response(str(exc))
    except Exception:
        pdftools.remove_tree(workspace)
        raise


@app.get("/api/pdf/pdf-sign/page/{token}", response_class=HTMLResponse)
async def pdf_sign_page(request: Request, token: str, page: Optional[int] = None):
    """Re-render a different page of a previewed PDF, as the same fragment."""
    draft = pdftools.find_draft(token)
    if draft is None:
        return pdftools.error_response("That preview has expired. Upload the PDF again.")

    try:
        described = await run_in_threadpool(
            pdftools.sign.describe_page, draft.path, page or 1
        )
    except pdftools.ToolError as exc:
        return pdftools.error_response(str(exc))

    return templates.TemplateResponse(
        request,
        "pdf/signature_preview.html",
        {
            "token": token,
            "page": described["page"],
            "pages": described["pages"],
            "image": base64.b64encode(described["png"]).decode("ascii"),
            "width_pt": round(described["width_pt"], 1),
            "height_pt": round(described["height_pt"], 1),
        },
    )


@app.post("/api/pdf/pdf-sign/apply", response_class=HTMLResponse)
async def pdf_sign_apply(request: Request):
    """Place the signature on the drafted PDF and return a download link."""
    form = await request.form()
    values = {k: v for k, v in form.multi_items() if isinstance(v, str)}

    token = values.get("draft", "")
    draft = pdftools.take_draft(token)
    if draft is None:
        pdftools.remove_tree(pdftools.new_workspace())
        return pdftools.error_response("That preview has expired. Upload the PDF again.")

    result_dir = pdftools.new_workspace()
    try:
        output = result_dir / "result"
        download_name = await run_in_threadpool(
            pdftools.sign.apply_signature,
            draft.path,
            values.get("signature", ""),
            values.get("page", "1"),
            values.get("across", ""),
            values.get("down", ""),
            values.get("width", "25"),
            output,
        )
        download_token = pdftools.store_result(output, download_name)

    except pdftools.ToolError as exc:
        # The draft is kept on failure so a mistyped width does not cost the user
        # their upload and preview.
        pdftools.put_draft(token, draft)
        pdftools.remove_tree(result_dir)
        return pdftools.error_response(str(exc))
    except Exception:
        pdftools.remove_tree(result_dir)
        raise

    # The draft's own tree belongs to it and was consumed on success.
    pdftools.remove_tree(draft.path.parent)
    return templates.TemplateResponse(
        request,
        "pdf/result.html",
        {"download_name": download_name, "token": download_token},
    )


@app.post("/api/pdf/{tool_id}", response_class=JSONResponse)
async def run_pdf_tool(tool_id: str, request: Request):
    """Process a PDF upload and return JSON or a legacy htmx fragment.

    The form is read by hand rather than through declared parameters: every tool
    wants a different set of fields, and one route that accepts whatever arrives
    is less code than a signature per tool.

    Standalone clients request JSON containing the download URL and filename.
    Existing htmx pages continue to receive a small HTML fragment.

    NOTE: these routes are POST-only and live under /api, so they cannot collide
    with the GET /tool/{tool_id} placeholder above.
    """
    entry = pdftools.HANDLERS.get(tool_id)
    if entry is None:
        return _pdf_error(request, "That PDF tool is not implemented yet.", 501)

    handler, suffixes = entry
    form = await request.form()

    # Split the multipart body: files go to disk, everything else is a string field.
    uploads = [v for v in form.getlist("files") if isinstance(v, UploadFile)]
    params = {k: v for k, v in form.multi_items() if isinstance(v, str)}

    # Two separate temp trees rather than one with subdirectories. Results outlive
    # the request, and the download route deletes only the tree it owns; nesting
    # them would leave the parent behind every time.
    inputs_dir = pdftools.new_workspace()
    result_dir = pdftools.new_workspace()

    try:
        saved = await pdftools.save_uploads(uploads, inputs_dir, suffixes)
        output = result_dir / "result"
        download_name = await run_in_threadpool(handler, saved, params, output)

        # A tool returns a name, so the extension drives the content type: the split
        # tool produces a ZIP, everything else a PDF.
        media_type = "application/zip" if download_name.endswith(".zip") else "application/pdf"
        token = pdftools.store_result(output, download_name, media_type)

    except pdftools.ToolError as exc:
        pdftools.remove_tree(inputs_dir)
        pdftools.remove_tree(result_dir)
        return _pdf_error(request, str(exc))
    except Exception:
        # Unexpected failure: never leave the upload behind on disk.
        pdftools.remove_tree(inputs_dir)
        pdftools.remove_tree(result_dir)
        raise

    # Inputs are no longer needed. The result tree now belongs to the store.
    pdftools.remove_tree(inputs_dir)
    return _pdf_result(request, download_name, token)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

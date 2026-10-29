import asyncio
import base64
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

if __package__:
    # Support ``python -m backend.main`` from the project root.
    from . import pdftools
    from . import learning
    from .scratch import limits as scratch_limits
    from .scratch import python_service as scratch_python
    from .scratch import sql_service as scratch_sql
    from .scratch import sql_workspaces as scratch_sql_workspaces
    from .scratch.errors import ScratchError
    from .providers import (
        DOMESTIC,
        INTERNATIONAL,
        NotFound,
        ProviderError,
        active_provider,
        clean_scope,
        is_live,
        provider_for,
    )
else:
    # Also support ``python main.py`` / ``uvicorn main:app`` from backend/.
    import pdftools
    import learning
    from scratch import limits as scratch_limits
    from scratch import python_service as scratch_python
    from scratch import sql_service as scratch_sql
    from scratch import sql_workspaces as scratch_sql_workspaces
    from scratch.errors import ScratchError
    from providers import (
        DOMESTIC,
        INTERNATIONAL,
        NotFound,
        ProviderError,
        active_provider,
        clean_scope,
        is_live,
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

# Provider credentials live in a local .env file, never in the repo or browser.
load_dotenv(BASE_DIR.parent / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """One shared HTTP client for outbound provider calls."""
    learning.initialize_learning_store()
    # SQL Scratch tokens are process-local, so files left by an earlier process
    # can never be valid again. Start from a clean server-owned root.
    scratch_sql_workspaces.initialize()
    app.state.http = httpx.AsyncClient(timeout=15.0)

    async def cleanup_temporary_files():
        while True:
            await asyncio.sleep(60)
            pdftools.cleanup_stale()
            scratch_sql_workspaces.cleanup_expired()

    cleanup_task = asyncio.create_task(cleanup_temporary_files())

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
    level: int = Field(ge=0)
    choice: int = Field(ge=0, le=2)


class LearningCodeRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)
    track: str = Field(min_length=1, max_length=20)
    level: int = Field(ge=0)
    code: str = Field(max_length=5_000)


class LearningEventRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)
    challenge_id: str = Field(min_length=1, max_length=80)
    event: str = Field(min_length=1, max_length=32)


class LearningSolutionRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)
    track: str = Field(min_length=1, max_length=20)
    challenge_id: str = Field(min_length=1, max_length=80)


class LearningPreviewRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)
    track: str = Field(min_length=1, max_length=20)
    level: int = Field(ge=0)
    code: str = Field(max_length=5_000)


class LearningReviewRequest(BaseModel):
    learner_id: str = Field(min_length=1, max_length=64)


class ScratchPythonRunRequest(BaseModel):
    """Arbitrary Python source. Limits come from the server, never this body."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(max_length=scratch_limits.PYTHON_MAX_SOURCE)
    run_id: Optional[str] = Field(default=None, max_length=80)


class ScratchSqlCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: str = Field(min_length=1, max_length=64)
    base: Optional[str] = Field(default="blank", max_length=64)


class ScratchSqlRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: str = Field(min_length=1, max_length=64)
    workspace_id: str = Field(min_length=20, max_length=128)
    sql: str = Field(max_length=scratch_limits.SQL_MAX_SOURCE)


class ScratchSqlWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: str = Field(min_length=1, max_length=64)
    workspace_id: str = Field(min_length=20, max_length=128)


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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Canonical backend catalog: readiness and execution are derived below.
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
# Signing needs preview, page navigation, and apply endpoints, so it uses
# dedicated routes instead of the generic one-request PDF handler.
PDF_CUSTOM_ROUTES = {"pdf-sign"}

for _tool in TOOLS:
    if _tool["id"] in CLIENT_TOOL_IDS:
        _tool["execution"] = "client"
        _tool["ready"] = True
    elif (
        _tool["id"] == "live-score"
        or _tool["id"] in pdftools.HANDLERS
        or _tool["id"] in PDF_CUSTOM_ROUTES
    ):
        _tool["execution"] = "api"
        _tool["ready"] = True
    else:
        _tool.setdefault("ready", False)
        _tool["execution"] = "unavailable"

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


@app.get("/api/tools")
async def api_tools(category: Optional[str] = None):
    # Publish only tools that have a working handler. Unreleased catalog entries
    # stay in the source list and do not appear in the public API.
    response = []
    for tool in TOOLS:
        if not tool["ready"] or tool["execution"] not in {"client", "api"}:
            continue
        if category and tool["category"] != category:
            continue
        public_tool = dict(tool)
        response.append(public_tool)
    return response


@app.post("/api/learning/session")
def api_learning_session(payload: LearningSessionRequest):
    """Resume or create an anonymous learning profile for this browser."""
    return learning.create_or_restore_session(payload.learner_id)


@app.post("/api/learning/event", status_code=204)
def api_learning_event(payload: LearningEventRequest):
    """Accept fixed event labels only; no source code, SQL, or result is retained."""
    try:
        learning.record_learning_event(payload.challenge_id, payload.event, payload.learner_id)
    except learning.LearningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/api/learning/solution")
def api_learning_solution(payload: LearningSolutionRequest):
    try:
        return learning.get_solution(payload.learner_id, payload.track, payload.challenge_id)
    except learning.LearningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


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


@app.post("/api/learning/preview")
def api_learning_preview(payload: LearningPreviewRequest):
    """Run learner code against challenge sample data without awarding XP or updating progress."""
    try:
        return learning.preview_code(payload.learner_id, payload.track, payload.level, payload.code)
    except learning.LearningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/api/learning/review")
def api_learning_review(payload: LearningReviewRequest):
    """Mixed practice set: hint-assisted and oldest completed challenges across tracks."""
    try:
        return learning.review_set(payload.learner_id)
    except learning.LearningError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


# --------------------------------------------------------------------------
# Code Quest Scratch
# --------------------------------------------------------------------------

def _raise_scratch_error(exc: ScratchError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.post("/api/learning/scratch/python/run")
def api_scratch_python_run(payload: ScratchPythonRunRequest):
    """Run one complete script. Never grades, awards XP, or writes progress."""
    try:
        return scratch_python.run_scratch(payload.code, payload.run_id)
    except ScratchError as exc:
        _raise_scratch_error(exc)


@app.post("/api/learning/scratch/sql/workspaces")
def api_scratch_sql_create(payload: ScratchSqlCreateRequest):
    try:
        return scratch_sql_workspaces.create_workspace(payload.learner_id, payload.base or "blank")
    except ScratchError as exc:
        _raise_scratch_error(exc)


@app.post("/api/learning/scratch/sql/run")
def api_scratch_sql_run(payload: ScratchSqlRunRequest):
    try:
        return scratch_sql.run_script(payload.learner_id, payload.workspace_id, payload.sql)
    except ScratchError as exc:
        _raise_scratch_error(exc)


@app.post("/api/learning/scratch/sql/reset")
def api_scratch_sql_reset(payload: ScratchSqlWorkspaceRequest):
    try:
        return scratch_sql_workspaces.reset_workspace(payload.learner_id, payload.workspace_id)
    except ScratchError as exc:
        _raise_scratch_error(exc)


@app.delete("/api/learning/scratch/sql/workspaces/{workspace_id}")
def api_scratch_sql_delete(
    workspace_id: str = ApiPath(min_length=20, max_length=128),
    learner_id: str = Query(min_length=1, max_length=64),
):
    try:
        return scratch_sql_workspaces.delete_workspace(learner_id, workspace_id)
    except ScratchError as exc:
        _raise_scratch_error(exc)


@app.get("/api/live")
async def api_live(day: Optional[str] = None, scope: Optional[str] = None):
    """Return fixtures in the provider-normalized API shape."""
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

def _pdf_error(_request: Request, message: str, status_code: int = 400):
    return JSONResponse({"detail": message}, status_code=status_code)


@app.exception_handler(RequestBodyTooLarge)
async def request_body_too_large(request: Request, _exc: RequestBodyTooLarge):
    return _pdf_error(
        request,
        "That request is too large. The limit is 100 MB for files, plus up to 1 MB for form data.",
        status_code=413,
    )


def _pdf_result(download_name: str, token: str):
    return JSONResponse(
        {
            "download_url": f"/api/pdf/download/{token}",
            "filename": download_name,
            "expires_in_seconds": pdftools.RESULTS_TTL,
        }
    )

@app.get("/api/pdf/download/{token}")
async def download_pdf_result(_request: Request, token: str):
    """Serve a finished PDF, once. The token is consumed by this request."""
    result = pdftools.take_result(token)
    if result is None:
        return JSONResponse(
            {"detail": "That download has expired or was already used."}, status_code=404
        )
    return pdftools.download_response(result)


# The three signing routes are declared above POST /api/pdf/{tool_id} for clarity.
# They do not actually collide with it: each has two path segments after /api/pdf,
# where the generic route has one.

def _sign_preview_payload(token: str, described: dict) -> dict:
    """The JSON the placement UI needs: page image, page count and page size.

    The page is inlined as a data URL so the app shows it without a second
    request, and the size travels in PDF points so the browser never has to
    guess the real page geometry.
    """
    image = base64.b64encode(described["png"]).decode("ascii")
    return {
        "token": token,
        "page": described["page"],
        "pages": described["pages"],
        "image": f"data:image/png;base64,{image}",
        "widthPt": round(described["width_pt"], 1),
        "heightPt": round(described["height_pt"], 1),
    }


@app.post("/api/pdf/pdf-sign/preview", response_class=JSONResponse)
async def pdf_sign_preview(request: Request):
    """Keep the uploaded PDF as a draft and return a rendered page to aim at."""
    form = await request.form()
    uploads = [v for v in form.getlist("files") if isinstance(v, UploadFile)]

    workspace = pdftools.new_workspace()
    try:
        saved = await pdftools.save_uploads(uploads, workspace, (".pdf",))
        page = _form_int(form, "page", 1)

        described = await run_in_threadpool(pdftools.sign.describe_page, saved[0], page)

        # The draft owns its tree from here; nothing else may delete it.
        token = pdftools.store_draft(saved[0], saved[0].name)
        return JSONResponse(_sign_preview_payload(token, described))

    except pdftools.ToolError as exc:
        pdftools.remove_tree(workspace)
        return _pdf_error(request, str(exc))
    except Exception:
        pdftools.remove_tree(workspace)
        raise


@app.get("/api/pdf/pdf-sign/page/{token}", response_class=JSONResponse)
async def pdf_sign_page(_request: Request, token: str, page: Optional[int] = None):
    """Re-render a different page of a previewed PDF, with the same payload shape."""
    draft = pdftools.find_draft(token)
    if draft is None:
        return _pdf_error(request, "That preview has expired. Upload the PDF again.", 404)

    try:
        described = await run_in_threadpool(
            pdftools.sign.describe_page, draft.path, page or 1
        )
    except pdftools.ToolError as exc:
        return _pdf_error(request, str(exc))

    return JSONResponse(_sign_preview_payload(token, described))


@app.post("/api/pdf/pdf-sign/apply", response_class=JSONResponse)
async def pdf_sign_apply(request: Request):
    """Place the signature on the drafted PDF and return a download link."""
    form = await request.form()
    values = {k: v for k, v in form.multi_items() if isinstance(v, str)}

    token = values.get("draft", "")
    draft = pdftools.take_draft(token)
    if draft is None:
        return _pdf_error(request, "That preview has expired. Upload the PDF again.", 404)

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
        return _pdf_error(request, str(exc))
    except Exception:
        pdftools.remove_tree(result_dir)
        raise

    # The draft's own tree belongs to it and was consumed on success.
    pdftools.remove_tree(draft.path.parent)
    return _pdf_result(download_name, download_token)


@app.post("/api/pdf/{tool_id}", response_class=JSONResponse)
async def run_pdf_tool(tool_id: str, request: Request):
    """Process a PDF upload and return a JSON download descriptor."""
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
    return _pdf_result(download_name, token)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

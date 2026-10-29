  # Central Hub

  This README describes the current Central Hub application, its architecture, features, and local setup.

  ## 1. Purpose

  Central Hub is a full-stack web application designed to combine personal productivity tools and utilities, with optional learning activities and connected data services into a single user-facing workspace. The product is intended to act as a practical digital hub where users can:

  - access browser-based utilities such as JSON formatting, Base64 encoding, hashing, QR generation, and date conversion,
  - run lightweight local games and study activities,
  - complete guided learning exercises for Python and SQL,
  - browse football fixtures and match details from public upstream sports providers,
  - process PDF files through server-side tools such as merge, split, organise, and metadata updates.

  The application uses a React frontend and a FastAPI JSON API. The backend owns integrations, learning progress, and server-side document processing; the frontend owns navigation and user-facing pages.

  ## 2. Scope

  This project provides a personal all-in-one digital hub for a single user, primarily intended for local use. It is not a large-scale enterprise platform and does not implement authentication, user accounts, or multi-user roles.

  The scope includes:

  - a central application shell and navigation,
  - category-based tool catalog browsing,
  - offline-capable client-side utilities,
  - a learning module for Python and SQL challenge exercises,
  - server-side PDF processing workflows,
  - browser persistence for lightweight local state.

  The scope excludes:

  - role-based access control,
  - persistent user accounts,
  - cloud-managed deployment orchestration,
  - production-grade security hardening for public internet exposure,
  - advanced document workflows requiring enterprise PDF signing infrastructure.

  ## 3. System overview

  Central Hub consists of two primary runtime components:

  1. Backend: Python + FastAPI
     - serves the API,
     - normalises data from third-party providers,
     - handles file uploads and PDF generation,
     - stores learning progress in SQLite.

  2. Frontend: React + TypeScript + Vite
     - provides the standalone dashboard experience,
     - renders tool categories and pages,
     - manages client-side utilities,
     - calls backend JSON endpoints for PDF and data features.

  The frontend and backend are intentionally decoupled. The frontend communicates with the API over HTTP/JSON, while the backend remains the authoritative source for external integrations and server-side file operations.

  ## 4. Architecture

  ### 4.1 Frontend architecture

  The frontend application is located under the `frontend/` directory and is built with:

  - React 19
  - TypeScript
  - Vite
  - React Router
  - TanStack Query
  - Tailwind CSS

  The frontend provides a consistent shell with navigation for:

  - Home / dashboard
  - Activities
  - Code Quest
  - Quick notes
  - Digital tools
  - Tool categories
  - Settings

  Each section is implemented as a feature module and is loaded through the application router with React Router.

  ### 4.2 Backend architecture

  The backend is located under the `backend/` directory and is built with FastAPI. It contains:

  - the API application entry point in `main.py`,
  - provider adapters under `backend/providers/`,
  - PDF processing logic under `backend/pdftools/`,
  - the SQLite learning store for Code Quest progress.

  The backend acts as the API and integration layer for:

  - sports data providers,
  - PDF generation and processing,
  - local utility catalog exposure,
  - API-driven data access for the frontend.

  ### 4.3 Data model and persistence

  The project uses a small, lightweight persistence model:

  - SQLite database for learning state (`backend/data/learning.sqlite3`)
  - browser local storage for notes and theme preference
  - temporary directories for uploaded PDFs and generated output
  - environment variables for backend secrets and configuration

  No user accounts are enforced; a browser-generated anonymous ID is used to resume progress in the learning feature.

  ## 5. Functional capabilities

  ### 5.1 Digital tools catalog

  The application exposes a catalog of tools grouped by category, including:

  - data tools,
  - encoding tools,
  - crypto tools,
  - generators,
  - time utilities,
  - text tools,
  - design utilities,
  - sports data tools,\r?\n  - PDF tools.

  Client-side utilities are executed directly in the browser without sending raw input to the backend. Examples include:

  - JSON formatter
  - Base64 encoding/decoding
  - hashing
  - UUID generation
  - timestamp conversion
  - regex testing
  - color conversion
  - QR generation

  ### 5.2 Activities and games

  The frontend includes a set of lightweight local activities intended for quick use and offline reuse after initial load. These include:

  - Tic-tac-toe
  - Memory Match
  - Number Guess

  These are primarily self-contained client features and do not depend on server-side logic.

  ### 5.3 Code Quest

  Code Quest is organized into two language modules, **Python** and **SQL**. Each module has a **Path** for guided challenges and a **Scratch** workspace for independent work. The hybrid **Case Files** project is linked from the Code Quest area as a cross-language project, not as a third language module.

  - **Python Path** — 14 phases and 72 challenges grouped into three stages: **Python Foundations** (phases 1–6), **Practical Python** (phases 7–9), and **Python Engineering** (phases 10–14). The path runs from the first `print()` through collections, functions, modules and imports, files with `pathlib`, CSV/JSON reports, error handling, classes, a read-only SQLite bridge, algorithms, testing/refactoring, and capstones. Early phases run in a guided interpreter for instant, safe feedback; later phases run real CPython in an isolated subprocess.
  - **SQL Path** — 10 phases from `SELECT` through joins, subqueries, window functions, schema design, cleaning, and performance work. Read-only phases query sandboxed SQLite databases; advanced phases add a disposable scratch database for schema and `UPDATE` lessons.
  - **Foundations challenge content** — earlier Python and SQL material remains available inside its language module with its original progression and grading behavior.
  - **Case Files** — the hybrid SQL + Python mystery path remains one cross-language project with one canonical route and progress identity at `/learn/case-files`.

  `/learn` is the Code Quest module chooser: Python, SQL, and Case Files are separate destinations. Opening Python or SQL shows only that module's navigation, Path, and Scratch areas; the other language does not appear there. Module routes are `/learn/python/path`, `/learn/sql/path`, `/learn/python/scratch`, and `/learn/sql/scratch`. The legacy `/learn/scratch/python` and `/learn/scratch/sql` URLs redirect to the matching module Scratch route, and `/learn/challenges` returns to the chooser. Python and SQL keep separate challenge content, progress keys, runners, drafts, and workspace behavior.

  All sandboxes use SQLite through Python standard library; no separate database server or driver is required. The shared registry in `backend/datasets/` includes Northwind, StreamHub, Bookings, Reviews, and the StreamHub Case File dataset:

  - **Northwind** — the classic business schema (customers, orders, products, shipping).
  - **StreamHub** — a streaming product: users, subscriptions, invoices, events, and support tickets.
  - **Bookings** — a deliberately messy hotel bookings extract for cleaning lessons.
  - **Reviews** - product reviews with a JSON attributes column.
  - **StreamHub Case File** - investigation records layered over StreamHub for the Case Files path.

  Datasets are seeded deterministically (identical data on every run), so grading is stable and datasets can be rotated freely. A `perf` tier (for example, 200,000 events) backs the performance lessons.

  Grading never compares against copied expected text: each submission runs live alongside a private reference solution on the same data, and behavior-preserving checks (reduced-data re-runs, constraint probes, feature checks) keep hardcoding from passing. Submissions run with row, step, and time caps; ATTACH, PRAGMA, and file-access functions are blocked. Python Path challenges run as isolated subprocesses with timeouts; SQL work is executed against restricted SQLite connections. This local-use design is not an OS-level security boundary for untrusted public users. Learner source is not retained.

  The subprocess uses `exec` to run learner code inside its harness. Isolation mode, a timeout, blocked imports/operations, and temporary per-run files provide local-use guardrails, not OS-level containment.

  Learner progress, XP, hints, and badges are stored in SQLite on the backend. Preview runs never award XP, hints unlock with the same rule as challenges, and solution walkthroughs open only after a challenge is completed. Learning aids stay honest: a pseudo-code plan is free to read (never a hint, never affects the mastery badge), predict-the-output warm-ups carry no XP, failed submissions get targeted coaching notes for classic mistakes, and a PRACTICE queue mixes hinted or stale completions across tracks.

  New phase-based learning paths are content packs: add a `phases_<name>.py` module under `backend/curriculum/` and build its challenges with shared factories. Add a runner in `grading.RUNNERS` only when a new execution profile is needed. See [doc.md](doc.md) for implementation details.

  **Scratch workspaces.** Code Quest also has learner-owned Scratch workspaces for running your own ideas outside challenge grading:

  - **Python Scratch** (`/learn/python/scratch`) runs the complete editor buffer in a fresh isolated CPython subprocess on every run. Limits are server-owned: 5,000 source characters, 5-second timeout, 20,000 stdout/stderr characters, and up to 10 UTF-8 text files (64 KiB per file, 256 KiB total). Runs return structured diagnostics and never grade, award XP, open hints, or touch challenge progress.
  - **SQL Scratch** (`/learn/sql/scratch`) uses a persistent, disposable SQLite workspace. Create a blank database or a copy of a registered dataset (`small` tier only), run multi-statement scripts atomically, then reset or delete the workspace. Each browser tracks one active workspace token; the server caps a learner at three active workspaces and expires idle workspaces after 60 minutes.

  Scratch editor drafts live in browser storage under versioned keys and stay separate from challenge drafts. SQL workspace files live under a server-owned temporary root (override with `CQ_SCRATCH_SQL_ROOT`) and are removed on startup and idle expiry. Scratch endpoints never call challenge grading and store no source, SQL, results, or generated files in the learning database. This is a local/trusted-use feature, not a public untrusted-code service. See [code-quest-workspaces.md](code-quest-workspaces.md) for the full contract.

  ### 5.4 LiveScore

  The application includes a football scoreboard feature that reads fixture data from public providers and normalises it into a common shape for display.

  Supported behaviour includes:

  - daily fixture browsing,
  - domestic/international scope filtering,
  - match detail views,
  - live match highlighting,
  - kickoff and match status formatting,
  - provider fallback logic.

  The implementation abstracts provider differences so that the frontend is not tightly coupled to a specific upstream API.

  ### 5.5 PDF processing

  The backend contains PDF automation workflows for tools such as:

  - merge PDFs,
  - split PDFs,
  - page organisation,
  - page numbering,
  - metadata editing,
  - text/image watermarking workflows.

  These operations are implemented as server-side processes because they require file handling, temporary storage, and backend-controlled validation.

  ## 6. External interfaces

  ### 6.1 Backend APIs

  The backend exposes JSON endpoints for frontend integration, including:

  - tool catalog retrieval,
  - learning session creation and code challenge submission,
  - match detail queries,
  - PDF processing requests,
  - secured download routes for generated files.

  Code Quest uses `POST /api/learning/session` to load progress and `POST /api/learning/code` to run and check a coding challenge. The API also supports preview, hints/events, answer submission for retained Foundations content, review sets, and solution walkthroughs.

  The FastAPI app also exposes generated OpenAPI documentation at `/docs` and `/redoc`.

  During development the frontend is served by Vite and calls the FastAPI JSON API. The backend does not render application pages.

  ### 6.2 Provider integrations

  The sports integration uses a provider abstraction that supports:

  - ESPN (default, no key required)
  - API-Football (preferred when configured with an API key)

  These providers are normalised into a common match and fixture structure so the presentation layer does not depend on provider-specific response fields.

  ## 7. Configuration and environment

  The project uses environment variables for backend configuration. The key configuration files are:

  - `backend/.env.example`
  - `frontend/.env.example`

  Important configuration values include:

  - `API_FOOTBALL_KEY` for optional external sports API access,
  - `FRONTEND_ORIGINS` for allowed frontend origins in CORS configuration,
  - `VITE_API_BASE_URL` for frontend API targeting in local or deployed environments.

  Sensitive values must remain in local `.env` files and must not be committed to source control.

  ## 8. Requirements

  ### Backend

  - Python 3.10+
  - pip
  - FastAPI ecosystem packages specified in `backend/requirements.txt`

  ### Frontend

  - Node.js 20+
  - npm

  ### Supporting dependencies

  - PDF libraries for backend processing,
  - HTTP client libraries for upstream API access,
  - frontend build toolchain for Vite and React.

  ## 9. Build and run

  ### 9.1 Start the backend

  From the project root:

  ```powershell
  cd backend
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install -r requirements.txt
  python -m uvicorn main:app --host 127.0.0.1 --port 8000
  ```

  ### 9.2 Start the frontend

  In a separate terminal:

  ```powershell
  cd frontend
  npm install
  npm run dev
  ```

  The frontend is typically served at:

  - http://127.0.0.1:5173

  The backend API is typically served at:

  - http://127.0.0.1:8000

  ### 9.3 Run the backend tests

  The Scratch contract tests use the standard library `unittest` runner and the project virtualenv (no `pytest` dependency):

  ```powershell
  cd backend
  .\.venv\Scripts\python.exe -m unittest discover -s tests -v
  ```

  The suite starts the real FastAPI lifespan against temporary learning and SQL workspace roots, so it never touches `backend/data/learning.sqlite3` or the default scratch root.

  ## 10. Security and privacy considerations

  This project is intended for local and small-scale deployment and does not implement enterprise security controls. Current design considerations include:

  - local-only storage of lightweight user state in browser storage,
  - no account system or authentication layer,
  - backend-only management of credentials for external services,
  - temporary file handling for uploaded documents,
  - provider-backed access to public football data rather than private operational systems.

  Important operational guidance:

  - keep secrets in `.env` files and not in source control,
  - ensure uploaded files are processed in temporary directories and deleted when no longer needed,
  - validate and restrict external service configuration before deployment,
  - treat upstream provider responses as third-party data and verify assumptions before relying on them in production workflows.

  ## 11. Project structure

  ```text
  Central_hub/
  ├── README.md
  ├── backend/
  │   ├── main.py
  │   ├── requirements.txt
  │   ├── .env.example
  │   ├── learning.py
  │   ├── curriculum/
  │   ├── datasets/
  │   ├── providers/
  │   ├── pdftools/
  │   ├── scratch/
  │   └── tests/
  ├── frontend/
  │   ├── package.json
  │   ├── vite.config.ts
  │   └── src/
  ├── run.txt
  ├── .gitignore
  └── .git
  ```

  ## 12. Current status and limitations

  The project is an operational local-first digital hub and is still evolving. Notable current limitations include:

  - some advanced PDF workflows remain planned or partially implemented,
  - the application is not designed as a multi-user production system,
  - Python Scratch uses a best-effort local subprocess sandbox (static source screen, timeout, output caps, temporary per-run directory), which is not an OS-level security boundary for untrusted public users,
  - SQL Scratch workspaces are disposable, capped, and expire after idle time; they are not durable storage or backups,
  - some third-party sports data integrations rely on public provider behavior and may change without notice,
  - the application has no accounts or cross-device sync; lightweight user state is kept in the browser or local SQLite database.

  ## 13. Summary

  Central Hub is a lightweight, local-first digital hub for everyday tasks. It brings together:

  - browser-native utility tools,
  - educational challenge exercises,
  - server-side document utilities,
  - a single accessible digital workspace.

  Its core design goal is simplicity and convenience: provide users with a single place to perform common tasks, learn programming concepts, and access useful data without requiring formal account management or a large-scale platform architecture.

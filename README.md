  # Central Hub

  Document type: Simplified Technical Documentation
  Status: Active
  Version: 1.0

  This document provides the project overview, system context, and technical description for Central Hub technical documentation structure.

  ## 1. Purpose

  Central Hub is a full-stack web application designed to combine everyday productivity utilities, learning activities, and external data services into a single user-facing workspace. The product is intended to act as a practical digital hub where users can:

  - access browser-based utilities such as JSON formatting, Base64 encoding, hashing, QR generation, and date conversion,
  - run lightweight local games and study activities,
  - complete guided learning exercises for Python and SQL,
  - browse football fixtures and match details from public upstream sports providers,
  - process PDF files through server-side tools such as merge, split, organise, and metadata updates.

  The application is intentionally designed with a dual interface model: a modern React frontend for the standalone experience and a FastAPI backend that provides APIs, data processing, and compatibility routes for the existing web interface.

  ## 2. Scope

  This project provides a self-contained utility and learning portal for single-user or small-team local use. It is not a large-scale enterprise platform and does not implement authentication, user accounts, or multi-user roles.

  The scope includes:

  - a central application shell and navigation,
  - category-based tool catalog browsing,
  - offline-capable client-side utilities,
  - a learning module for Python and SQL challenge exercises,
  - sports fixture browsing through provider-normalised APIs,
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
     - provides compatibility pages,
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

  Each section is implemented as a feature module and is loaded through the application router rather than embedding different pages directly into the backend templates.

  ### 4.2 Backend architecture

  The backend is located under the `backend/` directory and is built with FastAPI. It contains:

  - the API application entry point in `main.py`,
  - provider adapters under `backend/providers/`,
  - PDF processing logic under `backend/pdftools/`,
  - templated legacy pages under `backend/templates/`,
  - the SQLite learning store for Code Quest progress.

  The backend acts as the integration layer for:

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
  - sports tools,
  - PDF tools.

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

  Code Quest is the educational component of the application. It provides multiple challenge tracks for:

  - Python fundamentals
  - SQL query reasoning

  Each challenge provides an editable coding workspace, starter code, progressive hints, run feedback, and output. Learners build Python fundamentals and SQL queries one step at a time, earn XP, and unlock subsequent levels. Challenge progress is persisted in SQLite on the backend.

  Python submissions run through a small interpreter that supports the language features used in the lessons, including variables, printing, conditions, loops, and simple functions. SQL submissions run against temporary sample tables in a read-only SQLite connection. The service does not execute submitted Python with `eval` or `exec`, and SQL writes are blocked.

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
  - sports fixture queries,
  - match detail queries,
  - PDF processing requests,
  - secured download routes for generated files.

  Code Quest uses `POST /api/learning/session` to load progress and `POST /api/learning/code` to run and check a coding challenge.

  Each language track has 11 guided coding challenges: five beginner, three intermediate, and three advanced. Intermediate work practices filtering, state tracking, joins, and common table expressions. Advanced work introduces search algorithms, recursion, window functions, and recursive CTEs. Clearer challenges award more XP, and hints plus saved browser drafts support practice at the learner's pace.

  The editor colors Python and SQL commands, names, functions, strings, numbers, and comments while keeping native keyboard editing. Python runs in a restricted interpreter; SQL runs read-only against small in-memory datasets. Learner progress remains in SQLite, and startup migrates older five-level progress tables without clearing saved completions.

  The FastAPI app also exposes generated OpenAPI documentation at `/docs` and `/redoc`.

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
  │   ├── providers/
  │   ├── pdftools/
  │   ├── templates/
  │   └── static/
  ├── frontend/
  │   ├── package.json
  │   ├── vite.config.ts
  │   └── src/
  ├── run.txt
  ├── .gitignore
  └── .git
  ```

  ## 12. Current status and limitations

  The project is operational as a combined utility hub and learning platform, but it is still evolving. Notable current limitations include:

  - some advanced PDF workflows remain planned or partially implemented,
  - the application is not designed as a multi-user production system,
  - some third-party data integrations rely on public provider behavior and may change without notice,
  - the legacy backend templates remain available alongside the newer React frontend during migration.

  ## 13. Summary

  Central Hub is best understood as a lightweight, local-first productivity and learning portal that blends:

  - browser-native utility tools,
  - educational challenge exercises,
  - sports data browsing,
  - server-side document utilities,
  - a single accessible digital workspace.

  Its core design goal is simplicity and convenience: provide users with a single place to perform common tasks, learn programming concepts, and access useful data without requiring formal account management or a large-scale platform architecture.

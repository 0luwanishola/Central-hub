# Code Quest: Python and SQL Workspaces

**Status:** implementation specification  
**Product goal:** let a learner study a challenge and also run their own ideas in the same Code Quest area.  
**Audience:** agents and developers implementing Code Quest changes.  
**Product scope:** local-first, single-user learning and experimentation. This document does not authorize exposing arbitrary code execution as a public multi-user service.

## Implementation status

Stages 0–3 are implemented; Stage 4 (career-path content audit) and Stage 5 (further module extraction) remain open.

- **Python Scratch** (`POST /api/learning/scratch/python/run`) reuses the hardened `python_runner` subprocess. Results are shaped by `backend/scratch/python_service.py`; each run returns bounded stdout/stderr and up to 10 UTF-8 text artifacts (64 KiB each, 256 KiB total) and never enters challenge grading.
- **SQL Scratch** uses `backend/scratch/sql_workspaces.py` for token/ownership/lifecycle policy and `backend/scratch/sql_service.py` for atomic multi-statement execution through `sql_runner.workspace_authorizer()`. Learner transaction control, temp schema objects, PRAGMA, ATTACH/DETACH, VACUUM, extension loading, and file functions are denied server-side.
- Routes are registered in `backend/main.py` under `/api/learning/scratch`. All limits come from `backend/scratch/limits.py`; request models use `extra="forbid"` so clients cannot override timeouts, paths, or caps.
- The UI keeps one active workspace token per browser learner in local storage (with a replace confirmation) while the server independently enforces a cap of three active workspaces per learner. The SQL workspace root defaults to the system temp directory (`central_hub/sql_scratch`) and can be overridden with `CQ_SCRATCH_SQL_ROOT`; startup wipes stale files because tokens are process-local.
- Backend contract tests live in `backend/tests/test_scratch.py` (standard library `unittest`); see `README.md` §9.3 for the command.

## 1. Product decision

Code Quest must offer two clearly distinct modes for both Python and SQL:

1. **Learning mode** presents a curriculum challenge, checks whether the learner met its requirements, provides learning feedback, and may update progress, XP, badges, hints, and review scheduling.
2. **Scratch mode** lets the learner run their own idea without selecting a challenge. It returns execution results and diagnostics. It never grades against a challenge and never changes learning progress, XP, hints, badges, or completion state.

Python scratch mode is a general-purpose Python code runner. SQL scratch mode is a general-purpose SQL workspace over a disposable SQLite database, optionally seeded from one of the app's registered learning datasets. Scratch means a contained workspace; it does not mean access to the host shell, the repository, arbitrary host files, or a production database.

The UI may call these areas **Learn** and **Scratch** or **Challenges** and **Scratchpad**. The product copy must say that runs are bounded and must not imply that the workspace is a full operating-system terminal.

## 2. Current architecture and reuse points

The relevant current implementation is:

- `backend/main.py`: FastAPI setup and learning endpoints.
- `backend/learning.py`: challenge definitions for retained Foundations content, track lookup, progress persistence, preview/check orchestration, and some runner logic.
- `backend/curriculum/`: phase-based Python, SQL, and Case Files packs; `grading.py` dispatches challenge graders by runner name.
- `backend/python_runner.py`: real CPython subprocess, temporary per-run directory, time limit, output cap, source screening, and optional fixtures or read-only dataset bridge.
- `backend/guided_python.py`: restricted in-process Python interpreter for early lessons. This is for guided curriculum use and is not the general scratch runtime.
- `backend/sql_runner.py`: SQLite statement splitting, read-only and disposable scratch modes, authorizer policy, result caps, and progress/time limits.
- `backend/datasets/`: deterministic SQLite dataset registry and schema metadata.
- `frontend/src/features/learning/LearnPage.tsx`: Code Quest session, selected track/challenge, editor state, drafts, and learning mutations.
- `frontend/src/features/learning/components/SqlWorkbench.tsx`: current shared challenge workspace composition despite its SQL-oriented filename; it displays both Python and SQL challenges.
- `frontend/src/services/apiClient.ts` and `frontend/src/types/index.ts`: frontend API wrappers and contracts.

Do not create separate copies of the existing Python or SQL execution engines for scratch mode. Add explicit scratch service/API flows that reuse the existing engines while bypassing challenge grading and progression. The current SQL `mode="scratch"` is a per-challenge disposable database for curriculum lessons; it is not yet a learner-owned persistent scratch workspace.

## 3. Core behavior contract

### 3.1 Isolation between modes

The scratch and learning flows must remain separate at every boundary:

- Different API operations and mutation functions.
- Different output/result presentation states.
- Scratch requests do not require a `track`, `challenge_id`, or `level`.
- Scratch requests do not call challenge grading, award XP, or write learning progress.
- Scratch execution may record coarse operational metrics only if explicitly designed later; do not store source, SQL, result data, or file contents as analytics.
- A scratch result cannot unlock a solution, mark a challenge complete, count toward progress, or enter the review queue.
- Challenge mode continues to use the challenge's declared `runner`, `dataset`, `fixtures`, `checks`, `mode`, and caps.

Use separate React Query keys, mutation state, and result types for scratch. Switching tabs must not silently submit or discard challenge code. Preserve each editor's draft independently.

### 3.2 Shared behavior

Both scratch experiences should provide:

- A code editor appropriate to the selected language.
- Run and Reset controls, with clear pending/disabled states.
- Keyboard shortcut for run; show the shortcut in the UI.
- Output and structured error display; retain prior output only until another run or explicit clear.
- A visible notice that each run has time, output, and workspace limits.
- A concise first-run example or optional starter snippet; it must be editable and not treated as a challenge.
- Local browser draft persistence with versioned keys, error handling for disabled storage, and a clear action to reset the draft.
- Clear separation from XP/progress UI. The shared Code Quest shell may still show the learner's overall progress, but scratch runs do not change it.

## 4. Python Scratch specification

### 4.1 User-facing capability

Python Scratch accepts an arbitrary Python script, not just code shaped for the active lesson. It must support ordinary expressions, variables, loops, functions, imports from the supported standard library, and common multi-line scripts to the extent allowed by the current runner's safety policy. Do not require a `challenge_id` or require the code to print a predeclared expected answer.

For example, this should be runnable without opening a Python lesson:

```python
from collections import Counter

words = "ideas are easy; testing ideas makes them useful"
print(Counter(words.split()))
```

The initial feature does not need persistent interpreter state between runs. Each Run executes the complete current editor buffer in a fresh process. Explain this behavior in the UI so users know that variables from a previous run are not retained.

### 4.2 Runtime and execution flow

1. The frontend sends source code and a scratch-run request ID to a dedicated scratch endpoint.
2. The backend validates the request size and code length.
3. The backend calls `python_runner.run_python` (or a small public wrapper around it) with no challenge grader, fixtures, or dataset unless an explicitly selected future feature supplies a safe registered dataset.
4. Execution occurs in a fresh temporary directory and isolated CPython subprocess, using the existing timeout, output, and file handling mechanisms.
5. Return a structured result. Always clean up the temporary directory, including failures and timeouts.
6. The endpoint must not call `learning.submit_code`, `learning.preview_code`, or any progress mutation.

The regular scratch mode should initially run in the same Python environment/interpreter as the existing `python_real` runner. Do not install arbitrary packages at runtime. Do not promise internet access, shell access, notebook semantics, GPU access, or host filesystem access.

### 4.3 Files

The existing Python runner can read learner-created files from its temporary directory before cleanup. Scratch mode may return a bounded list of text files created during the run, using that existing mechanism, with these rules:

- Only files created under the per-run temporary directory are eligible.
- Never return the runner's `learner.py`, `harness.py`, or seeded infrastructure files.
- Bound the number of returned files, each file's byte size, total returned bytes, filename length, and text decoding.
- Do not return arbitrary binary files as text. For v1, omit non-text files and files over the limit with a clear per-file status where practical.
- Files are per-run artifacts. They are not durable user files and disappear after the response; the browser may offer a download of a returned text file.
- Never accept a path from the client and read it from the host.

If the existing runner's file reporting is too broad or lesson-specific, factor its internal execution result into a shared private runner function and add a strict scratch-specific result adapter. Keep limits centralized and consistent.

### 4.4 Python result contract

Use a dedicated endpoint, for example `POST /api/learning/scratch/python/run`. The request contains `code` and may contain a client-generated `run_id` used only to correlate the response. It must not accept a challenge ID, track ID, dataset path, arbitrary runner settings, timeout, or output-limit override. The service selects server-owned limits and invokes the existing real-Python subprocess. Require only the ordinary local scratch-mode context; do not make learning progress a prerequisite to experimenting. Use Pydantic validation and return a JSON error contract for invalid source/size and runner failures.

Define a typed result, for example:

```json
{
  "run_id": "client-generated-or-server-generated-id",
  "status": "completed",
  "stdout": "...",
  "stderr": "...",
  "error": null,
  "error_line": null,
  "duration_ms": 42,
  "timed_out": false,
  "truncated": false,
  "files": [{"name": "summary.txt", "content": "...", "truncated": false}]
}
```

The exact field names may follow the existing `LearningCodeResult` conventions, but scratch results must have their own TypeScript type and must not contain `xp`, `progress`, `correct`, challenge feedback, or challenge metadata. Distinguish a Python exception, a timeout, an invalid request, and an internal runner failure. Preserve the error line when available. Bound stdout/stderr independently and indicate truncation.

### 4.5 Python guardrails and honest limitations

Reuse the existing timeout and caps. Make the scratch limits explicit constants or validated settings; initial values should not exceed the runner's existing bounds without a documented reason. Ensure subprocess output cannot grow unbounded in parent memory: if `subprocess.run(capture_output=True)` permits output to grow past the cap before truncation, improve collection/capping as a separate runner hardening step before describing the cap as a hard memory limit.

The existing subprocess and AST source screen are best-effort local-use guardrails, not an OS-level security boundary. Arbitrary Python may still access capabilities not anticipated by the static screen. The product is for the user's local/trusted use. Do not expose this endpoint as a public untrusted-code service. If public multi-user hosting becomes a goal, require a separate security design using OS/container isolation, resource quotas, filesystem/network policy, process ownership, and operational abuse controls before deployment.

Do not label this feature a “terminal” in a way that implies a shell. It runs Python source only.

## 5. SQL Scratch specification

### 5.1 User-facing capability

SQL Scratch accepts multi-statement SQL scripts and lets the learner inspect the results of every statement that returns rows. It should support queries and ordinary database-development exercises such as creating tables, inserting/updating/deleting rows, indexes, constraints, views, and transactions to the degree allowed by the authorizer.

The learner chooses one of these workspace bases:

1. **Blank SQLite database** (default): starts with no user tables.
2. **Registered dataset copy** (optional v1): select an available dataset such as Northwind, StreamHub, Bookings, or Reviews. The workspace receives an isolated copy. Writes never modify the registry source or a curriculum attempt.

Dataset selection is explicit. Do not silently load lesson data into a blank workspace. Display the active base dataset and provide a clear Reset action that recreates the selected base from scratch.

### 5.2 Workspace persistence and lifecycle

Unlike Python, SQL schema/data needs to survive multiple Run requests. The v1 SQL workspace is persistent across requests for the active learner/browser, but disposable and bounded:

- Create the workspace through a dedicated API operation. The server generates an unguessable workspace token; never use a caller-supplied path or raw filesystem name.
- Bind workspace ownership to the existing anonymous learner ID. Validate that ID with the same UUID validation already used by learning services. A workspace token alone must not be enough to access another learner's workspace.
- Store the SQLite file under a server-owned temporary root with restrictive permissions where supported. Generate filenames server-side. Keep each workspace in its own directory.
- The blank base is an empty SQLite database. For a dataset base, seed a fresh copy using `backend/datasets/` then make that copy writable for the learner.
- Persist database state between runs in the active workspace so a learner can create a table in one run and query it in another.
- Reset destroys/rebuilds the current workspace using its originally selected base. It must require an explicit UI action; do not reset automatically after every Run.
- Expire abandoned workspaces after a configurable idle TTL, initially 60 minutes. Refresh `last_used` on successful create/run/reset operations. A periodic cleanup removes expired directories and files.
- Enforce a maximum workspace file size and a maximum number of active workspaces per learner: v1 defaults are 25 MiB per workspace and 3 active workspaces per learner. Use SQLite's page limit (or an equivalent enforceable cap) so a query cannot first grow past the disk quota and only then be rejected. Reject a run that reaches the cap with an actionable message.
- Seed registered dataset workspaces from the small tier only. Do not offer `perf` datasets as an initial SQL Scratch base.
- If a server restart loses in-memory token metadata, stale files must become inaccessible and be cleaned on startup. Do not claim durable backup. Local browser state can retain the workspace token only for the current lifetime; expired/invalid tokens should offer a recreate action.
- Provide an explicit “New workspace” action, and confirm before replacing a workspace with unsaved database state.

This is disposable scratch data, not a second learning-progress database. Do not add SQL workspace tables to `learning.sqlite3` unless later requirements demand durable history. Do not persist source scripts or query history server-side.

V1 is for the current single-backend-process local deployment. The workspace registry/locks may be process-local. Do not run multiple independent API workers against this design until workspace token metadata, ownership, expiry, and locking are moved to a shared coordination layer. The anonymous learner UUID is a local profile identifier, not authentication suitable for hostile networks.

### 5.3 SQL execution semantics

Use the existing `sql_runner` safety policy, but add a dedicated workspace service that manages database files and connections. Do not route scratch SQL through challenge grading.

For each request:

1. Validate the workspace token, learner ownership, script length, statement count, and optional run limits.
2. Open only the resolved server-owned workspace database. Reject symlink/path traversal and ensure the resolved path stays under the workspace root.
3. Enable SQLite defensive settings available in the installed Python/SQLite version; disable extension loading.
4. Apply an explicit authorizer policy. Scratch mode allows only the documented schema and data operations. Always deny `ATTACH`, `DETACH`, extension loading, dangerous file functions, and unsafe `PRAGMA` operations. Be especially cautious with SQLite authorizer semantics for transaction and temp-schema actions.
5. Apply per-run wall-clock and SQLite progress-operation caps, source-size cap (5,000 characters initially, matching challenge code), statement-count cap (50 initially), per-statement row cap (100 initially), cell/text-size cap, and total response-byte cap (1 MiB initially). Keep these as server constants, not client overrides.
6. Use SQLite's completeness checker for statements; do not split scripts on semicolons with a naive regex.
7. Execute the script in order and collect a result entry for each statement. For DDL/DML with no row result, return the statement kind and affected-row count where SQLite can provide it. For `SELECT`/`RETURNING` statements, return bounded columns and rows. Do not return an unbounded full table.
8. Run each script atomically inside a backend-managed transaction. Begin the transaction before enabling the learner authorizer; deny learner-issued `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, and `RELEASE` operations in the public scratch API. On any statement failure, roll back the entire script so no partial changes are left. On success, remove/relax the authorizer as needed for the backend to commit. Explain this behavior in the UI. SQL transaction-control commands remain teachable in the existing challenge runner where the challenge owns the disposable database and grading contract; the general SQL Scratch API does not offer them in v1.
9. Close the connection reliably, update activity time, and return structured results. Keep the workspace database if the request fails after rollback.

Do not claim SQLite is interchangeable with every production database. The workspace teaches SQLite. PostgreSQL, SQL Server/T-SQL, MySQL, and cloud data warehouse dialects can be added later as separately scoped curricula/runners, not by pretending SQLite implements them.

### 5.4 SQL API contract

Use dedicated endpoints under `/api/learning/scratch/sql`. Keep route code thin and put workspace/file policy in a service module:

- `POST /api/learning/scratch/sql/workspaces` — create workspace. Request includes `learner_id` and `base` (`blank` or a registered dataset ID). Response includes opaque `workspace_id`, base metadata, expiry/idle TTL, and limits.
- `POST /api/learning/scratch/sql/run` — request includes `learner_id`, `workspace_id`, and `sql`. Response includes per-statement outputs, final result summary, duration, truncation flags, and workspace metadata.
- `POST /api/learning/scratch/sql/reset` — request includes `learner_id` and `workspace_id`; response confirms reset and returns the same base metadata.
- `DELETE /api/learning/scratch/sql/workspaces/{workspace_id}` — explicitly destroy the workspace. Verify ownership before deletion.

Use Pydantic request/response models, appropriate 4xx errors for invalid/expired workspace and limits, and a consistent JSON `detail` error contract. Do not let the frontend choose a database path, SQL mode policy, timeout, row cap, or workspace file limit.

For SQL `Run`, serialize operations against the same workspace with a per-workspace lock. Reject concurrent reset/delete while a run is active, or queue them behind that run. Do not hold a process-wide lock while queries execute. Return the same generic not-found/expired response for unknown tokens and tokens owned by a different learner so the endpoint does not reveal workspace existence.

Example run response:

```json
{
  "workspace_id": "opaque-token",
  "status": "completed",
  "duration_ms": 8,
  "statements": [
    {"index": 0, "kind": "CREATE TABLE", "columns": [], "rows": [], "affected_rows": 0},
    {"index": 1, "kind": "INSERT", "columns": [], "rows": [], "affected_rows": 2},
    {"index": 2, "kind": "SELECT", "columns": ["id", "name"], "rows": [[1, "Ada"], [2, "Grace"]], "truncated": false}
  ],
  "error": null,
  "workspace": {"base": "blank", "expires_in_seconds": 3600}
}
```

The response must not include learning progress or XP. Decide whether displaying every statement result is too noisy; if so, keep a bounded list of statement summaries and a selected result panel, but do not silently omit write/query errors.

## 6. Curriculum: beginner through developer/engineer

The product ambition is to take a learner from SQL beginner toward practical analytics, data engineering, and database development. The existing SQL path already covers SELECT, aggregation, joins/grain, CTEs, window functions, analytics patterns, schema/DDL, performance, transactions, and case studies. Treat this as a strong base and audit it for gaps; do not author a second duplicate beginner curriculum.

### 6.1 Proposed progression map

Use learning outcomes and projects, not job-title promises, to define levels:

1. **SQL foundations:** tables/rows, SELECT, filtering, sorting, NULL, aliases, basic expressions.
2. **Analyst:** aggregation, joins and row grain, subqueries/CTEs, windows, date/text/JSON data, metrics and validation, communicating findings.
3. **Developer:** schema design/normalization, keys and constraints, views, indexes, transactions, safe CRUD, parameterized query concepts, query plans, migrations as a concept.
4. **Data engineer:** ingest/clean/transform pipelines, staging and curated layers, idempotent loads, deduplication, incremental processing, slowly changing dimensions/concepts, data quality constraints, reconciliation, late/duplicate data, performance and reproducibility.
5. **Advanced practice:** integrated projects with requirements, ambiguous data, validation evidence, performance tradeoffs, and a short written interpretation.

These are proposed curriculum layers, not necessarily five UI tracks. Prefer the current Python Path / SQL Path mental model with phases and challenge packs. Consider specialist SQL Analyst and SQL Developer/Data Engineering paths only if different learner goals warrant branching after the shared foundations. A final design decision should be based on content/playtesting; do not duplicate foundations just to add more track labels.

### 6.2 SQLite dialect boundaries

Keep v1 SQLite-only. Mark dialect-specific lessons and syntax as SQLite. Teach transferable concepts where possible, and include short comparison notes for PostgreSQL/SQL Server/MySQL only when accurate. Do not mix unsupported syntax into an exercise and then make learners infer why it fails. Later dialect support requires a separate runner/profile, driver/dependency decision, isolated database provisioning, migration/data portability, and dialect-specific grading.

## 7. Frontend organization and module boundaries

### 7.1 Reuse, do not over-merge

- Keep `ChallengeBrief`, `ChallengeExplorer`, `LearningOutputPanel`, `PredictCheck`, and `SchemaNavigator` as focused presentation components.
- Keep the Python and SQL execution policies in separate backend runners.
- Keep Python Scratch and SQL Scratch as separate workspace components because their state models differ: Python resets process state each run; SQL persists database state.
- Rename `SqlWorkbench.tsx` to a neutral name such as `ChallengeWorkbench.tsx` only if that reduces confusion during this work; it currently composes both language experiences. Do not mix scratch-specific state into this challenge workbench.
- Split `LearnPage.tsx` if needed into a thin challenge page and a small challenge-session hook/controller. Keep API transport in `apiClient.ts`.
- Add a `scratch/` frontend feature directory with `PythonScratchPage`/`PythonScratchWorkspace` and `SqlScratchPage`/`SqlScratchWorkspace`. Keep `/learn` as the existing Challenges route; add `/learn/scratch/python` and `/learn/scratch/sql` routes. Add visible Code Quest navigation between Challenges and Scratch, and between the two scratch languages. Browser back/forward must restore the selected route.
- Add dedicated TypeScript request/result types. Do not widen `LearningCodeResult` until it ambiguously represents challenge grading and scratch execution.

### 7.2 Suggested backend boundaries

Keep `main.py` as route registration/request translation. As implementation proceeds, extract:

- `backend/learning_service.py` (or equivalent): challenge operations and orchestration, if `learning.py` remains too broad.
- `backend/scratch/python_service.py`: validate/run arbitrary Python, adapt bounded output, never mutate learning state.
- `backend/scratch/sql_workspaces.py`: create/resolve/authorize/reset/expire/delete server-owned SQLite files.
- `backend/scratch/sql_service.py`: script execution and bounded result serialization through `sql_runner`.
- Existing `curriculum`, `grading`, `datasets`, `python_runner`, and `sql_runner` stay separately testable modules.

Do not move files solely to make a larger directory tree. Extract when it gives a clear owner for a responsibility and improves testability. Keep compatibility imports stable until all callers move.

## 8. Data, persistence, and privacy

- Learning progress remains in the existing SQLite learning store and keeps its current migration compatibility.
- Scratch editor source is stored only in the browser's local storage (versioned keys) unless the user later asks for durable sync. Handle quota/security exceptions and offer download/copy when persistence is unavailable.
- Python process state and files are per run and temporary.
- SQL workspace database state is server-side, disposable, tokenized, capped, and subject to idle expiration.
- Do not persist scratch code, query history, stdout, stderr, rows, or generated files in the learning database or analytics.
- Do not reset learning progress or alter the current learner ID when enabling scratch mode.
- Show a clear expiry/temporary-data notice for SQL workspace state. If the workspace expires, keep the editor buffer and provide a one-click recreate action, but explain that database tables/data from the expired workspace are gone.

## 9. Failure and edge-case behavior

Implement explicit user-facing handling for:

- Empty code/script, code/script too long, too many SQL statements, or unsupported operation.
- Python syntax/runtime exception, timeout, runner process failure, truncated output, or oversized generated file.
- SQL syntax/authorization/constraint error, query timeout/step cap, result truncation, workspace quota hit, invalid/expired workspace, and workspace file error.
- Browser storage disabled/quota exceeded.
- Double-click/repeated Run. Disable the run button while in flight; server requests should be bounded even if clients retry.
- Reset while a run is in flight. Prevent races or serialize workspace operations per workspace.
- Browser reload. Restore editor draft and the current SQL workspace token if still valid; otherwise preserve editor SQL and offer workspace recreation.
- Server restart. SQL scratch DBs may be lost/inaccessible. Do not corrupt learning progress.

Error messages should explain the next useful action. Do not leak Python tracebacks, host file paths, environment variables, tokens, internal exception dumps, or database file locations.

## 10. Implementation stages

Implement in small reviewable slices. Do not bundle a broad learning-engine rewrite with the first scratch release.

### Stage 0 — Baseline and contract

- Read current API types, runner implementations, and Code Quest UI before editing.
- Record current public API contracts and learner progress schema. Preserve challenge completion, XP, hints, and review behavior.
- Add this document to the implementation checklist; record unresolved initial limits as constants in one place.

### Stage 1 — Python Scratch vertical slice

- Add a typed scratch request and response.
- Add a dedicated endpoint/service that validates and invokes `python_runner` without challenge metadata or progress writes.
- Ensure subprocess timeout, output bounds, per-run files, and internal errors are handled.
- Add a Scratch mode selector and independent Python editor/draft/output UI.
- Confirm session progress and XP are unchanged by any scratch request.

### Stage 2 — SQL workspace lifecycle

- Add workspace token generation, learner ownership validation, server-root path resolution, workspace create/reset/delete, idle expiry, quota, and periodic/startup cleanup.
- Support blank database and registered dataset copy.
- Decide and implement transaction/script semantics before exposing multi-statement writes.
- Add create/run/reset/delete API operations and structured per-statement results.
- Make concurrent operations on one workspace safe (lock per workspace or equivalent).

### Stage 3 — SQL Scratch UI

- Add independent SQL draft and workspace state.
- Show selected base dataset, database persistence across runs, idle expiration, output tables, DDL/DML status, and reset/new workspace controls.
- Preserve the editor buffer even if the server workspace expires.

### Stage 4 — Career-path content audit

- Compare existing phase content with §6.1 learning outcomes.
- Identify only real gaps in analyst, developer, and data engineering competencies.
- Author incremental phases/capstones using existing challenge factories and stable IDs.
- Use registered datasets or add deterministic, documented datasets only when they teach a distinct concept.
- Playtest content for clear requirements, multiple valid SQL approaches where appropriate, row-grain reasoning, data quality, and meaningful validation.

### Stage 5 — Refine module boundaries

- Extract orchestration/persistence only where the scratch work exposes concrete coupling that makes changes difficult.
- Move repeated request validation or result shaping into services, not generic abstractions without multiple callers.
- Keep challenge and scratch types, endpoints, and UI state separate.

## 11. Acceptance criteria

The feature is complete only when all applicable criteria hold:

### Python

- A learner can switch from Python Challenges to Python Scratch.
- Scratch accepts code unrelated to any current lesson and returns its output without expected-answer grading.
- A scratch run does not change XP, progress, badges, hints, completion, or review queue.
- Each run starts fresh; a subsequent run does not retain variables from the previous run.
- Timeout, output truncation, exceptions, and file limits return understandable structured results.
- Files outside the temporary run directory cannot be read back as created artifacts.
- Scratch code draft persistence is independent from challenge drafts.

### SQL

- A learner can create a blank workspace or a copy of a registered dataset.
- A learner can create a table, insert rows in one run, then query/update them in a later run.
- Reset returns the workspace to its selected original base; deleting destroys it.
- Workspace state is isolated from other workspace tokens and the dataset registry.
- Expired/invalid workspaces return a clear error and can be recreated without losing the editor buffer.
- Script execution is multi-statement with documented atomicity; statement outputs/errors are bounded and structured.
- Authorizer, attach/detach, extension loading, file functions, time/step/row/size limits, and ownership checks are enforced server-side.
- A scratch SQL run does not change learning progress or XP.
- SQL source draft persistence is independent from challenge drafts and workspace reset does not silently clear editor text.

### System and compatibility

- Existing challenge preview/check, solution, hint, progression, review, and dataset navigator behavior remains intact.
- Existing learning progress DB opens without destructive migration or loss.
- API rejects malformed IDs/tokens/source and does not reveal internals.
- UI states clearly explain scratch semantics, temporary data, SQLite dialect, and local-use limits.
- No public deployment claim is made for the current Python sandbox.

## 12. Verification guidance for the implementing agent

The implementing agent should verify behavior when asked to implement this specification. At minimum:

- Unit-level checks for runner result shaping, source/statement caps, SQL statement splitting, permissions, and transaction rollback.
- API checks that Python and SQL scratch endpoints never mutate learning progress/XP and correctly enforce learner/workspace ownership.
- SQL workspace lifecycle checks: create, reuse, reset, expiry, delete, quota, cross-workspace isolation, dataset copy isolation, and server restart behavior.
- Frontend type/build checks and manual flows for scratch switching, pending states, local drafts, keyboard run, errors, truncation, reset confirmation, and expired SQL workspace recreation.
- Regression checks for existing challenge workflows and migration compatibility.

Do not claim the feature passes because endpoints import or because the build succeeds; exercise both happy paths and failure/limit paths.

## 13. Explicit non-goals for v1

- Public multi-user arbitrary-code hosting or an OS-secure sandbox.
- Interactive POSIX/Windows shell, REPL state for Python, notebooks, package installation, internet/network control promises, or collaborative editing.
- Durable cloud sync, user accounts, scratch code history, server-side analytics of submitted code, or long-term file storage.
- Production database connections or SQL dialects beyond SQLite.
- Replacing the Code Quest curriculum with job-placement guarantees.
- Merging the Python and SQL runners or merging scratch execution with challenge grading.

## 14. Existing documentation relationship

`doc.md` is the broader Code Quest architecture/redesign plan and contains detailed existing runner, dataset, and curriculum notes. This document specializes the product and implementation contract for learner-owned Python and SQL scratch workspaces. If future implementation changes a decision here, update this specification and `README.md` so the agent has one current contract rather than conflicting plans.

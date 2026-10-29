# Code Quest — Learning Platform Redesign Plan

**Status:** phase paths, Scratch workspaces, and two-module Code Quest navigation are implemented. This document keeps the design history; `README.md` and `code-quest-workspaces.md` describe the current shipped behavior.
**Date:** updated 2026-10-29
**Scope:** learning module (Python + SQL tracks), sandbox architecture, dataset system, learning frontend.

The implementation specification for separate learner-owned Python and SQL Scratch workspaces is in [code-quest-workspaces.md](code-quest-workspaces.md). That document is the current contract for scratch mode; this file remains the broader learning-platform redesign plan.

---

## 1. Purpose and outcomes

Redesign the learning module so a learner can go from zero to advanced in both Python and SQL, with:

1. **A real progression path** — phases from Foundations through data structures, algorithms, analytics, schema design, performance, and transactions; not a flat list of 10 levels.
2. **Multiple datasets** — four first-class datasets shared by SQL and Python lessons, rotated across phases so repeated practice never feels routine.
3. **One sandbox stack** — SQLite only. No MySQL, no Docker, no server database, no T-SQL.
4. **A Python ↔ SQLite bridge** — Python lessons can query the same seeded database that SQL lessons use.
5. **A third programming language later** — adding a language becomes "add a content pack + a runner", with no engine or frontend rewrite.

---

## 2. Locked decisions

| # | Decision | Consequence |
|---|----------|-------------|
| a | **Delete** the Northwind MySQL challenges and all MySQL plumbing | `northwind_mysql` (~12 challenges) and `northwind_python` (~8 challenges) are removed, along with `northwind.py`, `northwind_curriculum.py`, Docker/env/scripts, and `mysql-connector-python`. Northwind survives as *data* (dataset registry). The legacy `python`/`sql` Foundations tracks stay until the new phase content replaces them. |
| b | **All four datasets first-class** — `northwind`, `streamhub`, `bookings` (messy), `reviews` (JSON) | Shared registry; SQL and Python draw from the same schemas; phases rotate datasets; challenge templates can exist in dataset variants. |
| c | **Python ↔ SQLite bridge in v1** | `python_real` runner opens a read-only copy of the challenge's dataset; guided Python gets the same rows as dicts. |
| d | **SQLite only** | No MSSQL/T-SQL, no dialect layer, no server tier. The runner registry exists for *languages* (Python, SQL, third language), not SQL dialects. |

---

## 3. Verified platform facts

Measured on this machine (`backend\.venv\Scripts\python.exe`):

- **Python's bundled SQLite is 3.50.4** and supports everything the curriculum needs. Verified live: window frames with running totals (`SUM(...) OVER (... ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`), `LAG`/`LEAD`/`NTILE`, `json_extract`, `STRICT` tables (reject wrong types with `IntegrityError`), `EXPLAIN QUERY PLAN`, recursive CTEs.
- **No install needed for SQLite** — `sqlite3` is statically linked into CPython on Windows. The database engine runs inside the backend process. There is no service, no auth, no network, nothing to configure.
- **The backend already runs on the system Python** (venv on top). A "real Python" runner spawns `sys.executable` — the same interpreter.
- **MSSQL is installed but out of scope** (`MSSQLSERVER` service is running, `sqlcmd` present). Decision (d): not used. It is a server you connect to, unlike SQLite which is a library inside the process.

### 3.1 Guided Python interpreter — current capabilities and limits (`learning.py:699–1060`)

| Area | Supported today | Missing (needed by phases 2–6) |
|------|-----------------|-------------------------------|
| Statements | assignment, `AnnAssign`, `AugAssign`, `if/elif/else`, `for` (list/tuple/dict/range, ≤1,000 items, no `else`), `def` (named args only), `return`, `pass` | `while`, `break`, `continue`, slicing, `try/except/finally`, `raise`, `assert` |
| Builtins | `print`, `range`, `len`, `sum`, `min`, `max`, `sorted`, `round`, `int`, `float`, `str`, `bool`, `list`, `dict`, `enumerate`, `zip`, `abs` | sets, comprehensions, f-strings (verify), `map`/`filter`, `join` |
| Methods | `list.append/count`, `dict.get/keys/values/items`, `str.lower/upper/strip/title` | `str.split/join/replace/startswith/endswith/find`, `list.sort/pop/index/remove/extend/reverse`, set methods |
| Limits | 10,000 execution ticks; 5,000 output chars; collections ≤ 1,000 items; call depth 12; display depth 64 | per-challenge overrides for efficiency lessons |

### 3.2 SQL sandbox today (`_sql_result`, `learning.py:1218–1282`)

- Per-run `sqlite3.connect(":memory:")` seeded from the challenge's inline `datasets` rows.
- Gate: `^(SELECT|WITH)\b` only (`:1233`).
- Authorizer allows `SQLITE_SELECT`, `SQLITE_READ`, `SQLITE_RECURSIVE` + a small function whitelist (`:1253–1263`): `abs, avg, coalesce, count, ifnull, length, lower, max, min, nullif, round, sum, upper, rank, row_number`.
- 20,000-step progress handler (`:1266`); limits: length 100,000 / SQL 5,000 / column 64 (`:1238–1241`); 100-row result cap (`:1269–1271`).

**Three upgrades required for advanced SQL** (see §6.1): allow `EXPLAIN`, expand the function policy, add scratch-write mode.

---

## 4. Current system audit (as-is)

### 4.1 Backend learning engine — `backend/learning.py`

| Piece | Location | Fate |
|-------|----------|------|
| `TRACKS` registry | `:31` | Replaced by phase packs |
| `_challenge_difficulty` / `_challenge_xp` (index-based) | `:666–675` | Replaced by metadata on phases/challenges |
| Guided interpreter `_python_output` | `:699+` | Kept as `python_guided`, extended, retired after Python phase 6 |
| `_python_shape_error(source, level)` | `:1063` | Replaced by named checks (`uses_*`) |
| `_sql_result` | `:1218–1282` | Kept as `sqlite` runner, upgraded |
| `_sql_shape_error(source, level)` | `:1285–1302` | Replaced by named checks |
| `_run_challenge_code` if/elif on track id | `:1312+` | Replaced by `RUNNERS[runner]` dispatch |
| Unlock rule `level > len(completed)` | `:1393` | Replaced by server-computed phase unlock |
| Stable-id progress writes | `:1408–1418` | Kept — new phases use stable challenge ids |
| `_northwind_data` (MySQL rows for Python) | `:1305–1309` | Replaced by `_dataset_rows(dataset_id)` from the registry |
| Northwind branch in runner (`:1342–1349`), error handling (`:1367–1375`), badges (`:1421`), `CURRICULA` (`:1534`) | | Deleted with MySQL |

### 4.2 Frontend learning today

- `LearnPage.tsx` — session, drafts, hints, mutations, and language-module scoping. A `module` prop limits the visible tracks to the selected language; Python and SQL track state and progress IDs stay separate.
- `codeQuestModules.ts` — shared module definitions for Python, SQL, and the cross-language Case Files project, including canonical Path/Scratch routes and default track IDs.
- `CodeQuestNav.tsx` — two language-module cards (Python, SQL), each with Path and Scratch tabs, plus a separate Case Files project link. Active state follows the URL.
- `ChallengeExplorer.tsx` — groups path challenges by the optional phase `stage` metadata first, then by phase. Tracks without stages keep the existing tier/phase grouping.
- `SqlWorkbench.tsx` — shared challenge workbench composition despite the SQL-oriented filename. It receives only the current module's tracks and totals, rather than every Python and SQL track.
- `LearningOutputPanel.tsx` — shared result, hints, review, and capstone presentation.
- `types/index.ts` — track IDs are strings; track languages include `python`, `sql`, and `mixed`; phases carry optional `stage` metadata.

---

## 5. Target architecture

```
Frontend (React)
   |  GET /api/learning/session            (tracks -> phases -> challenges, progress, datasets)
   |  POST /api/learning/run               (dispatch by runner tag)
   |  GET /api/learning/datasets           (registry metadata for SchemaNavigator)
   v
Learning API (main.py -> learning.py)
   |
   +-- Progression engine      phases, unlock, checkpoints, review queue, progress by stable id
   +-- Content packs           backend/curriculum/*.py — pure data + factories (no engine edits)
   |      +-- Dataset registry backend/datasets/*.py — DDL + deterministic seeders + metadata
   +-- Runner registry         RUNNERS = { "python_guided", "python_real", "sqlite" }
          +-- python_guided   in-process AST interpreter (phases 1–6)
          +-- python_real     sys.executable -I subprocess + scratch dir + bridge DB (phases 7–14)
          +-- sqlite          in-memory SQLite, readonly | scratch modes (all SQL phases)
```

### 5.1 Data model (sketch)

```python
Phase = {
    "id": "py-04-collections", "track_id": "python", "order": 4,
    "name": "Collections", "arc": "Working with data",
    "summary": "...",
    "unlock_after": "py-03-functions", "min_percent": 70,
    "checkpoint": "py-04-checkpoint",        # closing challenge id
    "datasets": ["northwind", "streamhub"],  # rotation pool for this phase
}

Challenge = {
    "id": "py-04-03-dict-count",             # stable id (progress key)
    "phase_id": "py-04-collections", "order": 3,
    "title": "...", "brief": "...", "starter": "...", "hints": [...],
    "plan": ["...", "..."],                  # free pseudo-code steps (never a hint)
    "predict": {"prompt": "...", "code": "...", "options": [...], "answer": 0, "why": "..."},
    "runner": "python_guided",               # python_guided | python_real | sqlite
    "dataset": {"id": "northwind", "tables": ["customers"], "size": "small"},
    "mode": "readonly",                      # sqlite only: readonly | scratch
    "checks": ["uses_loop", "matches_reference"],
    "reference": "<private solution, never sent to client>",
    "variants": [                            # optional dataset flavors
        {"dataset": "streamhub", "reference": "<private>"},
    ],
    "efficiency": {"max_steps": 5000},       # or {"max_seconds": 1.5} for python_real
}
```

### 5.2 Grading model

- **Execution-based:** checks run the *reference solution* live against the same dataset as the learner's attempt and compare results (multiset compare by default; ordered compare when the task says `ordered: true`).
- **Named checks** replace level-keyed shape errors. Initial check library:

| Check | Meaning |
|-------|---------|
| `matches_reference` | Result equals reference output on the same dataset |
| `uses_window` / `uses_join` / `uses_cte` / `uses_loop` / `uses_recursion` | Structural requirement (AST for Python, SQL text normalize for SQL) |
| `no_hardcoded_output` | Re-runs the solution against variant inputs (generalizes `_test_variants`) |
| `efficiency` | Step count (guided) or wall clock / scale ratio (real) within threshold |
| `constraint_rejected` | Scratch-mode: a bogus write must have been rejected by the schema (e.g., CHECK) |
| `table_state` | Scratch-mode: final table contents/counts match expectations |
| `quiz` | Multiple choice (keeps the legacy quiz mechanic) |

- **Private answers stay server-side**, as in `northwind_curriculum.py` today.

### 5.3 Progression model

- Challenge progress keyed by stable id (mechanism already exists, `learning.py:1408–1418`).
- A phase unlocks when the previous phase's checkpoint is cleared (or `min_percent` of its challenges + checkpoint — tune in slice 4).
- **Unlock is computed server-side** and shipped in the session payload; the frontend only renders lock states (removes the duplicated rule in `LearnPage.tsx:136` and `ChallengeExplorer.tsx:81`).
- After each phase: a short **review set** (see §9) and the **phase checkpoint**.

---

### 5.4 Code Quest navigation

Code Quest exposes exactly two language modules. Each module contains its own guided Path and Scratch workspace:

| Module | Path | Scratch |
|---|---|---|
| Python | `/learn/python/path` | `/learn/python/scratch` |
| SQL | `/learn/sql/path` | `/learn/sql/scratch` |

`/learn` redirects to `/learn/python/path`. The old `/learn/scratch/python` and `/learn/scratch/sql` routes redirect to the matching module Scratch route. The hybrid Case Files path stays a single cross-language project at `/learn/case-files`; it does not become a third language module. Python and SQL tracks, execution runners, drafts, progress identities, and workspace lifecycle remain separate.

---

## 6. Runner and sandbox specification

### 6.1 `sqlite` runner (upgrade of `_sql_result`)

**Modes:** per-challenge `mode: "readonly" | "scratch"`.

- `readonly`: exactly today's safety posture, plus upgrades below.
- `scratch`: CREATE TABLE / INSERT / UPDATE / DELETE / DROP allowed on the **disposable in-memory DB**; grading reads final state via `constraint_rejected` / `table_state` checks. Always denied in both modes: `ATTACH`/`DETACH` (file access), `PRAGMA` writes, `load_extension` (`fts3_tokenizer`, `readfile`, `writefile` denylisted belt-and-braces).

**Exact changes vs today:**

| # | Change | Where |
|---|--------|-------|
| 1 | Leading-keyword gate becomes `^(SELECT|WITH|EXPLAIN|VALUES)\b` (EXPLAIN stays read-only) | `learning.py:1233` |
| 2 | Function policy: allow all functions **except** a small denylist (`load_extension`, `fts3_tokenizer`, file I/O), instead of the 15-name allowlist | `learning.py:1253–1263` |
| 3 | Scratch mode: allow DML/DDL statement types in the authorizer; multi-statement execution (split with `sqlite3.complete_statement`); readonly keeps single statement | authorizer + executor |
| 4 | Per-challenge knobs: `row_cap` (default 100), `step_cap` (default 20k), `time_cap_ms` (wall-clock guard added inside the progress handler), `size` tier | challenge config |
| 5 | Dataset seeding moves from inline `datasets` rows to the registry (`datasets.connect(dataset_id, size)`) | `_sql_result` |

**Why this is enough for all 10 SQL phases:** verified SQLite 3.50.4 covers windows, CTEs, recursive CTEs, JSON, EXPLAIN QUERY PLAN, STRICT tables, transactions. Performance lessons use EXPLAIN QUERY PLAN + wall-clock timing on generated tables. Server-admin topics (roles, backups, HA, stored procedures) are out of scope by decision (d).

### 6.2 `python_guided` runner (extend, then retire)

Extensions required for phases 2–6 (keep the friendly error style):

1. `while` loops (tick-limited), `break`, `continue`.
2. Slicing (`items[1:3]`, `text[::-1]`).
3. String methods: `split`, `join`, `replace`, `startswith`, `endswith`, `find` (+ optional f-strings).
4. List methods: `sort`, `pop`, `index`, `remove`, `extend`, `reverse`; set support (`set`, `add`, `union`, `intersection`).
5. Comprehensions: list and dict.
6. `try/except/finally`, `raise`, `assert`.
7. Optional: function defaults (currently rejected at `learning.py:1043`).
8. Per-challenge overrides for `tick` budget and output cap.

After phase 6, new content uses `python_real`; the interpreter is kept only for the legacy Foundations levels until they are replaced.

### 6.3 `python_real` runner (new)

- **Process model:** parent spawns `[sys.executable, "-I", harness.py, source.py]` in a fresh `tempfile.mkdtemp()` scratch dir. `-I` = isolated (no `PYTHON*` env vars, no user site, script dir not on path).
- **Harness:** captures stdout/stderr, runs learner code, emits a JSON result (output, error + line, duration). Parent enforces timeout (`subprocess.run(timeout=...)`, default 5 s, per-challenge override) and kills the process on expiry.
- **Scratch dir:** seed fixture files for file lessons (e.g., `sales.csv`); learner-written files land here; checks read them back; dir cleaned after each attempt.
- **Efficiency checks:** wall-clock threshold on a fixed fixture (e.g., "search 100k rows in < 0.5 s") and an optional scale test (run at N and 5N; fail if time ratio > ~10, i.e., not linear-ish). Thresholds live in challenge data and are calibrated generously.
- **Honest limitations (documented, accepted for a local single-user app):** not an OS-level security boundary; imports are available. Best-effort guardrails: isolated mode, timeout, scratch dir, static screen for obviously destructive imports (`os.system`, `subprocess`, `shutil.rmtree`) with clear lesson feedback. No network restriction at OS level.

### 6.4 Python ↔ SQLite bridge (v1, decision c)

- For bridge lessons, the runner seeds the challenge's dataset into `<scratch>/learning.db` and injects a documented `DB_PATH` global.
- Learner connects with the standard library:
  ```python
  import sqlite3
  db = sqlite3.connect(f"file:{DB_PATH}?mode=ro&immutable=1", uri=True)
  rows = db.execute("SELECT ... FROM streamhub_events ...").fetchall()
  ```
- The file is opened **read-only** (`mode=ro`) and created read-only, so learner Python cannot corrupt the shared fixture.
- Guided mode gets the same rows as dicts via `_dataset_rows(dataset_id)` (replacement for `_northwind_data`), so SQL and Python lessons use identical table/column names.

---

## 7. Dataset registry

### 7.1 Registry design

New package `backend/datasets/`:

```
backend/datasets/
  __init__.py     # DATASETS registry, connect(dataset_id, size), schema_metadata()
  northwind.py    # static seed rows converted from the old dump (curated columns)
  streamhub.py    # deterministic generator
  bookings.py     # deterministic generator (messy extract)
  reviews.py      # deterministic generator (text + JSON attributes)
```

```python
@dataclass
class Dataset:
    id: str
    name: str
    summary: str
    ddl: str                       # CREATE TABLE statements (SQLite dialect)
    tables: dict[str, TableMeta]   # columns, types, keys, grain -> drives SchemaNavigator
    sizes: dict[str, Ranking]      # {"small": {...rows}, "perf": {...rows}}
    seed: Callable[[sqlite3.Connection, str], None]   # deterministic, seeded RNG

def connect(dataset_id: str, size: str = "small") -> sqlite3.Connection: ...
```

- **Deterministic:** fixed RNG seeds → identical data every run → stable grading and cacheable fixtures.
- **On demand:** small tiers generate per attempt (milliseconds); perf tiers only for performance/efficiency lessons.
- **Row budgets:** each challenge declares the dataset + size; runs stay fast.
- **Optional optimization (only if needed):** dump the seeded perf-tier DB to a temp file once and reuse (immutable) across attempts.

### 7.2 The four datasets

| id | Theme | Small tier | Perf tier | Powers |
|----|-------|-----------|-----------|--------|
| `northwind` | Classic business schema (curated columns from the old dump) | ~3k rows | 50k | SQL 1–3 warm-ups; Python dict basics |
| `streamhub` | Streaming/SaaS product | ~2k users, 8k subs, 30k invoices, 50k events | 500k events, 200k invoices | SQL 3–6, 8–10; Python 7–14; cohorts, retention, funnels, MRR/churn, sessionization |
| `bookings` | One deliberately dirty denormalized hotel table | ~2k rows | — | SQL 7, 9 (scratch DDL); data cleaning in SQL and Python |
| `reviews` | Review text + JSON attributes | ~5k rows | 50k | JSON1 in SQL; `json`/text/regex in Python; review-driven variety |

**StreamHub schema sketch** (column lists abbreviated):

```
users(id PK, name, email, country, city, signup_date, acquisition_channel, birth_year)
plans(id PK, name, tier, monthly_price_cents, currency)
subscriptions(id PK, user_id FK, plan_id FK, started_at, ended_at NULL, status, coupon_code NULL)
invoices(id PK, subscription_id FK, issued_at, amount_cents, currency, paid_at NULL, status)
events(id PK, user_id FK, event_type, content_id NULL, occurred_at, device, session_id)
contents(id PK, title, genre, release_year, duration_minutes, rating)
support_tickets(id PK, user_id FK, opened_at, closed_at NULL, category, priority, satisfaction_score NULL)
campaigns(id PK, name, channel, started_at, ended_at, spend_cents, target_country NULL)
```

Built-in realism: NULLs (`ended_at`, `paid_at`, `closed_at`, `satisfaction_score`), churned subscriptions, unpaid/overdue invoices, duplicate and late-arriving events, sessions that need gap-and-island logic.

**Bookings schema sketch (messy on purpose):**

```
bookings_raw(booking_ref, guest_name, email NULL, phone, hotel_name, hotel_city,
             room_type, check_in TEXT (mixed date formats), check_out TEXT, nights,
             rate_text, promo_code NULL, notes NULL)
```

Dirty features: mixed date formats, inconsistent casing/whitespace, duplicate refs, missing emails, promo-code typos, phone-format variance, `nights` that sometimes disagrees with the dates.

**Reviews schema sketch:**

```
reviews(review_id PK, product_id, product_name, reviewer, rating,
        review_text, attributes JSON TEXT, created_at, verified)
```

`attributes` example: `{"size": "M", "color": "blue", "helpful_votes": 4, "photos": 2}`.

**Northwind conversion:** at removal time, the curated subset is extracted from `northwind.sql` (same column list the old learning views exposed: categories, customers, employees, employeeterritories, orderdetails, orders, products, shippers, suppliers, territories) and re-emitted as SQLite DDL + literal INSERTs in `backend/datasets/northwind.py`.

---

## 8. Curriculum maps

### 8.1 Python — 14 phases

| # | Phase | Topics | Runner | Datasets |
|---|-------|--------|--------|----------|
| 1 | Foundations | values, variables, `print`, arithmetic, comments | guided | northwind |
| 2 | Control flow | `if/elif/else`, logic operators, `for` + `range`, `while`, `break/continue` | guided* | northwind, streamhub |
| 3 | Functions | `def`, parameters, `return`, scope, defaults, docstrings | guided* | northwind, streamhub |
| 4 | Collections | lists, tuples, dicts, sets, indexing/slicing, mutation, comprehensions | guided* | streamhub, reviews |
| 5 | Text & strings | methods, f-strings, split/join, searching, light regex | guided*/real | reviews |
| 6 | Errors & debugging | tracebacks, `try/except/finally`, `raise`, assertions | guided*/real | reviews, bookings |
| 7 | Files & data | CSV/JSON in a scratch dir, path handling, the SQLite bridge | real | bookings, reviews |
| 8 | Stdlib & modules | imports, math/random/datetime/collections/itertools, pip & venv concepts | real | streamhub |
| 9 | OOP | classes, attributes/methods, dataclasses, dunders, composition vs inheritance | real | streamhub |
| 10 | Iterators & generators | `yield`, laziness, `map/filter/sorted` keys, itertools patterns | real | streamhub |
| 11 | Testing & quality | assert-style tests, unittest/pytest structure, type hints, refactoring | real | streamhub, bookings |
| 12 | Data structures | stacks, queues (`deque`), linked lists, hash maps from scratch, BST, heaps, graph adjacency | real + efficiency | reviews, bookings |
| 13 | Algorithms | big-O, searching, sorting, two pointers, sliding window, prefix sums, recursion → memoization → DP intro, BFS/DFS, greedy | real + efficiency | streamhub fixtures |
| 14 | Applied projects | CLI tools, a pipeline over StreamHub, text processing, capstone + mixed review | real | streamhub |

`*` = requires the §6.2 interpreter extensions.

### 8.2 SQL — 10 phases

| # | Phase | Topics | Sandbox |
|---|-------|--------|---------|
| 1 | Foundations | SELECT, WHERE, ORDER BY, LIMIT, operators, aliases, NULL basics | sqlite readonly |
| 2 | Aggregation | COUNT/SUM/AVG, GROUP BY, HAVING, DISTINCT, CASE WHEN | sqlite readonly |
| 3 | Joins & row grain | INNER/LEFT, self-joins, join chains, fan-out/grain discipline | sqlite readonly |
| 4 | Subqueries & CTEs | scalar/IN/EXISTS/correlated, derived tables, CTEs, recursive CTEs | sqlite readonly |
| 5 | Window functions | ROW_NUMBER/RANK/DENSE_RANK/NTILE, LAG/LEAD, frames, running totals, moving averages | sqlite readonly |
| 6 | Analytics patterns | top-N per group, dedupe-keep-latest, gaps & islands, cohort retention, funnels, period-over-period, pivots via CASE, RFM | sqlite readonly |
| 7 | Schema design & DDL | types, PK/FK/UNIQUE/CHECK/DEFAULT, 1NF→3NF, views, index basics | sqlite scratch |
| 8 | Performance | EXPLAIN QUERY PLAN, composite & covering indexes, sargability, avoiding `SELECT *`, join strategy, rewrites | sqlite (perf tier) |
| 9 | Transactions & reliability | BEGIN/COMMIT/ROLLBACK, atomicity, constraints as guardrails, isolation concepts | sqlite scratch |
| 10 | Case studies & review | multi-step business analyses, mixed review, capstone reports | sqlite, all datasets |

### 8.3 Phase anatomy and authoring rules

- Every phase: 6–10 challenges + 1 checkpoint + a review set.
- Content lives in `backend/curriculum/` as pure-data modules composed from factories (`f_phase`, `f_sql`, `f_python`, `f_quiz`) — no engine edits per challenge.
- Reference solutions and expected outputs are private (server-side only), as in `northwind_curriculum.py` today (whose `_sql_challenge` / `_python_challenge` + behavioral grading + `_test_variants` pattern is the template to generalize).
- Difficulty is a display badge, not a grouping key.

---

## 9. Variety mechanism ("not routine, not predictable")

Three layers, increasing in cost:

1. **Dataset rotation** — phases declare a rotation pool (`northwind`, `streamhub`, `bookings`, `reviews`); consecutive phases and neighboring challenges rarely reuse the same data. Same skill, different shape.
2. **Dataset variants per template** — a challenge authored once can be instantiated in 2–4 flavors (`variants: [{dataset, reference}]`). Grading is execution-based, so a variant only needs a re-run of its reference.
3. **Mixed practice queue** — after each phase, a review set resurfaces earlier skills as *random variants across datasets*, so repetition never replays the same card. Sits alongside the normal path (a "Practice" section), plus one checkpoint per phase.

Not in scope: fully generated challenges (grading would become fragile). Variety comes from authored templates × datasets × review scheduling.

---

## 10. MySQL removal plan

### 10.1 Backend inventory

| Remove | Location |
|--------|----------|
| `northwind.py` (connection, schema, `run_query`, `expected_result`, `referenced_learning_tables`, `load_table_rows`) | `backend/northwind.py` |
| `northwind_curriculum.py` (~20 challenges, curriculum, concepts) | `backend/northwind_curriculum.py` |
| MySQL init/reader scripts | `backend/mysql/` (whole dir) |
| Imports, `TRACKS.update`, `public_schema`, `_northwind_data`, runner branches, error handling, badges, `CURRICULA` | `backend/learning.py` `:16–19, :469, :618, :1305–1309, :1320–1321, :1342–1349, :1367–1375, :1421, :1534` |
| Northwind docstring | `backend/main.py:691` (verify remaining route wiring) |
| `mysql-connector-python` | `backend/requirements.txt:33–34` |
| Northwind env vars | `backend/.env.example:5–6, :18–24` (+ local `.env` cleanup if present) |

### 10.2 Frontend inventory

| Remove / change | Location |
|-----------------|----------|
| Track/curriculum unions | `frontend/src/types/index.ts:12–13` |
| Default track name | `LearnPage.tsx:207` |
| Track id type + "up to 100 rows" copy | `ChallengeBrief.tsx:7, :91` |
| Northwind aria label | `ChallengeExplorer.tsx:49` |
| Northwind branches | `LearningOutputPanel.tsx:61–62, :91` |
| `isMySQLTrack`, curriculum selector, MySQL labels | `SqlWorkbench.tsx:46–47, :53, :101–121, :189, :199, :330` |
| Track-id selection | `LearningWorkspace.tsx:42–43, :53–54, :60` |
| Wrapper | `PythonWorkbench.tsx` (deleted after workbench refactor) |

### 10.3 Deploy / docs / deps

- Delete: `northwind.sql` (root), `docker-compose.northwind.yml`, `.env.northwind.example`.
- Update: `README.md` (Northwind sections), `run.txt`, regenerate `structure.txt`.

### 10.4 Content deletion and gap mitigation

- Deleted: `northwind_mysql` (~12 SQL challenges) and `northwind_python` (~8 Python challenges), plus the `northwind_data` curriculum.
- The skills they taught are covered again by the new phases (§8) with broader variety.
- **Gap mitigation:** the legacy `python`/`sql` Foundations tracks (levels 1–10) remain operational and independent of MySQL, so the learning feature stays usable while new phase content lands incrementally (slice 5).
- Order of work keeps slices 2 and 5 close together; first new phases (SQL 1–4, Python 1–6) land before lower-priority content.

---

## 11. Frontend work plan

1. **Types** — replace hardcoded unions with string ids + capability descriptors (`runner`, `language`, `mode`, dataset info). `language` becomes `string`.
2. **Explorer** — group by phase (collapsible sections with progress), difficulty as a card badge, lock states from the session payload only.
3. **Workspace selection** — choose the workbench by `runner` tag (`sqlite` / `python_guided` / `python_real`) instead of track id; fold `PythonWorkbench.tsx` into the shared component; drop `isMySQLTrack` and the curriculum selector.
4. **SchemaNavigator** — fed by `GET /api/learning/datasets` (registry metadata: tables, columns, keys, grain, which dataset the challenge uses).
5. **Run output** — SQL scratch mode shows each executed statement's result; remove Northwind branches.
6. **Practice section (slice 6)** — mixed review sets + checkpoint entry points.

---

## 12. Build order (slices)

Each slice is independently testable. Backend checks run via `backend\.venv\Scripts\python.exe` with workdir `backend` (so `import main` resolves); frontend builds use `npm.cmd run build` (PowerShell blocks `npm.ps1`).

### Slice 1 — SQLite sandbox upgrades + dataset registry
- Deliverables: `backend/datasets/` package with all four datasets; upgraded `sqlite` runner (EXPLAIN gate, function policy, scratch mode, per-challenge caps); Northwind converter.
- Verify: window query with LAG/LEAD/NTILE passes; `EXPLAIN QUERY PLAN` returns a plan; scratch CREATE+INSERT+SELECT works; a CHECK violation is observable; ATTACH and PRAGMA writes stay blocked; a 100k-row scan completes with raised caps but still hits the wall-clock guard if runaway.

### Slice 2 — MySQL removal + cleanup
- Deliverables: files removed, `learning.py`/`main.py` cleaned, requirements/env/docs updated, frontend references removed, `structure.txt` regenerated.
- Verify: `py_compile` + `import main`; `GET /api/learning/session` returns tracks with no Northwind; grep for `northwind|mysql` is clean; `npm.cmd run build` passes.

### Slice 3 — `python_real` runner + bridge + guided interpreter extensions
- Deliverables: subprocess runner (isolation, timeout, scratch dir, harness), read-only SQLite bridge (`DB_PATH`), interpreter extensions per §6.2.
- Verify: recursion + file writing work; bridge query against `streamhub` returns rows; infinite loop is killed at timeout; `no_hardcoded_output` rerun works; guided phase-2 constructs all execute.

### Slice 4 — phase metadata + explorer + session model
- Deliverables: phases in the session payload, server-side unlock, phase-grouped explorer, runner-based workspace selection, dataset endpoint.
- Verify: unlock behaves per phase rules; legacy tracks still render and run; explorer shows phases and badges.

### Slice 5 — content authoring (SQL phases 1–10, Python phases 1–14)
- Deliverables: phases as data in `backend/curriculum/`, checkpoints, hint/starter/reference content, variants.
- Order: SQL 1–4 → Python 1–6 → SQL 5–8 → Python 7–11 → SQL 9–10 → Python 12–14.
- Verify: golden-path smoke per phase (reference solution clears every challenge; a wrong attempt fails with the right feedback).

### Slice 6 — mixed review queue + checkpoints
- Deliverables: review sets after phases, Practice section, spaced resurfacing across datasets; checkpoint wiring into capstone/portfolio flow.
- Verify: a review set draws variants from earlier phases; checkpoint gating works.
- Status: the Practice review queue shipped with slice 8 (hint-first + spaced resurfacing, mixed across tracks). Cross-dataset variants for resurfacing still need authored variant content.

### Slice 7 — third language pack (later)
- A new language = one runner module + one dataset/fixture strategy + one phase pack + a capability descriptor. Engine and frontend need no changes beyond labels.

### Slice 8 — learning aids and practice (pilot shipped)
- **Pseudo-code plans** — `challenge(plan=[...])` stores plain-prose steps with no syntax. A plan renders free in the Hints tab: reading it never counts as a hint and never costs the mastery badge. Pilot content: Python phase 1 + SQL phase 1; all other challenges default to `plan=[]` until the rollout pass.
- **Error-pattern coaching** — failed submissions get targeted notes from `backend/coaching.py`: SQL `= NULL` / `!= NULL`, `HAVING` without `GROUP BY`, `SELECT *` column drift; Python `== None`, print-only functions where the reference returns a value, unchanged starter code. Detectors stay deliberately conservative and notes are additive to the regular feedback string.
- **Predict-the-output drills** — `challenge(predict={prompt, code, options, answer, why})` renders an optional warm-up card in the challenge brief (local-only, no XP, no badge impact). Pilot: four drills in phase 1.
- **Mixed review queue** — `POST /api/learning/review` selects up to 5 completed challenges per learner: hint-assisted completions first, then the oldest ones; each track's newest completion is skipped and the set alternates tracks. A PRACTICE card in the navigator opens the challenge directly — re-solving a cleared challenge awards no XP and no extra badge.

---

## 13. Non-goals

- No MSSQL/T-SQL track, no SQL dialect layer (decision d).
- No server database, Docker, or external services for learning.
- No server-admin content (roles, backups, HA, stored procedures).
- No fully generated challenge content; variety comes from authored templates and datasets.
- No changes to non-learning features (tools and PDFs) beyond what removal cleanup requires.

---

## 14. Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Content volume (24 phases) is the long pole | Factories + dataset variants reduce authoring cost; ship phase by phase; combined with slice 4 metadata, partial content still looks coherent |
| Content gap after deleting Northwind challenges | Legacy Foundations tracks stay live; slice 5 starts immediately with SQL 1–4 and Python 1–6 |
| `python_real` is not an OS security boundary | Accepted for a local single-user app; isolated mode, timeout, scratch dir, static import screen, clear documentation |
| Relaxed SQL function policy | Authorizer still denies ATTACH/DETACH/PRAGMA writes/non-read actions in readonly; `load_extension` off; denylist for historical footguns |
| Perf-check flakiness on slow machines | Guided step counts primary; generous wall-clock thresholds; scale-ratio test optional and generous; thresholds in challenge data |
| Progress migration legacy → phases | Stable-id progress already exists; legacy levels keep the index scheme until replaced |
| Perf-tier seeding cost | Size tiers; only perf lessons use big tiers; optional cached immutable DB file |

---

## 15. Appendix A — completed fix round (in working tree, uncommitted)

From the previous review round (all verified, none committed):

- Level cap removed (`le=10` in `backend/main.py`); bounds now enforced by `learning.py`.
- PDF sign tool completed: three JSON routes (`/api/pdf/pdf-sign/preview`, `/page/{token}`, `/apply`), new `frontend/src/features/tools/PdfSignTool.tsx` (upload → click-to-place → draw/type/upload signature → apply → download), `PdfDownload`/`PdfSignPreview` types + apiClient functions; end-to-end smoke passed.
- `PDF_PAGES` trimmed to tools with real templates; import-time assert extended; `tool.html` now `{% include content %}`; `tool_content.html` ready-tool copy; legacy pages return 200.
- Frontend: ``LearningOutputPanel` real tab states + `[hidden]` fix; ChallengeBrief chip spacing; `CatalogPage` track count derived; dead `LearningWorkbench.tsx` removed.
- Docs/config: `structure.txt` regenerated; stale note removed from `run.txt`; `backend/.env.example` created.
- Verification: `py_compile`, `import main` asserts, sign smoke test, legacy template renders, `npm.cmd run build` all pass.

## 16. Appendix B — key file map

| File | Role |
|------|------|
| `backend/learning.py` | Engine: track registry (legacy + paths), session/progress/XP, runner dispatch, unlock rules |
| `backend/guided_python.py` | Guided Python interpreter shared by legacy and path challenges |
| `backend/sql_runner.py` | SQLite sandbox: readonly + scratch modes, authorizer, row/step/time caps |
| `backend/python_runner.py` | Real CPython subprocess runner, fixtures, Python ↔ SQLite bridge |
| `backend/datasets/` | Dataset registry + four deterministic seeded datasets (northwind, streamhub, bookings, reviews) |
| `backend/curriculum/` | Phase packs, factories, private references, checks, pluggable runners |
| `backend/curriculum/phases_python.py` | Python path: 14 phases, 72 challenges, three stage labels |
| `backend/curriculum/phases_sql.py` | SQL path: 10 phases, 50 challenges |
| `backend/curriculum/phases_case_files.py` | Cross-language Case Files project (SQL + Python) |
| `backend/main.py` | Learning API routes (session/event/solution/answer/code/preview/scratch) |
| `frontend/src/features/learning/LearnPage.tsx` | Learn state, drafts, hints, mutations, language-module scoping |
| `frontend/src/features/learning/codeQuestModules.ts` | Python/SQL module definitions, routes, track scoping |
| `frontend/src/features/learning/components/SqlWorkbench.tsx` | Shared runner-driven challenge workbench (scoped to one language module) |
| `frontend/src/features/learning/components/ChallengeExplorer.tsx` | Stage → phase explorer for path tracks; tier groups for legacy |
| `frontend/src/features/scratch/CodeQuestNav.tsx` | Two language modules with Path/Scratch plus Case Files project link |
| `frontend/src/features/learning/components/SchemaNavigator.tsx` | Dataset explorer fed by `session.datasets` |
| `frontend/src/types/index.ts` | Learning types generalized (track ids are strings, phases may carry a stage) |
| `structure.txt`, `run.txt`, `README.md` | Docs regenerated/updated |

MySQL integration files (`backend/northwind.py`, `backend/northwind_curriculum.py`, `backend/mysql/`, `northwind.sql`, `docker-compose.northwind.yml`, `.env.northwind.example`) were deleted; Northwind now ships as a dataset.

---

## 17. Appendix C — extending the platform (implemented recipe)

Adding a new learning path is a **data change, not an engine change**. The
auto-discovery and runner registry make a future ML path (or a third language)
a drop-in addition:

1. **Author the content pack.** Create `backend/curriculum/phases_<name>.py` and
   export a `PATH` built with `helpers.challenge()` / `helpers.phase()` /
   `helpers.path()`. Optional `ORDER = <int>` controls UI ordering. The pack is
   discovered automatically on startup — `phases_*.py`, nothing else to touch.
2. **Register a runner (only if the execution profile is new).** Map a runner
   name to a grading function with `grading.register_runner("python_ml", fn)`,
   or reuse `sqlite` / `python_guided` / `python_real`. A runner is any function
   `(challenge, source) -> (output, correct, feedback, sql_columns, sql_rows,
   error_line, error_column)`.
3. **Reuse the shared datasets.** The four seeded SQLite datasets and their
   metadata (schema navigator, `DB_PATH` bridge) are shared by every runner;
   new datasets are single modules dropped into `backend/datasets/`.
4. **Nothing else changes.** Sessions, unlock/progression, XP, hints, plans,
   predict drills, coaching notes, the review queue, drafts, previews, solution
   walkthroughs, and the phase explorer all work from the exported `PATH` as-is.

Worked example (future ML path):

```python
# backend/curriculum/phases_ml.py
from .helpers import challenge, path, phase

ORDER = 30

PHASE_1 = phase(
    "ml-1-foundations",
    "Data Foundations",
    "Warm-up",
    "Load, inspect, and describe the shared datasets with pandas.",
    [
        challenge(
            "ml-01-01",
            "Load the frame",
            "pandas",
            "Load the products table with pandas through the SQLite bridge and print its shape.",
            "import pandas as pd\nimport sqlite3\n\n# your code here\n",
            "import pandas as pd\nimport sqlite3\n\nconnection = sqlite3.connect(DB_PATH)\ndf = pd.read_sql_query(\"SELECT * FROM products\", connection)\nconnection.close()\nprint(df.shape)",
            hints=["Start by loading the table."],
            plan=[
                "Load the products table through the SQLite bridge.",
                "Print the shape of the frame.",
            ],
            predict={
                "prompt": "What does df.shape print for a table with 77 rows and 10 columns?",
                "code": "print(df.shape)",
                "options": ["(77, 10)", "77", "[77, 10]"],
                "answer": 0,
                "why": "shape is a (rows, columns) tuple.",
            },
            success="You loaded your first frame.",
            runner="python_ml",  # registered via grading.register_runner
            dataset={"id": "northwind"},
        ),
    ],
)

PATH = path("ml_path", "ML Path", "From tables to models.", "python", [PHASE_1])
```

```python
# In a module inside backend/curriculum/ (or alongside a pack):
from . import grading

def grade_python_ml(challenge, source):
    ...

grading.register_runner("python_ml", grade_python_ml)
```

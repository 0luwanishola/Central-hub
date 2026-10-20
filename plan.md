# The Case Files — Hybrid Python + SQL Mystery Game Plan

**Status:** Slices 0–2 implemented (2026-10-16) — Case 1 ("The StreamHub Swindle") is playable as the "The Case Files" track; Slices 3–5 pending.
**Date:** 2026-10-16
**Scope:** a new learning path (Case Files) for Code Quest plus a future free-roam "Case Files mode" feature, built on the existing engine (`learning.py`, `curriculum/`, `datasets/`, `sql_runner.py`, `python_runner.py`), with Python + SQL used side by side inside one detective story.

---

## 1. Origin and purpose

Inspired by [The SQL Murder Mystery](https://mystery.knightlab.com) (Knight Lab, Northwestern): clues spread across database tables, solved by querying, verified with an accusation. The goal here is a **hybrid**: the same case is solved with SQL (records, ledgers, joins) and Python (forensics: file artifacts, logs, anomaly scans) inside Central Hub's Code Quest platform.

The design principle borrowed from the original: **the story lives in the data**. Prose is a wrapper; the deduction chain is the game.

Three product decisions are locked from the design discussion:

| # | Decision | Consequence |
|---|----------|-------------|
| a | **Staged rollout (Option D)** | Ship as a Mystery Path content pack first (zero engine changes), then grow into a free-roam Case Files mode feature reusing the same datasets and content. |
| b | **Four cases as a series** | One case per phase, difficulty ramping 1→4. Nothing authored is throwaway; the series doubles as a syllabus. |
| c | **Per-case narrative vehicle** | Each case gets the narrative depth its data naturally carries (documentary → character voice → epistolary → noir). See §4. |

---

## 2. Locked decisions

| # | Decision | Consequence |
|---|----------|-------------|
| d | Path v1 uses **only existing mechanics** | `phases_case_files.py` + new datasets. No changes to `learning.py`, `grading.py`, `sql_runner.py`, `python_runner.py`, or the frontend. |
| e | **"Solved" = correct accusation** | Clearing all challenges = "ready to close"; only the accusation wins the case. |
| f | **Spoiler hygiene** | No `guilty` flag anywhere readable; each clue's answer is a foreign key into the next table; solution, fact predicates, and epilogues live only in private server-side data (same rule as `reference`/`checks` today). |
| g | **Success ladder** | query → clue/fact → case → series; each level has a defined verifier (§5). |
| h | **Case mode allows accusation anytime** | With an in-character warning when evidence is thin (fact-count threshold, not a hard lock). Path mode uses the accusation as the final checkpoint. |
| i | Series spine: **one city ("Iron Harbor"), one recurring narrator** | The world is written once; each case changes the narrative vehicle, not the setting. Working title: *The Case Files: Iron Harbor*. |

---

## 3. Verified platform facts (what we build on)

All verified against the current working tree.

| Piece | Location | What the mystery uses |
|-------|----------|----------------------|
| Path auto-discovery | `backend/curriculum/__init__.py` (`_discover_paths`) | Drop in `phases_case_files.py` exporting `PATH`; optional `ORDER` attribute for sorting. Nothing else changes. |
| Factories | `backend/curriculum/helpers.py` | `challenge(...)` (supports `plan`, `predict`, `concept`, `checks`, `mode`, `limits`, `fixtures`, `dataset`, `capstone`), `phase(...)`, `path(...)`. |
| Runner registry | `backend/curriculum/grading.py` | `sqlite` / `python_guided` / `python_real` cover every case challenge; `register_runner` only if a new profile is ever needed. |
| Live-reference grading | `grading.py` | Learner output is compared to a private reference executed on the same seeded data — hardcoding is useless. SQL feature checks (`join`, `group`, `window`, ...) and Python AST checks (`for`, `comprehension`, `method:...`, `call:...`) gate required techniques. |
| SQL sandbox | `backend/sql_runner.py` | `readonly` (single read statement) and `scratch` (multi-statement CREATE/INSERT/UPDATE/DELETE) modes; authorizer blocks ATTACH/PRAGMA writes/`load_extension`; per-challenge `limits = {rows, steps, time_ms}`. |
| State predicates | `sql_runner.run_check_queries` + `checks.final` | Run after the learner's SQL against the same connection: `{"query","expect"}`, `{"query","expect_rows"}`, `{"rejected_insert"}`. **This is the accusation verifier.** |
| Real Python runner | `backend/python_runner.py` | Isolated subprocess (`-I`), 5 s default timeout, scratch dir per attempt, learner-created files read back for `checks.files`. |
| Fixtures | `python_runner._write_fixture` | Seed files into the scratch dir: `{"file","content"}` or `{"file","dataset","query","format":"csv"}` (generated from any registered dataset). |
| Python ↔ SQLite bridge | `python_runner.run_python` | When a challenge declares `dataset`, a read-only seeded `learning.db` is written into the scratch dir and `DB_PATH` is injected. |
| Dataset registry | `backend/datasets/__init__.py` | Module contract: `ddl()`, `seed(connection, size)`, `TABLES`, `RELATIONSHIPS`; register one entry in `DATASETS`. Powers `connect`, `table_rows`, `write_dataset_file`, `schema_metadata`, `all_metadata`. Sizes: `small`, `perf`. |
| Schema navigator | `frontend` + `all_metadata()` | New case datasets appear automatically — the "case files cabinet". |
| Progress store | `backend/data/learning.sqlite3`, stable challenge ids | Completions, XP, hints, badges, review queue all work for new paths without changes; anonymous browser id identifies the learner. |
| Public payload stripping | `curriculum/public_challenge` | `reference` and `checks` never leave the server; new private keys must follow the same rule. |

---

## 4. The series: four cases, four narrative vehicles

One path pack: `backend/curriculum/phases_case_files.py` (`ORDER = 200`). **One case = one phase = one dataset layer + an accusation checkpoint.**

| # | Case | Dataset | SQL skills | Python skills | Narrative vehicle | Depth |
|---|------|---------|-----------|---------------|-------------------|-------|
| 1 | **The StreamHub Swindle** | `case_streamhub` (StreamHub + case layer) | SELECT/WHERE/ORDER, first joins | CSV fixture, lists/dicts, dossier report | **Documentary / audit file** — the data is the story | N1 |
| 2 | **The Vanishing at Hotel Meridian** | `case_hotel` (Bookings + case layer) | cleaning (dates, dupes), joins, aggregation | datetime parsing, timeline reconstruction | **Character voice** — witness statements, desk notes | N2 |
| 3 | **The Northwind Heist** | `case_northwind` (Northwind + case layer) | join chains, GROUP BY/HAVING, subqueries | aggregate + cross-check two ledgers, write a report file | **Epistolary / institutional** — memos, manifests, audit reports | N2+ |
| 4 | **The Iron Harbor Homicide** | `case_ironharbor` (new police DB) | window functions, CTEs, grain discipline | 200k-row log anomaly scan (perf tier, efficiency check), bridge joins | **Noir** — transcripts, forensics, branching epilogue | N3 |

### 4.1 Why each vehicle fits (locked rationale)

- **Case 1 — documentary (N1).** Fraud is a paper trail; the seeded StreamHub tables already contain churn, unpaid invoices, duplicate events. Prose is limited to briefing + in-table evidence + epilogue. Also the format validator: if data-alone cannot hook a player here, we learn that before paying for noir.
- **Case 2 — character voice (N2).** A disappearance is a people story; messy bookings data reads like human traces. Per-act scene setters, witness-tip hints, one emotional beat.
- **Case 3 — epistolary (N2+).** Corporate shipping speaks in documents. Memos and audit reports *are* the narrative; one twist (the obvious suspect is a patsy).
- **Case 4 — noir (N3).** A murder, the flagship, and a purpose-built dataset — so prose can live inside the tables (interview transcripts = dialogue; forensics reports = set pieces) with a branching epilogue.

### 4.2 Series spine

- One setting: **Iron Harbor**. StreamHub, Hotel Meridian, Northwind are all part of the same city; case 4's police DB belongs to it.
- One narrator: a recurring detective voice across all four cases (name is an open decision).
- Per-case **story bible** (one page, authored in Slice 0 for case 1, repeated per case): victim, culprit, motive, timeline, clue chain (table → key → table), red herrings, narrative vehicle, epilogue variants, suspect list (≥5), fact-predicate targets.

---

## 5. Success model

### 5.1 Player side — the success ladder

| Level | "Success" means | Verified by | Status |
|-------|-----------------|-------------|--------|
| Query/script | Run matches the private reference on the same data | `grading.py` (live reference, feature checks, caps) | exists |
| Clue/fact | The insight was actually demonstrated | Path mode: challenge pass. Case mode: hidden predicate over the learner's result (subset-contains, §5.2) | new in case mode |
| Case | Correct accusation | Path mode: scratch `INSERT` + `checks.final`. Case mode: `POST /api/mystery/accuse` | machinery exists |
| Series | Cases closed; badges; XP; cold cases resurface in review | Progress store + badge catalog | extends existing |

### 5.2 Accusation mechanics (path v1 — zero engine changes)

- Challenge config: `runner: "sqlite"`, `mode: "scratch"`, dataset = the case dataset. The dataset DDL ships an empty `accusations(id INTEGER PRIMARY KEY, name TEXT)` table.
- Learner writes `INSERT INTO accusations (name) VALUES ('<suspect>');`
- `checks.final` verifies server-side:
  - `{"query": "SELECT COUNT(*) FROM accusations", "expect": 1}` (no multi-name hedging)
  - `{"query": "SELECT COUNT(*) FROM accusations WHERE name = '<culprit>'", "expect": 1}`
- `reference` = the correct `INSERT` (never leaves the server; the reference comparison is skipped because INSERT returns no columns — the final checks carry the verification).
- Wrong accusation → in-character failure feedback, attempt counts as failed, learner can retry: *"The DA won't take this to a judge. Go back to the board."*
- Right accusation → the challenge `success` text is the case-closed beat.

### 5.3 Case mode predicate (fact) design

- A **fact** logs when the learner's query result **contains** the required evidence row(s): `expect_rows` (list of tuples) must be a subset of the learner's returned rows, optionally with required columns present (`columns` list). One required technique per fact (join across the right tables, isolation of the right row, aggregation landing on the right number).
- Predicates are private (case registry), never sent to the client.
- A spoofed `SELECT '<name>'` line can never satisfy a fact because facts require the *evidence rows*, not the conclusion.
- Implementation: a small `result_contains` helper in the mystery service, modeled on `_compare_sql_results` (exists in `grading.py`); it is **not** `run_check_queries` (that one evaluates DB state in scratch mode; facts evaluate learner results in readonly mode).

### 5.4 Designer side — how we measure the game works

| Bar | Target | How measured |
|-----|--------|--------------|
| Solvability (must-pass) | 100% | Golden path: private references clear every challenge and the accusation; the case is solvable using only in-game text. |
| Cold-solve test | ≤ 2 hints, no wall > 20 min | A person who has never seen the solution solves Case 1 from zero; log stuck points. |
| Evidence-gated, not guessable | Wrong-accusation rate 10–30% (first attempt) | Path mode: failed accusation completions. Case mode: `mystery_events`. ≥5 plausible suspects ⇒ blind-guess floor 20%. |
| Early-guess signal | tracked | Accusations with < 3 facts found; if common, the tension curve is off. |
| Anti-hardcoding | 0 false passes | Live-reference + result-contains predicates; add variant re-runs if ever needed. |
| Pacing proxies | hints on < 40% of challenges; sane attempts/challenge | Existing progress store (completions, hint usage, XP per stable id). |
| Drop-off point | Case 1 close rate ≥ 70% for cold players | Which challenge people quit at; informs tuning. |
| **Hook signal (the series test)** | ≥ 50% of closers start Case 2 | Completion of case N follows into case N+1. |

Instrumentation:

- **Path v1:** zero new work — completions, XP, hints are already logged.
- **Case mode:** one `mystery_events(learner_id, case_id, kind ∈ run|clue_found|accusation|hint, payload, created_at)` table in `learning.sqlite3`, plus an optional local stats view. Local single-user app: this is a playtest lab, not analytics.

### 5.5 Playtest protocol (per case)

1. Author runs the golden path (all references clear, accusation succeeds).
2. Cold-solve with one player who has not read the solution; record hints used, stuck points, accusations (right/wrong, fact count at accusation).
3. Tune: broken chain → fix clue placement; 0% wrong accusations → add a red herring or decoy-insight; > 30% → strengthen planting.
4. Log results in the story bible notes for that case.

---

## 6. Architecture

### 6.1 What is reused (nothing rebuilt)

- `learning.py` session/progress/XP/hints/badges/review for the path (automatic once `PATH` exists).
- `curriculum/grading.py` runners and checks for every path challenge.
- `sql_runner.py` sandbox (readonly + scratch, caps, authorizer) for interrogation and the accusation.
- `python_runner.py` subprocess + fixtures + `DB_PATH` bridge for the forensics lens.
- `datasets/` registry for case datasets (schema navigator included).
- Frontend: `SyntaxEditor`, `SqlWorkbench` (runner-driven), `SchemaNavigator`, `ChallengeExplorer` (phase groups), `LearnPage` mutations — all as-is.
- Progress store + anonymous learner id for case-mode state.

### 6.2 What is new

| Piece | Where | Slice |
|-------|-------|-------|
| Case datasets (4) | `backend/datasets/case_streamhub.py`, `case_hotel.py`, `case_northwind.py`, `case_ironharbor.py`; one entry each in `DATASETS` | 1, 3, 5 |
| Case Files path | `backend/curriculum/phases_case_files.py` (`PATH`, `ORDER = 200`) | 2, 3, 5 |
| Case registry | `backend/mystery/cases.py` — case id, title, briefing, dataset id, acts, facts (+ predicates), suspects, solution, epilogue variants | 4 |
| Mystery service | `backend/mystery/service.py` — run (readonly + facts + events), accuse (outcome + epilogues), state reads; `predicates.py` (`result_contains`) | 4 |
| Mystery routes | `backend/mystery/router.py`, mounted in `main.py`: `GET /api/mystery/cases`, `GET /api/mystery/case/{id}`, `POST /api/mystery/run`, `POST /api/mystery/accuse` | 4 |
| Case state tables | `learning.sqlite3`: `mystery_facts`, `mystery_accusations`, `mystery_events` | 4 |
| Frontend feature | `frontend/src/features/mystery/` — `CasesPage`, `CaseBoard` (evidence), `SuspectList`, `InvestigationConsole` (reuses workbench), `AccusationDialog`; nav item "Cases" + dashboard card | 4 |
| Badges | "Case Closed" per case, via the existing badge catalog | 2, 4 |
| Docs | README/structure.txt updates | final |

### 6.3 Case mode API sketch

```
GET  /api/mystery/cases                 -> cases + per-learner state (solved, facts found, last accusation)
GET  /api/mystery/case/{id}             -> briefing, acts, public suspect list, found facts (labels only)
                                           (never: solution, predicates, epilogues, red-herring flags)
POST /api/mystery/run    {case_id, source} -> rows + newly found facts + in-character feedback
                                           (sql_runner readonly; caps reused; events logged)
POST /api/mystery/accuse {case_id, name}   -> outcome + epilogue (right) or drama + guidance (wrong);
                                           thin-evidence warning when facts_found < threshold (default 3)
```

Act gating options (decide in slice 3 playtest): (a) authorizer table whitelist per act (`allowed_tables` param — small isolated extension), or (b) narrative-only guidance (all tables always browsable). Default recommendation: (a), fallback (b) if the whitelist proves fiddly.

Python forensics console in case mode (later extension, after slice 4): same route pattern calling `python_runner.run_python` with the case dataset + fixtures and no grading, returning output only.

---

## 7. Case blueprints (starting sketches — final clue chains authored in Slice 0 / per-case slice)

### 7.1 Case 1 — The StreamHub Swindle (`case_streamhub`)

**Slice 0 complete** — full story bible + validated clue chain: [case_files/case-01-streamhub-bible.md](case_files/case-01-streamhub-bible.md). Highlights: nine case tables (`case_persons`, `case_reports`, `case_refunds`, `case_badge_events`, `case_statements`, `case_emails`, `case_tips`, `case_account_links`, `case_accusations`) composed over `streamhub.ddl()/seed()` plus six appended sock accounts (users 401–406); the refund/badge/phone trails converge on one culprit; Python lens uses the guided runner with a `refunds` list of dicts (CSV fixtures move to Case 2). Small tier only — the case dataset must ignore `perf`.

### 7.2 Case 2 — The Vanishing at Hotel Meridian (`case_hotel`)

- **Theme:** a guest disappears; the messy extract is the puzzle.
- Case layer: `keycard_logs`, `staff_shifts`, `front_desk_notes`, `cctv_metadata` (+ CCTV CSV fixture).
- **Skills:** clean mixed-format dates, dedupe refs, join guest → keycard → shift; Python: parse and reconstruct the last 24 hours as a timeline.
- **Narrative:** N2 — witness-tip hints with voice, one emotional beat ("who was the last person to see them?").

### 7.3 Case 3 — The Northwind Heist (`case_northwind`)

- **Theme:** insider shipping scheme; forty crates of chai unaccounted for.
- Case layer: `shipments`, `warehouse_audit`, `memos`, `reprimands`; employees/territories as the cast.
- **Skills:** join chains, GROUP BY/HAVING, subqueries; Python: cross-check manifest vs audit and write a report file (`checks.files`).
- **Narrative:** N2+ — memos and audit reports as the voice; one twist (the obvious suspect is a patsy).

### 7.4 Case 4 — The Iron Harbor Homicide (`case_ironharbor`)

- **Theme:** murder; the flagship and the noir case.
- **New dataset:** `persons`, `vehicles`, `checkins`, `gyms`, `interviews` (transcripts as dialogue), `forensics`, plus a `perf`-tier event log (~200k rows) for the anomaly scan.
- **Skills:** windows, CTEs, grain discipline; Python: efficiency-gated scan across 200k rows + bridge joins.
- **Narrative:** N3 — act scenes, interrogation set pieces, one twist, **branching epilogue** (right: confrontation; wrong: they walk).

---

## 8. Slices

Each slice is independently testable. Backend checks run via `backend\.venv\Scripts\python.exe` with workdir `backend` (so `import main` resolves); frontend builds use `npm.cmd run build`.

### Slice 0 — Case 1 story bible + deduction chain (no app code)

- **Deliverables:** one-page story bible for Case 1 (culprit, motive, timeline, full clue chain with exact keys, red herrings, suspect list ×6, fact-predicate targets, epilogue drafts); the chain hand-validated by solving it from zero against a seeded draft connection.
- **Verify:** solvable with only in-game text; every hop is a foreign key; no table contains the conclusion directly; ≥5 plausible suspects.

### Slice 1 — Case dataset infrastructure

**Done (2026-10-16):** `backend/datasets/case_streamhub.py` + registry entry shipped; verified deterministic (SHA-256 match across two seeds), all chain invariants hold, metadata/relationships served to the navigator, `write_dataset_file` works, `perf` ignored (pinned to small tier).

- **Deliverables:** `backend/datasets/case_streamhub.py` composed over `streamhub` (reuse `ddl()`/`seed()` + case layer); `TABLES`/`RELATIONSHIPS` metadata; registry entry; empty `accusations` table in DDL.
- **Verify:** two `connect()` calls produce identical data (deterministic); `all_metadata()` lists the new tables (navigator shows them); FK columns match the bible; `write_dataset_file` chmods read-only.

### Slice 2 — Case Files path v1 (Case 1 playable)

**Done (2026-10-16):** `backend/curriculum/phases_case_files.py` (`ORDER = 200`) with 8 challenges: 5 readonly SQL hops, 1 guided-Python lens, 1 readonly SQL synthesis hop, and the accusation checkpoint (scratch + `checks.final`) as its own capstone. All references clear through the real grading engine; wrong names and hedged (two-name) accusations fail with in-character messages; learner variants (hardcoded ids/nights, comparison operators, IN-subquery styles) pass fairly; public payload carries no private keys. CSV fixtures moved to Case 2 (per §7.1). Cold-solve protocol (§5.5) still to run with a learner.

- **Deliverables:** `backend/curriculum/phases_case_files.py` — phase 1 with 5–7 challenges (mix of `sqlite` readonly, `python_guided`/`python_real` with fixture + bridge) + the accusation checkpoint (§5.2); in-character hints, `plan`, `predict` drills; `ORDER = 200`.
- **Verify:** track appears in `GET /api/learning/session`; golden path — references clear every challenge and the accusation passes with the culprit INSERT while hedge/multi-INSERT and wrong names fail; no private keys in the public payload; `py_compile` + `import main`; `npm.cmd run build`; cold-solve protocol (§5.5) on Case 1.

### Slice 3 — Cases 2 and 3 content

- **Deliverables:** `case_hotel` + `case_northwind` datasets and their phases in the same pack; per-case story bibles; case mode act-gating decision (whitelist vs narrative-only) settled by playtest.
- **Verify:** per-case golden path + cold-solve; drop-off check on case 2's cleaning challenges (the historically riskiest spot).

### Slice 4 — Case Files mode (free-roam feature)

- **Deliverables:** `backend/mystery/` (registry, service, predicates, router) mounted in `main.py`; `mystery_facts` / `mystery_accusations` / `mystery_events` tables; frontend `features/mystery/` + nav + dashboard card; thin-evidence warning (default < 3 facts); act gating per slice-3 decision.
- **Verify:** free-roam run logs facts only when evidence rows are contained (spoof queries don't); wrong accusation returns the right drama and records the attempt; right accusation closes the case and awards the badge; stats view reads events; legal moves stay inside the existing sandbox posture (ATTACH etc. still blocked); `npm.cmd run build`.

### Slice 5 — Case 4 flagship + polish

- **Deliverables:** `case_ironharbor` dataset (incl. `perf` event tier) + phase; noir narrative assets; cold-case integration into the review queue (solved cases resurface old challenges as practice); **Case Closed** badges per case; case reset/replay; final story bibles committed with the content.
- **Verify:** efficiency check on the 200k scan stays generous on this machine; full series golden path 1→4; hook signal instrumented; docs (`README`, `structure.txt`) updated.

---

## 9. Design rules (binding)

1. **The answer is never stored.** No `guilty` column, no solution string in any table. Each clue's conclusion keys into the next table's foreign key.
2. **The story lives in the data.** Prose budget per case: briefing + act scene setters + hints + epilogue ≈ 600–900 words (N1 less, N4 more), plus in-table evidence text.
3. **One twist per case, max.** Red herrings earn their keep as deductive content, not prose.
4. **Facts are earned, not clicked.** Predicates require evidence rows, never conclusions.
5. **Private by default.** References, checks, fact predicates, solution, epilogues, red-herring flags: server-side only, stripped from public payloads exactly like `reference`/`checks` today.
6. **In-character feedback only.** Failures coach in detective voice (reuse the `coaching.py` spirit); never reveal the answer.
7. **XP:** normal Code Quest XP for path challenges + the "Case Closed" badge per case; no mastery-badge coupling.
8. **Zero engine edits for path content.** If an idea needs an engine change, it belongs to the case-mode slices, not the path pack.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Clue chain broken / unsolvable | Slice 0 hand-solve + golden path every slice; cold-solve protocol per case. |
| Case 1 fails to hook → series risk | Case 1 is the cheapest case by design (N1, 5 tables, no engine work); pivot is cheap. |
| Content volume (4 cases) | One case per slice; datasets compose over existing seeds; narrative vehicles chosen to minimize prose; stop after any case and the series still stands. |
| Guessable accusation | ≥5 suspects, red herrings, verdicts measured (10–30% target), early-guess tracking. |
| Hardcoding | Live-reference grading + result-contains predicates. |
| Free-roam queries abuse sandbox | Reuse `sql_runner` readonly posture + caps; never a new executor. |
| Act gating fiddly | Slice 3 decides; default narrative-only fallback (zero engine work). |
| Spoilers between players | Cases ship as content; solution lives server-side only. (Optional later: seeded variants.) |

---

## 11. Open decisions

1. **Series/narrator name** — "The Case Files: Iron Harbor" is a working title; the detective's name is unwritten.
2. **XP weight** for the accusation checkpoint vs regular challenges (default: capstone-weighted, 40 XP like other capstones).
3. **Act gating** — authorizer whitelist vs narrative-only (slice 3).
4. **Badge names** per case ("StreamHub Closed File", ...).
5. Whether case 3's twist or the patsy survives playtest — content-level, tunable.

---

## 12. File map (new)

```
backend/
├── datasets/
│   ├── case_streamhub.py        # Slice 1
│   ├── case_hotel.py            # Slice 3
│   ├── case_northwind.py        # Slice 3
│   └── case_ironharbor.py       # Slice 5
├── curriculum/
│   └── phases_case_files.py     # Slices 2, 3, 5 (one pack, one phase per case)
├── mystery/                     # Slice 4
│   ├── __init__.py
│   ├── cases.py                 # private registry: facts, predicates, solution, epilogues
│   ├── predicates.py            # result_contains
│   ├── service.py               # run / accuse / state
│   └── router.py                # /api/mystery/*
└── (main.py — mount router; learning.sqlite3 — mystery_* tables)

frontend/src/
├── features/mystery/            # Slice 4
│   ├── CasesPage.tsx
│   ├── CaseBoard.tsx
│   ├── SuspectList.tsx
│   ├── InvestigationConsole.tsx
│   └── AccusationDialog.tsx
└── (AppShell nav + App routes)
```

Existing files touched: `backend/datasets/__init__.py` (registry entries), `backend/main.py` (router mount), `frontend/src/app/AppShell.tsx`, `frontend/src/app/App.tsx`, docs (`README.md`, `structure.txt`).

---

## 13. Appendix — story bible template (one page per case)

```
Case: <number and title>                    Dataset: <id>
Narrative vehicle: N<x> (<name>)            Level: <beginner|...|advanced>
Spine: Iron Harbor, narrator voice

Victim / Stakeholder:
Culprit (private):
Motive (private):
Timeline (public facts):
Clue chain:  report -> <table.column> -> <table.column> -> ... -> accusation
  hop 1: <question>  key: <table.column> = <table.column>
  hop 2: ...
Red herrings (each with a plausible innocent explanation):
Suspects (>=5):            (1 = culprit, never flagged in data)
Fact predicates (case mode): id, label, expect_rows, required columns
Python lens: fixture(s), skill, expected artifact/output
Epilogue (right):
Epilogue (wrong):
Prose budget: briefing ~150w, act setters 3x ~60w, hints 6-8x 1 line, epilogue ~120w
Playtest log: cold-solve date, hints used, stuck points, accusation stats
```

# Code Quest Python Roadmap and Build Guide

## 1. Purpose

This document is the implementation brief for the Python learning experience in Code Quest. Follow it when revising the guided Python Path, its lessons, runner integration, or its connection to Python Scratch.

**Implementation status (2026-10-29):** the two-module Python/SQL navigation, language-scoped Path and Scratch routes, and the 14-phase Python stage mapping are implemented. The pre-change descriptions below remain as design context; section 4.1 records the shipped phase map, and `README.md` describes current behavior.

Code Quest is an all-in-one hub of useful tools. Python learning should therefore do two things well:

1. Teach Python in a clear progression, from first principles through practical and engineering skills.
2. Let a learner use Python Scratch to quickly try a personal idea, even when it is unrelated to the current lesson.

The guided path and Scratch are related parts of the Python experience, but they serve different purposes. Guided lessons provide structure, feedback, progression, and curated data. Scratch is an open-ended workspace. Do not make Scratch topic-dependent or require a learner to follow a lesson before using it.

The supplied `Python Roadmap.html` is a broad developer roadmap. Use its Python language, testing, tooling, and DSA topics to inform the Python Path. Shell, Git, Docker, system design, and interview practice are separate possible Code Quest paths; do not make them prerequisites or silently add them to the Python Path.

Treat the HTML file as a topic/resource proposal, not a verified authority for instructor credentials, popularity counts, time estimates, or current URLs. Do not copy those claims into product copy. If external resources are surfaced to learners, verify that each link works and that its content matches the current Python version and lesson objective. The Code Quest lesson must remain understandable and completable without watching a particular third-party video.

## 1.1 Code Quest section structure

Code Quest currently presents three navigation choices: **Challenges**, **Python Scratch**, and **SQL Scratch**. Replace that top-level structure with two language modules: **Python** and **SQL**. Keep each language's guided path and scratch workspace as distinct modes within that language module.

| Current navigation choice/content | Destination in the new structure | What changes |
|---|---|---|
| **Challenges** — currently contains both Python and SQL learning tracks | Split by language: Python challenges become **Python → Path**; SQL challenges become **SQL → Path** | The combined challenge selector must no longer mix Python and SQL. Reuse the existing challenge engine, progress, and grading. |
| **Python Scratch** | **Python → Scratch** | Keep the Python runner and free-form execution behavior. Change its navigation placement, not its purpose. |
| **SQL Scratch** | **SQL → Scratch** | Keep the SQL workspace and its persistence behavior. Change its navigation placement, not its purpose. |

The result is exactly two top-level language modules:

| Top-level module | Guided mode | Scratch mode |
|---|---|---|
| **Python** | Python Path, including the roadmap progression in section 4 | Python Scratch for arbitrary learner ideas |
| **SQL** | SQL Path and its current guided challenges | SQL Scratch with its own SQLite workspace |

This specifies exactly what is consolidated: the current **Challenges** choice is divided into its Python and SQL paths, and each path is grouped with the Scratch destination for the same language. This is navigation/page organization, not a backend merge. It does **not** combine Python with SQL, merge their runners, merge their workspace services, or make Scratch part of the graded path. Python Path and Python Scratch belong under Python; SQL Path and SQL Scratch belong under SQL. Keep their progress, editor state, workspace behavior, and execution rules separate.

The curriculum also contains a hybrid **Case Files** path (`backend/curriculum/phases_case_files.py`) that intentionally uses SQL and Python together. Audit its current route and visibility before changing navigation. Do not delete it, duplicate its progress, or silently mislabel it as a Python-only or SQL-only course. Keep it as a clearly labeled cross-language project reachable from the two-module Code Quest area (one canonical route and one progress identity); if the current design cannot expose it without creating an unintended third top-level language module, present it as a project entry linked from the Python and SQL modules.

Current frontend entry points to inspect are `frontend/src/app/App.tsx` (routes), `frontend/src/features/scratch/CodeQuestNav.tsx` (the three current navigation choices), `frontend/src/features/learning/LearnPage.tsx` (currently selects learning tracks), `frontend/src/features/learning/components/ChallengeExplorer.tsx` (challenge selector), `frontend/src/features/learning/components/SqlWorkbench.tsx` (despite its name, composes both language workbenches), `frontend/src/features/scratch/PythonScratchPage.tsx`, and `frontend/src/features/scratch/SqlScratchPage.tsx`. The current routes are `/learn`, `/learn/scratch/python`, and `/learn/scratch/sql`. Do not assume that route names or the present combined challenge screen are the desired final navigation.

The desired user flow is:

1. Choose **Python** or **SQL** as the Code Quest module.
2. Within that language, choose **Path** for guided challenges or **Scratch** for independent work.
3. Switching between Path and Scratch keeps the learner in the same language module. Switching languages takes the learner to the other module's corresponding mode, not to a shared Python/SQL editor.
4. The hybrid Case Files project remains reachable without becoming a third language module or being represented twice in progress/review data.

Use clear language-specific titles and active navigation states. A learner in Python must not see SQL challenges mixed into the Python Path selector, and vice versa. Preserve a way to reach all existing supported learning content; audit any non-Python/SQL tracks before changing navigation rather than silently hiding or deleting them.

## 2. Product outcomes

After completing the core Python Path, a learner should be able to:

- Read and write small Python programs using values, variables, expressions, conditions, loops, functions, and collections.
- Break a problem into functions, select useful standard-library modules, and handle expected errors.
- Read and write text, CSV, and JSON files in the workspace and use `pathlib` for paths.
- Build small, useful command-line-style scripts and reports.
- Write and run checks for their own functions, reason about edge cases, and make a small refactor safely.
- Understand basic data-structure and algorithm tradeoffs, with an optional deeper practice branch.
- Use Python Scratch to experiment with arbitrary Python code within the product's documented execution limits.

The core path should prioritize useful programming ability over interview trivia. Advanced language details and extensive DSA practice belong in optional advanced phases or a separate branch.

## 3. Current architecture to preserve

Before editing, inspect the live code. The implementation guide is based on these current conventions and files; if the code has changed, adapt to the live source and update this document where appropriate.

- `backend/curriculum/phases_python.py` defines the current 14-phase Python Path as data using `challenge()`, `phase()`, and `path()` from `backend/curriculum/helpers.py`.
- `backend/curriculum/__init__.py` discovers curriculum packs. Keep the Python pack declarative; do not add one-off engine branches for individual lessons.
- `backend/learning.py` owns learning session, progression, submission, grading dispatch, and progress behavior. Preserve stable challenge identifiers when editing existing lessons unless a deliberate migration is included.
- `backend/guided_python.py` is the constrained interpreter for introductory exercises. It is not full CPython. Keep it for lessons whose syntax and supported constructs fit its capabilities.
- `backend/python_runner.py` runs real Python in a time-limited subprocess and supports a temporary workspace, fixtures, bounded output, and the SQLite bridge. Use it for language features the guided interpreter does not support.
- Python Scratch lives under `backend/scratch/` and `frontend/src/features/scratch/`. Inspect its current API, persistence, and limits before changing it. Current Python runs use a fresh subprocess and temporary per-run directory; editor drafts are browser-side. Python Scratch is not the same product flow as a graded challenge.
- SQL Scratch uses `backend/scratch/sql_workspaces.py` and `backend/scratch/sql_service.py`. Its disposable SQLite database persists across runs until reset/deletion/expiry. Keep this workspace lifecycle distinct from Python's per-run process and file behavior.
- Scratch endpoints are currently registered in `backend/main.py`: Python uses `/api/learning/scratch/python/run`; SQL uses `/api/learning/scratch/sql/...` for workspace creation, execution, reset, and deletion. A frontend navigation change does not require changing these API contracts.
- The learning experience is rendered by `frontend/src/features/learning/`; Python Scratch has its own pages and shared scratch components under `frontend/src/features/scratch/`.
- `backend/datasets/` contains the deterministic datasets used by lessons. The Python-to-SQLite bridge is an applied feature of the learning environment, not a requirement for general Python competence.
- `backend/curriculum/phases_case_files.py` defines a hybrid SQL/Python detective-project path. Preserve its visibility and stable progress identity when splitting the current combined Challenges navigation into Python and SQL modules.

Do not assume the subprocess runner is a secure multi-tenant operating-system sandbox. Preserve and document its current threat model and limits. Do not add package installation, network access, or unrestricted host filesystem access as part of this curriculum work.

## 4. Target curriculum

Reshape the existing path into three named stages. The stage names are learner-facing groupings; they do not require a new backend engine or a new runner type.

### Stage A — Python Foundations

| Suggested phase | Topics and outcomes | Execution |
|---|---|---|
| 1. First Steps | `print`, comments, variables, primitive values, arithmetic, strings, f-strings | Guided interpreter where supported |
| 2. Decisions and Loops | Boolean logic, truthy/falsy values, `if`/`elif`/`else`, `for`, `while`, `range`, `break`, `continue` | Guided interpreter |
| 3. Collections | Lists, tuples, dictionaries, sets, indexing, slicing, mutation, iteration, common collection operations | Guided interpreter where supported; use real Python for unsupported constructs |
| 4. Functions | Definitions, parameters, return values, scope, defaults, decomposition, simple pure functions | Guided interpreter for basics; real Python for unsupported features |
| 5. Text and Errors | String methods, split/join, parsing, tracebacks, `try`/`except`, `else`/`finally`, deliberate `raise`, input validation | Guided for introductory cases; real Python for full syntax |

These topics may be arranged differently if the existing lesson dependencies make a safer transition, but learners must meet each outcome before relying on it in later phases. In particular, do not leave functions until after all practical file exercises.

### Stage B — Practical Python

| Suggested phase | Topics and outcomes | Execution |
|---|---|---|
| 6. Real Python and Modules | Transition to CPython; imports; local modules; useful standard-library discovery; explain `pip` and virtual environments without installing packages | Real Python |
| 7. Files and Paths | Text files, `pathlib`, relative paths, safe workspace reads/writes, predictable file output | Real Python in per-run workspace |
| 8. CSV, JSON, and Reports | `csv` readers/writers, JSON load/dump, data validation, small transformations, report generation | Real Python with deterministic fixtures |
| 9. Applied Automation | Combine functions, collections, errors, and files to build useful small scripts; explain input/output boundaries and clear user feedback | Real Python |
| 10. Python and SQL Data | Query a provided read-only dataset through the SQLite bridge, transform results in Python, compare when SQL or Python is the better tool | Real Python with bridge enabled only for these challenges |

The transition to real CPython should be explained in the lesson experience. Do not imply the guided interpreter is the Python language itself. Keep the starter program runnable and explain any execution difference that matters to the learner.

### Stage C — Python Engineering

| Suggested phase | Topics and outcomes | Execution |
|---|---|---|
| 11. Testing and Refactoring | Test expected and edge cases; assert behavior; use the available test workflow; separate logic from input/output; make a behavior-preserving refactor | Real Python; use the product grading harness without exposing reference solutions |
| 12. Classes and Composition | Define classes, instance state and methods; choose a class when it clarifies a model; prefer simple functions or composition where appropriate | Real Python |
| 13. Iteration and Reusable Code | Iterators, generators, context managers, decorators, type hints, and small module structure, introduced with practical examples | Real Python |
| 14. Data Structures and Algorithms | Big-O intuition; stacks, queues, hash-based lookup, searching, sorting, two pointers, recursion, and introductory graph/tree patterns | Real Python; optional engineering branch if workload is substantial |
| 15. Capstone Projects | Build, test, and explain a small CLI-style utility, file report, or dataset analysis; include a clear README-style summary of behavior and tradeoffs | Real Python; project-style grading rubric |

This is a target content map, not an instruction to blindly renumber every existing phase. First map existing challenges to outcomes, then reorder or split only where it improves progression. If maintaining 14 phases is preferable for compatibility, combine adjacent phases without dropping outcomes. Keep phase IDs and challenge IDs stable whenever possible.

### 4.1 Implemented phase map (2026-10-29)

The existing 14-phase pack was retained so phase and challenge IDs, learner progress, review data, and drafts stay stable. Two roadmap gaps were filled with new lessons (`py-07-06` modules/imports and `py-08-06` `pathlib` + JSON). The path is grouped into three visible stages:

| Phase | Stage | Primary outcome | Runner |
|---|---|---|---|
| 1. First Steps | Python Foundations | Values, variables, arithmetic, strings, f-strings | `python_guided` |
| 2. Collections and Loops | Python Foundations | Lists, indexing, iteration, `len`, `sum` | `python_guided` |
| 3. Decisions and Logic | Python Foundations | Boolean tests, `if`/`elif`/`else`, loop-and-filter patterns | `python_guided` |
| 4. Text and String Methods | Python Foundations | Indexing, `strip`, `split`/`join`, `replace`, cleaning pipelines | `python_guided` |
| 5. Dictionaries and Sets | Python Foundations | Dict access/counting, manual maximum, deduplication | `python_guided` |
| 6. Functions and Comprehensions | Python Foundations | Functions, return values, comprehensions as data transforms | `python_guided` |
| 7. Real Python and Modules | Practical Python | Full CPython transition, standard-library imports, file writing | `python_real` |
| 8. Files, Paths, and Reports | Practical Python | Text/CSV/JSON files, `pathlib`, report generation | `python_real` |
| 9. Errors and Validation | Practical Python | `try`/`except`, `raise`, `assert`, malformed-input handling | `python_real` |
| 10. Classes and Composition | Python Engineering | Classes, instance state, methods, object composition | `python_real` |
| 11. Python and SQL Data | Python Engineering | Read-only SQLite bridge, SQL aggregation with Python presentation | `python_real` |
| 12. Algorithms and Complexity | Python Engineering | Dict/set counting at scale, two pointers, deduplication | `python_real` |
| 13. Testing and Refactoring | Python Engineering | Defaults, assertions as tests, edge cases, behavior-preserving refactor | `python_real` |
| 14. Capstone Projects | Python Engineering | File reports, bridge reports, cleaning pipelines, dashboards | `python_real` |

Deferred optional material remains explicitly optional: iterators/generators, advanced context-manager authoring, type-hint depth, deeper `match`/`case`, advanced decorators/dataclasses/dunder methods, and broader DSA practice (heaps, graphs, dynamic programming, union-find). No package installation, network access, or pytest support is claimed.

### Optional advanced material

Add these only after the core path is coherent and learners can complete the practical projects:

- `match`/`case`, comprehensions in depth, closure behavior, and late-binding pitfalls.
- `*args`/`**kwargs`, decorators in more depth, dataclasses, dunder methods, and composition versus inheritance.
- More complete DSA practice: heaps, trees, graphs, BFS/DFS, dynamic programming, greedy strategies, and union-find.
- `pytest`, fixtures, mocking, and TDD concepts if the current execution and grading model can teach them accurately.

Do not claim to support `pytest`, package installation, external services, or arbitrary project layouts unless the runner actually provides them. Teach the concept with the capabilities that exist, or clearly mark the topic as conceptual.

## 5. Python Scratch requirements

Python Scratch supports quick, learner-chosen experiments. It is not a “Python lesson 0” and should not be filtered by the current challenge topic.

When changing Scratch, preserve or implement the following product behavior, subject to the current workspace implementation:

1. A learner can open Python Scratch from the Code Quest navigation without selecting a Python challenge.
2. The editor accepts general Python source; it does not inject a lesson-specific starter or dataset unless the learner explicitly selects an available helper.
3. Run executes the submitted source using the scratch service and returns stdout, stderr/error information, and execution status in a predictable response shape.
4. The interface displays timeout, syntax/runtime failure, and output-limit conditions distinctly enough for the learner to understand what happened.
5. Python file behavior is explicit: each run uses an ephemeral directory, so generated files do not carry into the next run. Continue returning bounded text artifacts from the run as currently supported. Browser-side editor drafts are separate from run files. Do not imply that Python Scratch is a persistent filesystem unless the implementation is deliberately changed.
6. Enforce the existing runtime, source-size, output-size, and other resource limits on the backend. Validate on the server even if the UI also prevents oversized input.
7. Do not execute code in the API process. Preserve the separate execution service/subprocess boundary already used by the project.
8. Keep scratch drafts in the existing client-side draft mechanism if that is the current behavior; do not confuse draft persistence with server-side filesystem persistence.
9. The challenge runner and Scratch service may share low-level execution utilities, but Scratch must not award challenge XP, unlock phases, reveal reference solutions, or silently overwrite a challenge draft.
10. Add no network or package-install capability as a shortcut for arbitrary-code support. If these capabilities are considered later, first design and implement an appropriate isolation model.

Before changing any of these, inspect `backend/scratch/python_service.py`, `backend/scratch/limits.py`, `backend/python_runner.py`, the Python Scratch frontend page, and the API routes in `backend/main.py`. Update the workspace guide if actual behavior changes.

## 6. Content-authoring requirements

Author lessons using the existing curriculum factories and metadata. Keep content changes separate from execution-engine changes whenever possible.

For every challenge:

- Give one measurable learning objective and one primary concept.
- Use concise, plain-language instructions. State the required output or behavior exactly where grading depends on it.
- Provide a useful starter that runs or fails only at the clearly marked learner task.
- Provide hints that reveal the next reasoning step progressively; do not put the full solution in the first hint.
- Include a short concept explanation and success message that reinforce the transferable idea.
- Prefer behavioral or structural checks that match the intended skill. Do not rely on brittle text matching when equivalent correct programs should pass.
- Use deterministic fixtures and bounded datasets. State the relevant columns and data shape in the challenge.
- Include edge cases in testing and validation challenges.
- For capstones, define a rubric that describes observable outcomes, not one exact implementation.
- Ensure reference solutions remain server-side and are not included in ordinary session or challenge responses.
- Keep learner IDs, phase IDs, and challenge IDs stable unless a migration is explicitly designed.

Avoid teaching magic constants as real-world best practice. If a challenge uses a fixed reference year or fixed dataset row count to make grading deterministic, state that it is fixed for the exercise.

## 7. Grading and learning design

- Grade the requested behavior, not merely whether the learner's code resembles the reference solution.
- Keep output checks exact only when exact output is the objective (for example, formatting practice).
- Add checks for required concepts only where they reflect the learning outcome; avoid forcing a specific syntax when several approaches are valid.
- When the system supports rerunning reference solutions, require each authored challenge's reference to pass through the same execution and grading path as learner submissions.
- Give useful failure feedback: distinguish syntax/runtime errors, incorrect output, missing required behavior, and timeouts where the API currently supports those states.
- Do not return stack traces or internal runner paths that expose server details. Preserve useful line/column information if already supported.
- Keep hints, prediction cards, plans, coaching notes, and review behavior compatible with existing `challenge()` metadata. Do not add a new frontend-only content source for Python lessons.
- Maintain an appropriate separation between lesson unlock/progression and free Scratch execution.

## 8. Step-by-step implementation plan

Complete these steps in order. Make each step a reviewable change and update this guide if implementation reveals a material mismatch.

### Step 1 — Audit before editing

1. Read this document, `Python Roadmap.html`, `README.md`, `doc.md`, and `code-quest-workspaces.md`.
2. Inspect `frontend/src/app/App.tsx`, `CodeQuestNav.tsx`, `LearnPage.tsx`, `ChallengeExplorer.tsx`, `SqlWorkbench.tsx`, both Scratch pages, routes, types, and API functions.
3. Inspect `backend/curriculum/phases_python.py`, `phases_sql.py`, `phases_case_files.py`, `helpers.py`, curriculum discovery, grading, `learning.py`, `guided_python.py`, and `python_runner.py`.
4. Inspect both Scratch services, SQL workspace lifecycle, limits, API route wiring, and browser draft storage. Record the actual Python and SQL persistence behavior separately.
5. Record current top-level navigation, routes, track/path IDs, challenge IDs, runner assignments, datasets, grading rules, unlock behavior, and progress keys.
6. Identify outdated claims in documentation. Treat code as the source of truth; do not copy obsolete proposed behavior from another document.

**Deliverable:** a short internal mapping in the implementation change or PR description that shows current content → target outcome → planned action (keep, move, split, add, or retire).

### Step 2 — Agree the phase map in code terms

Before curriculum edits, turn the source-to-destination mapping in section 1.1 into an implementation checklist. The agreed mapping is: split the current combined Challenges choice into Python Path and SQL Path; group Python Path with Python Scratch under Python; group SQL Path with SQL Scratch under SQL; retain Case Files as one cross-language project. Keep old routes working or redirect them; do not change track IDs, challenge IDs, browser draft keys, or progress identities as a side effect of navigation. Implement the frontend route/navigation changes in Step 6.

Then map every existing challenge in `phases_python.py` to one target outcome from section 4. Mark content that is repeated, out of order, missing, or attached to a runner that cannot support it. Preserve useful existing work: first steps, guided foundations, real CPython transition, file/data tasks, SQLite bridge, algorithms, tests/refactoring, and capstones. Decide whether the current 14 phases can express the revised map or whether one additional phase is warranted. Prefer no renumbering if phases are persisted against learner progress. Keep optional advanced DSA and professional tooling content visibly optional or in its own future path.

**Deliverables:** (a) a route/navigation mapping from the three current choices to the two language modules, including Case Files; and (b) final phase titles, one-sentence outcomes, prerequisite order, runner, and dataset for each Python phase.

### Step 3 — Adjust phase progression and metadata

1. Edit `backend/curriculum/phases_python.py` using existing factories.
2. Move or split challenge definitions only after checking stable identifiers and persisted progress behavior.
3. For new challenges, use stable IDs following the existing `py-XX-NN` convention unless the project has adopted another convention.
4. Put `runner="python_guided"` only on content supported by the guided interpreter; use the real Python runner for full-language features.
5. Use datasets/fixtures only when they teach the objective. Do not require a dataset for unrelated Python syntax lessons.
6. Add phase descriptions, challenge concepts, plans, hints, predict cards, checks, and rubrics consistently with the existing UI support.

**Deliverable:** a loadable curriculum pack with no engine-specific special cases for individual lessons.

### Step 4 — Fill core learning gaps

Prioritize additions in this order:

1. Functions and scope before projects that depend on reusable logic.
2. Error handling and validation with concrete malformed-input cases.
3. Modules, standard-library use, and environment concepts (without arbitrary installs).
4. `pathlib`, text, CSV, and JSON file workflows.
5. Small automation/report projects that combine the preceding skills.
6. Testing and refactoring based on edge cases.
7. Iterators/generators, context managers, type hints, and advanced OOP concepts.
8. DSA breadth and depth, with clear difficulty labels and optional progression where appropriate.

Do not grow the path by adding many isolated syntax cards. Prefer a smaller number of lessons that require learners to use a skill in a meaningful program.

### Step 5 — Check runner fit and workspace semantics

1. Run each proposed starter and reference against its assigned runner through the same APIs used by the product.
2. Confirm real-Python lessons receive only the required fixture files and that created files stay within the per-run workspace.
3. Confirm timeout and output limits still apply to all real-Python challenge submissions.
4. Confirm SQLite access is available only for the intended challenges and remains read-only as designed.
5. Confirm Scratch remains lesson-independent and follows its explicit persistence/reset behavior.
6. If a lesson requires a runner capability that does not exist, either redesign the lesson to fit or make a separate, narrowly scoped runner change with documented limits.

### Step 6 — Update learner-facing navigation and copy

1. Change the Code Quest top-level navigation from **Challenges / Python Scratch / SQL Scratch** to two language modules: **Python** and **SQL**. Each module must provide its own **Path** and **Scratch** destinations as specified in section 1.1.
2. Update `frontend/src/app/App.tsx` routes and `frontend/src/features/scratch/CodeQuestNav.tsx` (or replace the latter with a clearly named Code Quest navigation component) so the selected language and mode are visible in the URL and active navigation state.
3. Rework `frontend/src/features/learning/LearnPage.tsx` so a Python Path view selects only Python learning content and a SQL Path view selects only SQL learning content. Reuse existing challenge/session behavior where possible; do not duplicate grading, progression, or review logic just to add language-specific entry points.
4. Preserve the separate Scratch pages and APIs: Python Scratch stays connected to the Python scratch endpoint/service; SQL Scratch stays connected to the SQL workspace and query service. Do not route both languages through one editor or runner.
5. Choose stable, readable language-specific URLs based on the current router. Keep existing `/learn` and `/learn/scratch/python`, `/learn/scratch/sql` URLs working as redirects or compatible aliases where practical, so existing bookmarks do not break. The default `/learn` destination should lead to a deliberate Path view, not an ambiguous combined Python/SQL selector.
6. Group the Python Path by the three stages from section 4 using existing phase metadata and explorer behavior where possible.
7. Show phase purpose and runner transitions in language learners understand; do not expose internal runner names as product copy. Make optional/advanced content distinguishable from the core progression.
8. Preserve responsive behavior, keyboard-accessible controls, and existing draft, workspace, and progress behavior. Do not change draft keys or learner progress IDs as a side effect of changing routes.
9. Update frontend types/components only if the backend session shape changes; avoid hardcoding phase IDs into presentation logic.

### Step 7 — Update documentation

1. Update `README.md` with an accurate, concise description of the guided Python Path and Python Scratch.
2. Update `doc.md` and `code-quest-workspaces.md` where their architecture or workspace behavior is affected.
3. Document actual execution limits and persistence behavior; do not promise unrestricted Python, package installation, network access, or persistent files unless implemented.
4. Keep this file as the detailed build guide. Do not duplicate the full curriculum table in every document.

### Step 8 — Verify the implementation

Verify every changed behavior with the repository's existing checks. Add focused coverage when a behavior change is not already covered. Do not install new dependencies just to verify a curriculum or navigation change.

At minimum, inspect or verify:

- The curriculum pack imports and all phase/challenge IDs are unique.
- Session serialization exposes the intended phases and hides reference solutions.
- A representative guided challenge and a representative real-Python challenge work through the API.
- File fixtures and generated files behave as documented.
- Python Scratch still runs arbitrary topic-independent snippets and reports the actual runtime/limit behavior.
- Code Quest presents exactly two language modules, Python and SQL, with Path and Scratch available within the relevant module; Python and SQL challenges and workspaces remain distinct.
- Existing routes either continue to work or redirect to their new language-specific destinations; browser back/forward preserves the selected language and mode.
- Progress, phase unlock, drafts, hints, and review flows still use stable identifiers and behave as before.
- Frontend production build succeeds if frontend code or types changed.
- README and architecture docs describe the current implementation rather than a future plan.

Report what changed, the verification performed, and any remaining runner or product limits.

## 9. Change boundaries and non-goals

Unless separately requested, this curriculum effort does not:

- Add shell, Git, Docker, system design, or interview-prep courses to Python Path.
- Replace Python Scratch with guided lessons or restrict Scratch to lesson-related topics.
- Add a hosted multi-user arbitrary-code execution service or claim strong OS-level isolation.
- Permit external network calls, package installation, or access to host secrets/files.
- Rebuild learning progression, XP, review scheduling, or the shared editor solely to change curriculum content.
- Remove the SQL bridge; it is a useful applied connection between the Python and SQL learning paths.
- Expose reference solutions to the browser.

## 10. Definition of done

The Python roadmap work is complete when:

- The Python Path has a deliberate foundations → practical Python → engineering progression.
- Existing useful content has been mapped and retained, improved, or deliberately retired.
- New content covers the selected gaps without making optional advanced/interview topics block the core learner.
- Every challenge uses a runner that supports its syntax and workspace needs.
- Python Scratch remains available for arbitrary learner ideas and its actual persistence and execution limits are clear.
- Code Quest navigation has two top-level language modules, Python and SQL, with each language's Path and Scratch available inside it.
- Python and SQL learning content, Scratch services, and workspaces remain separate; only navigation and shared presentation are consolidated.
- IDs, progress, grading, and solution privacy remain intact.
- Frontend grouping and copy match the curriculum and execution behavior.
- README and supporting architecture docs accurately describe what shipped.
- The implementation report lists verification and any deferred optional topics.

## 11. Instructions to the coding agent

Use this file as the product and implementation specification, but inspect the repository before acting. Make the smallest coherent set of changes that achieves the agreed curriculum. Do not rewrite unrelated tools or architecture. Do not infer that a feature exists just because it is described here as a target; check the implementation. Preserve compatibility with learner progress, and clearly surface any required migration before changing persisted identifiers.

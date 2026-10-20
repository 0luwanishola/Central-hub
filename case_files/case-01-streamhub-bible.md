# Case 1 — The StreamHub Swindle (story bible)

**Status:** Slice 0 complete — clue chain validated end-to-end through the real sandboxes (`sql_runner` readonly/scratch, `guided_python`)
**Date:** 2026-10-16
**Dataset:** `case_streamhub` (composed over the existing `streamhub` dataset; small tier only)
**Narrative vehicle:** N1 — documentary / audit file (the data is the story)
**Level:** beginner (SQL: SELECT/WHERE/GROUP BY/HAVING/first joins; Python: lists, dicts, loops)
**Spine:** Iron Harbor, one narrator voice

---

## 1. Premise and briefing text

> **IRON HARBOR — June 12, 2026.**
> StreamHub's quarterly refund audit came back wrong. Eighteen refunds, six accounts, one hundred percent refund rate — every charge they ever paid came straight back. Company average: 1.8%. Finance wants a name before the board meets.
> The records room is yours: refunds, badge swipes, emails, interviews. Follow the money to a person.

Tone: terse auditor's file. No dialogue outside witness statements. The briefing screen is one card; the rest of the story lives in the tables.

## 2. Cast

| id | Name | Role | Status in story |
|----|------|------|-----------------|
| 1 | Dana Voss | Revenue Assurance Analyst, Finance | **Culprit (private — never flagged in any readable column)** |
| 2 | Vera Eriksen | Infrastructure Engineer (night), Platform | Red herring — tip points at her; night badges on the finance floor (cooling maintenance, emails prove it); never in the refund room |
| 3 | Marcus Reyes | Support Supervisor, Customer Support | Red herring — owns the shared `refunddesk-2` station login |
| 4 | Tomas Fischer | IT Administrator, IT | Red herring — wrote ticket 8841 (sessions not per-user); one daytime refund-room visit for a monitor swap |
| 5 | June Okafor | Support Lead, Customer Support | Red herring — the policy voice (badge log is the only reliable record) |
| 6 | Zane Diallo | Security Officer, Facilities | Red herring — night patrol on the finance floor (one night, outside the room) |
| 7 | Iris Kumar | Financial Analyst, Finance | Auditor — filed the report; not on the tip lines |

## 3. Public timeline

| Date(s) | Event |
|---------|-------|
| 2025-12-28 → 2026-02-16 | Six new accounts created (they only ever pay and refund) |
| 2026-02-11, 03-17, 04-08, 05-19 | Refund nights: 18 refunds issued 22:56–23:58, bursts of 3–6 |
| 2026-05-02 | Facilities report: cooling alarms on the finance floor (Vera's cover is real) |
| 2026-06-05 | Audit filed by Iris Kumar: 100% refund rate on six accounts, $539.82 total |
| 2026-06-09 → 06-11 | Seven statements taken; three anonymous tips received |

## 4. The scheme (private)

Dana Voss created six accounts (users 401–406) on a phone number and card fingerprint she controls, subscribed each to Premium (invoices 3201–3218 at $29.99), and refunded every charge — issuing the refunds from the station's shared `refunddesk-2` login during her late shifts. Total skimmed: **$539.82 over four nights**. The audit's "100% refund rate" is the hook. Two independent trails converge on her: badge swipes into the refund room (physical presence) and the shared phone/card on the six accounts (ownership). Neither alone is presented as a conclusion — the case closes when both point at the same person.

## 5. Clue chain (validated)

All hop queries below ran through `sql_runner.execute(..., mode=readonly)` against the seeded case dataset. Column names matter: the platform grades by comparing learner results to a private reference (columns + rows), so challenge briefs must state the expected columns.

| # | Question | Mechanism | Answer |
|---|----------|-----------|--------|
| 1 | What did the audit find? | `SELECT ... FROM case_reports WHERE category = 'refund audit'` | Iris's memo: 6 accounts, 18 refunds, $539.82 |
| 2 | Which accounts are refund-heavy? | `GROUP BY account_user_id HAVING COUNT(*) >= 3`, ordered by id | Exactly 6 accounts (401–406), 3 refunds each |
| 3 | Who are these accounts? | refunds ⋈ users (`GROUP BY u.id`) | Six recent signups, dormant otherwise, all `@example.com` |
| 4 | Who was on the floor on refund nights? | badges ⋈ persons, `substr` date match against refund dates, door `FINANCE-FLOOR` | Dana Voss, Vera Eriksen, Zane Diallo — the red-herring cluster |
| 5 | Who was inside the refund room, within 2 hours *before* refunds? | badges ⋈ refunds on `occurred_at BETWEEN datetime(issued_at, '-2 hours') AND issued_at`, `GROUP BY name HAVING nights = 4` | Dana Voss, 4 nights |
| 6 | Same verdict, Python lens | guided runner: `refunds` list of dicts → totals/counts per account, print accounts with ≥3 | `401 3 8997` … `406 3 8997` |
| 7 | Follow the money — why her? | `case_account_links` `GROUP BY recovery_phone HAVING COUNT(*) >= 3` ⋈ `case_persons.phone` | Dana Voss, `+1-555-0147` |
| 8 | **Accusation checkpoint** | scratch mode: `INSERT INTO case_accusations (name) VALUES (...)` + `checks.final` | Right: case closed. Wrong: in-character failure. Hedge (2 rows): fails |

Verified checkpoint predicates (both must pass, so hedging fails):

```json
[
  {"query": "SELECT COUNT(*) FROM case_accusations", "expect": 1},
  {"query": "SELECT COUNT(*) FROM case_accusations WHERE LOWER(TRIM(name)) = 'dana voss'", "expect": 1}
]
```

## 6. Red herrings and their resolutions

- **Vera (tip #1 + night badges).** On the floor during the maintenance nights (nights 2 and 4) — never inside the refund room; her two maintenance emails match the dates; statement explains the cooling route.
- **Marcus (login trail).** `refunddesk-2` is the shared station login; it identifies a *station*, not hands (his statement + June's email). The refund rows' `login_used` is a deliberate dead end.
- **Tomas.** Ticket 8841 explains the same dead end; his refund-room visit is daytime (outside every refund window).
- **June.** Policy statement establishes why the badge log *is* reliable — a rule that then works against the culprit.
- **Zane.** Patrol entry on night 3 only, outside the room; security walks the floor.
- **The shared-phone trap.** `case_account_links` also carries two legitimate households sharing phones (2 rows each) — `HAVING COUNT(*) >= 3` is required to isolate the six sock accounts.

## 7. Suspects and guessing floor

Six plausible suspects (Dana, Vera, Marcus, Tomas, June, Zane) + Iris visible in the reports. Blind-guess floor: 1/6 ≈ 17%. Expected first-try wrong-accusation rate target: 10–30% — the convergence of two trails should keep most first accusations correct while the tips pull early guesses toward Vera.

## 8. Narrative assets (drafts)

**Hints (one per challenge, witness voice):**
1. "Finance filed it under 'refund audit'. The room has other paperwork — filter, don't browse."
2. "Don't read 30 refunds one by one. Group them and let the counts talk."
3. "Refunds point at accounts. Accounts point at people. Use the key."
4. "Three names on a floor isn't a culprit. The room is inside the floor — check the room."
5. "Timing is the tell. A badge swipe is not a refund; it happens *before* one."
6. "You can get the same answer with Python: totals and counts in a dict."
7. "Six accounts, one phone, one card. Match it against the staff directory."
8. (checkpoint) "When you're sure, sign the accusation. One name. The DA reads only the first."

**Epilogue (right):** "Dana Voss doesn't look up when you enter. On her screen: six accounts, one phone number, one card — hers, all of it. She reaches for the keyboard, thinks better of it, and pushes the chair back. The DA takes the file. Case closed."

**Epilogue (wrong):** "You name the wrong person. The badge log shrugs; the accounts don't recognize the name. Somewhere in Iron Harbor, Dana Voss finishes her shift in peace. The window is yours to re-read. Case still open."

## 9. Python lens specification

- Runner: `python_guided`; dataset spec: `{"id": "case_streamhub", "variables": {"refunds": "case_refunds"}, "rows": 200}`.
- Task: print `account_user_id, refunds, total_cents` for accounts with ≥3 refunds, one line each, accounts in ascending order.
- Reference output:
  ```
  401 3 8997
  402 3 8997
  403 3 8997
  404 3 8997
  405 3 8997
  406 3 8997
  ```
- Required checks: `["for", "dict"]`. Reduction re-run passes (computed from data).

## 10. Planned challenge set (for Slice 2)

| # | Title | Runner / mode | Skill | Expected result columns |
|---|-------|---------------|-------|-------------------------|
| 1 | The audit memo | sqlite / readonly | SELECT, WHERE | filed_at, filed_by, report |
| 2 | Refund-heavy accounts | sqlite / readonly | GROUP BY, HAVING, ORDER BY | account_user_id, refunds |
| 3 | Who are these accounts? | sqlite / readonly | first JOIN | id, name, email, signup_date |
| 4 | Night visitors | sqlite / readonly | JOIN + IN (subquery) | person_id, name |
| 5 | Refund-room windows | sqlite / readonly | JOIN with BETWEEN + HAVING | name, nights |
| 6 | The money trail, in Python | python_guided | lists, dicts, loops | (printed lines above) |
| 7 | Follow the money | sqlite / readonly | GROUP BY/HAVING + JOIN | name, recovery_phone |
| 8 | The accusation | sqlite / scratch | INSERT + state checks | — |

Also planned: one `predict` drill on challenge 2 (HAVING vs WHERE) and one on challenge 5 (BETWEEN is inclusive). Hints per §8. Column names in briefs must exactly match §5 (grading compares columns).

## 11. Case-mode fact predicates (preview for Slice 4)

Candidate facts (subset-contains over learner results): "sock accounts identified" (challenge 2 rows), "badge window resolved" (challenge 5 row), "ownership link" (challenge 7 row), "accusation placed". Thin-evidence warning threshold: < 3 facts.

## 12. Dataset specification summary (for Slice 1)

**Case tables (9):** `case_persons` (7 rows), `case_reports` (3), `case_refunds` (30 = 18 sock + 12 normal), `case_badge_events` (~250; authored night events + daytime noise), `case_statements` (7), `case_emails` (4), `case_tips` (3), `case_account_links` (10), `case_accusations` (empty, checkpoint target).

**Appended base rows:** users 401–406 (sock accounts), subscriptions 801–806 (Premium), invoices 3201–3218 (3× $29.99 each, paid).

**Composition rules:** reuse `streamhub.ddl()` + `streamhub.seed()` verbatim, then case DDL + authored rows. Case layer is authored data only — no RNG except badge daytime noise (seeded `5501`). **Force small tier** (the case dataset must ignore `perf`): the sock ids 401+/801+/3201+ are safe for small (400 users / 800 subs / 3200 invoices even if the base invoice generator is fixed) but would collide on perf.

**Badge noise rules:** daytime only (08:00–19:00), doors `LOBBY / SUPPORT-FLOOR / DATA-CENTER / MAILROOM` — `FINANCE-FLOOR` and `REFUND-ROOM` are authored-only so the chain queries stay clean.

**Grading-relevant invariants (validated):** exactly 6 accounts with ≥3 refunds; exactly 3 names on the floor across refund dates; exactly 1 name in the refund-room windows across all 4 nights; exactly 1 phone matching ≥3 accounts; sock total $539.82 across 4 nights (3/4/6/5 per night).

## 13. Prose budget (N1)

Briefing ~120w, 8 hints × 1 line, epilogue right ~60w, wrong ~50w, plus in-table text (reports/statements/emails/tips ≈ 550w) — all of which is also evidence. No scene-setting prose.

## 14. Slice 0 validation log (prototype: `%TEMP%\opencode\case01_prototype.py`)

- Deduction chain: all 7 hops executed through `sql_runner` readonly with exact expected narrowings (validated output captured).
- Python lens: reference program runs in `guided_python`; output matches §9.
- Accusation: correct name passes; wrong name fails; hedging two rows fails.
- Determinism: two independent seeds produce identical table dumps (SHA-256 match).
- Spoiler scan: the string "Dana" appears only in `case_persons` (name + email) — nowhere in refunds, links, badges, emails, or tips.
- **Side finding (out of scope, reported):** the base `streamhub.seed` small tier generates **113 invoices, not 3,200** — the free-plan branch (`if amount == 0: continue`) skips the month advance, spinning the invoice counter to the cap at the first free subscription (id 21). The perf tier will under-generate similarly. Case 1 is unaffected (normal refunds draw from the 113 real invoices); a one-line fix (advance the month before `continue`) would restore full output for existing curriculum phases — decide separately.

## 15. Open tunables

- Refund-night count (4) and per-night bursts — tune after cold-solve.
- Whether Vera's tip should be sharper (currently 1/6-pointing).
- Dana's statement hubris line — keep only if cold-solve says players need the nudge toward badge logs.
- Tip #3 timing (currently 2026-06-08) — may move later to avoid solving challenge 7 for free.

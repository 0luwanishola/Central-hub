"""Case Files path: hybrid SQL + Python detective mysteries.

Case 1, "The StreamHub Swindle", is a documentary-lens investigation: a refund
audit flags six accounts with a 100% refund rate, and the learner follows the
money from the audit memo through refunds, staff badges, and account links to a
single accusation.

Design rules for this pack (see ``case_files/`` and ``plan.md``):

- Zero engine changes: everything is built on the existing challenge factories.
- SQL for records, Python for aggregation — the mystery is the syllabus.
- The accusation is a scratch-mode checkpoint that verifies database state
  (``checks.final``), not a query result: one row, one name.
- Spoiler hygiene: the culprit is never marked in the dataset, and solution
  predicates live only in ``checks``/``reference``, which never leave the
  server (see ``curriculum.public_challenge``).
"""

from .helpers import challenge, path, phase

ORDER = 200


def sql(id, title, topic, brief, starter, reference, *, hints, success, **kwargs):
    """SQL-flavored challenge: runner and language are pre-set."""
    return challenge(
        id,
        title,
        topic,
        brief,
        starter,
        reference,
        hints=hints,
        success=success,
        runner="sqlite",
        language="sql",
        **kwargs,
    )


# --------------------------------------------------------------------------- 1

CH_1 = sql(
    "case-01-01",
    "The audit memo",
    "SELECT / WHERE",
    "June 2026. An internal audit landed on your desk: someone refunded every "
    "charge on six customer accounts, and not one customer complained.\n\n"
    "Start at the source. From case_reports, return the report filed under the "
    "category 'refund audit' — its filed_at timestamp, filed_by author, and report "
    "text. One row.",
    "-- one row: filter case_reports by category\n",
    "SELECT filed_at, filed_by, report FROM case_reports WHERE category = 'refund audit';",
    hints=[
        "case_reports holds a handful of reports — filter, don't browse.",
        "The category value is exactly 'refund audit' (lowercase, one space).",
        "Return filed_at, filed_by, and report. Nothing else.",
    ],
    plan=[
        "Check what columns case_reports has.",
        "Filter with WHERE category = 'refund audit'.",
        "Select the three columns and read the numbers in the report.",
    ],
    concept="WHERE keeps the rows that match a condition — the query skips everything else.",
    success="Six accounts. Eighteen refunds. $539.82 — every charge returned. The audit calls it a '100% refund rate'.",
    checks={"required": ["where"]},
    dataset={"id": "case_streamhub", "tables": ["case_reports"]},
)

# --------------------------------------------------------------------------- 2

CH_2 = sql(
    "case-01-02",
    "Refund-heavy accounts",
    "GROUP BY / HAVING",
    "The audit names totals, not accounts. Find the accounts yourself: group "
    "case_refunds by account_user_id and keep only the accounts with 3 or more "
    "refunds.\n\n"
    "Return account_user_id and the refund count as a column named refunds, sorted "
    "by account_user_id. The audit claims six rows — prove it.",
    "-- count refunds per account; keep groups of 3 or more\n",
    "SELECT account_user_id, COUNT(*) AS refunds FROM case_refunds "
    "GROUP BY account_user_id HAVING COUNT(*) >= 3 ORDER BY account_user_id;",
    hints=[
        "One row per account: GROUP BY account_user_id.",
        "Measure each group with COUNT(*).",
        "Filter whole groups with HAVING, and alias the count AS refunds so the column name matches.",
    ],
    plan=[
        "Group the refunds by account.",
        "Count the rows in each group.",
        "Keep groups of 3+ with HAVING, sort by account, and compare with the audit's 'six accounts'.",
    ],
    concept="GROUP BY forms groups; aggregate functions measure them; HAVING keeps the groups worth keeping.",
    predict={
        "prompt": "WHERE and HAVING both filter. Which one keeps only the accounts with 3 or more refunds?",
        "code": "SELECT account_user_id, COUNT(*) AS refunds\nFROM case_refunds\nGROUP BY account_user_id\n-- keep accounts with 3 or more refunds\n",
        "options": ["WHERE refunds >= 3", "HAVING COUNT(*) >= 3", "ORDER BY refunds >= 3"],
        "answer": 1,
        "why": "WHERE filters single rows before grouping and can't see COUNT(*). HAVING filters the finished groups — that's where '3 or more refunds' lives.",
    },
    success="Six accounts — 401 through 406 — three refunds each. A perfect refund rate doesn't happen by accident.",
    checks={
        "required": ["group", "having", "order"],
        "ordered": True,
        "messages": {"having": "Groups are filtered after counting — keep the 3+ accounts with HAVING COUNT(*) >= 3."},
    },
    dataset={"id": "case_streamhub", "tables": ["case_refunds"]},
)

# --------------------------------------------------------------------------- 3

CH_3 = sql(
    "case-01-03",
    "Names behind the accounts",
    "INNER JOIN",
    "Account ids are just numbers; the owners live in users. Join case_refunds to "
    "users and put a name on each flagged account — the accounts with 3 or more "
    "refunds.\n\n"
    "Return id, name, email, and signup_date, one row per account, sorted by id.",
    "-- join refunds to users; one row per owner\n",
    "SELECT u.id, u.name, u.email, u.signup_date "
    "FROM users u "
    "JOIN case_refunds r ON r.account_user_id = u.id "
    "GROUP BY u.id HAVING COUNT(*) >= 3 ORDER BY u.id;",
    hints=[
        "Join on users.id = case_refunds.account_user_id.",
        "Each owner has three refund rows — dedupe with GROUP BY u.id (or SELECT DISTINCT).",
        "You can carry the 3+ filter from the last step (HAVING COUNT(*) >= 3) instead of typing ids.",
    ],
    plan=[
        "Join users to case_refunds on the account id.",
        "Aggregate per user so each owner appears once.",
        "Keep the 3+ accounts and sort by id.",
    ],
    concept="JOIN pulls the owner row alongside each refund row; aggregate after the join to collapse duplicates.",
    success="Zoe, Omar, Elif, Noah, Mia, Leo — six names, six strangers, none of them StreamHub staff. Someone else is holding the keys.",
    checks={"required": ["join"], "ordered": True},
    dataset={"id": "case_streamhub", "tables": ["case_refunds", "users"]},
)

# --------------------------------------------------------------------------- 4

CH_4 = sql(
    "case-01-04",
    "Who walked the floor",
    "Subquery + JOIN",
    "The refunds were issued from the finance floor, overnight — and that floor is "
    "badge-controlled. Find out who was up there on the four refund nights.\n\n"
    "Refund nights = the distinct dates of the flagged refunds (accounts with 3 or "
    "more). From case_badge_events, take entries (direction 'in') at door "
    "FINANCE-FLOOR on any of those dates, and join names from case_persons.\n\n"
    "Return person_id and name, one row per person, sorted by person_id.",
    "-- badge 'in' events on FINANCE-FLOOR, on any of the four refund nights\n",
    "SELECT DISTINCT b.person_id, p.name "
    "FROM case_badge_events b "
    "JOIN case_persons p ON p.id = b.person_id "
    "WHERE b.door = 'FINANCE-FLOOR' AND b.direction = 'in' "
    "AND substr(b.occurred_at, 1, 10) IN ("
    "  SELECT substr(r.issued_at, 1, 10) FROM case_refunds r "
    "  WHERE r.account_user_id IN ("
    "    SELECT account_user_id FROM case_refunds "
    "    GROUP BY account_user_id HAVING COUNT(*) >= 3)) "
    "ORDER BY b.person_id;",
    hints=[
        "Subqueries nest: ... WHERE substr(occurred_at, 1, 10) IN (SELECT ...).",
        "The refund nights are the distinct dates of the flagged refunds — a date is the first 10 characters of a timestamp.",
        "Join case_persons to turn person_id into a name, then dedupe so each person appears once.",
    ],
    plan=[
        "Compute the refund nights: distinct dates of refunds on flagged accounts.",
        "Filter badge events: FINANCE-FLOOR, direction 'in', date IN those nights.",
        "Join names, dedupe, sort by person_id.",
    ],
    concept="A subquery is a query that feeds another query — IN (SELECT ...) tests membership.",
    success="Three names crossed that floor on refund nights: Dana, Vera, Zane. Four nights, same pattern.",
    checks={"required": ["join"], "ordered": True},
    dataset={"id": "case_streamhub", "tables": ["case_badge_events", "case_persons", "case_refunds"]},
)

# --------------------------------------------------------------------------- 5

CH_5 = sql(
    "case-01-05",
    "The refund-room window",
    "JOIN on a time window",
    "Floor access is not enough — the refunds were issued from inside REFUND-ROOM. "
    "Match each flagged refund (accounts with 3 or more) to badge entries into "
    "REFUND-ROOM made within 2 hours before that refund was issued.\n\n"
    "Count the distinct refund nights per person and keep only the people present "
    "on all four nights. Return name and nights.",
    "-- refunds joined to REFUND-ROOM entries in the two hours before them\n",
    "SELECT p.name, COUNT(DISTINCT substr(r.issued_at, 1, 10)) AS nights "
    "FROM case_refunds r "
    "JOIN case_badge_events b ON b.door = 'REFUND-ROOM' AND b.direction = 'in' "
    "  AND b.occurred_at BETWEEN datetime(r.issued_at, '-2 hours') AND r.issued_at "
    "JOIN case_persons p ON p.id = b.person_id "
    "WHERE r.account_user_id IN ("
    "  SELECT account_user_id FROM case_refunds "
    "  GROUP BY account_user_id HAVING COUNT(*) >= 3) "
    "GROUP BY p.name HAVING nights = 4;",
    hints=[
        "The time window lives in the JOIN: b.occurred_at BETWEEN datetime(r.issued_at, '-2 hours') AND r.issued_at.",
        "Count distinct nights per person: COUNT(DISTINCT substr(r.issued_at, 1, 10)).",
        "Keep the person whose count reaches 4 with HAVING.",
    ],
    plan=[
        "Join each flagged refund to REFUND-ROOM entries from the two hours before it.",
        "Bring in names through case_persons.",
        "Count distinct nights per person and keep nights = 4.",
    ],
    concept="Time windows are joins with conditions; COUNT(DISTINCT day) counts unique days, not swipes.",
    predict={
        "prompt": "A refund goes out at 23:40. A badge swipe into the room at 21:40 — inside the two-hour window?",
        "code": "b.occurred_at BETWEEN datetime(r.issued_at, '-2 hours') AND r.issued_at",
        "options": [
            "No — the window starts after 21:40",
            "Yes — BETWEEN includes both endpoints",
            "Only if the clock is rounded to the hour",
        ],
        "answer": 1,
        "why": "BETWEEN is inclusive: exactly two hours before the refund still counts.",
    },
    success="One person stood inside that room on all four nights — always in the quiet hours before the refunds. The room was used, not visited.",
    checks={"required": ["join", "having"]},
    dataset={"id": "case_streamhub", "tables": ["case_refunds", "case_badge_events", "case_persons"]},
)

# --------------------------------------------------------------------------- 6

CH_6 = challenge(
    "case-01-06",
    "The money trail in Python",
    "dicts + loops",
    "Same question, second lens. refunds is the case_refunds table loaded as a "
    "list of dicts.\n\n"
    "For every account with 3 or more refunds, print the account id, the refund "
    "count, and the total amount in cents — three values separated by spaces, one "
    "line per account, accounts in ascending order.",
    "# refunds: a list of dicts, keys include 'account_user_id' and 'amount_cents'\n"
    "counts = {}\n"
    "totals = {}\n",
    "counts = {}\n"
    "totals = {}\n"
    "for r in refunds:\n"
    "    account = r['account_user_id']\n"
    "    counts[account] = counts.get(account, 0) + 1\n"
    "    totals[account] = totals.get(account, 0) + r['amount_cents']\n"
    "for account in sorted(counts):\n"
    "    if counts[account] >= 3:\n"
    "        print(account, counts[account], totals[account])\n",
    hints=[
        "Accumulate by key: counts[account] = counts.get(account, 0) + 1.",
        "The same pattern sums money: totals[account] = totals.get(account, 0) + r['amount_cents'].",
        "Loop over sorted(counts) and print only the accounts with 3+ refunds.",
    ],
    plan=[
        "Walk the refunds once, accumulating counts and totals per account.",
        "Loop over the accounts in ascending order.",
        "Print account, count, and total cents for the 3+ accounts.",
    ],
    concept="dict.get(key, 0) + value is the accumulate-by-key pattern — Python's cousin of GROUP BY.",
    success="Six lines: six accounts, three refunds, 8997 cents each. Python says the same thing SQL said.",
    runner="python_guided",
    language="python",
    checks={"required": ["for", "dict"]},
    dataset={
        "id": "case_streamhub",
        "variables": {"refunds": "case_refunds"},
        "rows": 200,
    },
)

# --------------------------------------------------------------------------- 7

CH_7 = sql(
    "case-01-07",
    "Follow the money",
    "JOIN + GROUP BY / HAVING",
    "Six accounts behaving as one operation — case_account_links shows how they "
    "know each other. Find the recovery phone shared by 3 or more accounts, then "
    "put a staff name on it.\n\n"
    "Return name and recovery_phone.",
    "-- shared recovery phone (3+ accounts) matched to a staff member\n",
    "SELECT p.name, l.recovery_phone "
    "FROM case_account_links l "
    "JOIN case_persons p ON p.phone = l.recovery_phone "
    "GROUP BY l.recovery_phone, p.name HAVING COUNT(*) >= 3;",
    hints=[
        "Group case_account_links by recovery_phone and count accounts per group.",
        "Careful: two phones are shared by 2 accounts each — decoys. You need 3 or more.",
        "Join to case_persons on phone = recovery_phone for the name.",
    ],
    plan=[
        "Group links by recovery_phone; count accounts in each group.",
        "Keep groups with 3+ accounts (HAVING).",
        "Join case_persons on the phone to name the owner.",
    ],
    concept="HAVING COUNT(*) >= 3 turns 'how many' into 'who' — recurring identifiers expose shared control.",
    success="The phone on all six accounts is +1-555-0147 — Dana Voss's office line. The door trail and the money trail just met in the same person.",
    checks={"required": ["join", "group", "having"]},
    dataset={"id": "case_streamhub", "tables": ["case_account_links", "case_persons"]},
)

# --------------------------------------------------------------------------- 8

CH_8 = sql(
    "case-01-08",
    "Close the case",
    "Case checkpoint",
    "Everything you found points at one person. Accusations go in writing: insert "
    "exactly one row into case_accusations with the full name.\n\n"
    "The case book must show one name — the right one. Hedging with two names "
    "fails; a wrong name keeps the case open.",
    "-- one INSERT, one full name\nINSERT INTO case_accusations (name) VALUES ('First Last');\n",
    "INSERT INTO case_accusations (name) VALUES ('Dana Voss');",
    hints=[
        "Two trails met in the same person: the room that opened for her four nights running, and the phone all six accounts share.",
        "One INSERT, one name, first and last name.",
    ],
    plan=[
        "Compare your two verdict tables: who was inside the refund-room windows, and who owns the shared phone.",
        "Insert one row with that full name.",
    ],
    concept="A verdict closes a case only when independent evidence agrees — the door log and the money trail aren't allowed to share a suspect by accident.",
    success="Dana Voss doesn't look up when you walk in. On her screen: six accounts, one phone, one card — hers, every account, back to February. She kept the door log in her head; the building kept it in a table. The DA signs the file. Case closed.",
    mode="scratch",
    checks={
        "required": ["insert"],
        "messages": {"insert": "This checkpoint closes with a written accusation — an INSERT into case_accusations."},
        "final": [
            {
                "query": "SELECT COUNT(*) FROM case_accusations",
                "expect": 1,
                "message": "The case book needs exactly one accusation row — filing nothing, or filing several names, both read as 'not ready'.",
            },
            {
                "query": "SELECT COUNT(*) FROM case_accusations WHERE LOWER(TRIM(name)) = 'dana voss'",
                "expect": 1,
                "message": "The DA reads the name back and frowns. That name wasn't inside the refund room on all four nights — recheck the badge window and the phone trail.",
            },
        ],
    },
    capstone=True,
    capstone_rubric=[
        "Both trails point at the same person",
        "Exactly one accusation row with the full name",
        "You can explain the two-hour window and the shared-phone count",
    ],
    dataset={"id": "case_streamhub", "tables": ["case_accusations"]},
)

PHASE_1 = phase(
    "case-1-streamhub",
    "The StreamHub Swindle",
    "Case 1",
    "June 2026: six accounts, eighteen refunds, and a 100% refund rate. Follow the "
    "paper trail from audit memo to accusation — records in SQL, money in Python.",
    [CH_1, CH_2, CH_3, CH_4, CH_5, CH_6, CH_7, CH_8],
)

PATH = path(
    "case_files",
    "The Case Files",
    "Iron Harbor's case files: hybrid mysteries solved with SQL records and Python forensics.",
    "mixed",
    [PHASE_1],
)

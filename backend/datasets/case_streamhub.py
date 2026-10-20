"""StreamHub Case File dataset: the Case 1 mystery layer over the StreamHub product data.

Composition rules:
  - ``ddl()`` = ``streamhub.ddl()`` + the case tables.
  - ``seed()`` pins the base seed to the **small tier** (the case dataset ignores
    ``perf``): the case layer appends rows at ids 401+ (users), 801+ (subscriptions),
    and 3201+ (invoices), which stay collision-free on the small tier even when
    the base invoice generator produces its full 3,200 invoices.
  - The case layer is authored data only; the one random element (daytime badge
    noise) uses a fixed RNG seed, so the dataset is identical on every run.

Authoring notes for the mystery:
  - ``case_badge_events`` noise rows are daytime-only and never use the
    ``FINANCE-FLOOR`` or ``REFUND-ROOM`` doors; those doors are authored events.
  - The culprit is never flagged anywhere in the data: the case closes only by
    chaining the refund, badge, and account-link trails (see
    ``case_files/case-01-streamhub-bible.md``).
"""

import random
import sqlite3
from datetime import date, timedelta

if __package__:
    from . import streamhub
else:  # pragma: no cover - module can run as a top-level module
    import streamhub


CASE_DDL = """
CREATE TABLE "case_persons" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT, "role" TEXT, "team" TEXT,
    "email" TEXT, "phone" TEXT, "badge_serial" TEXT,
    "hire_date" TEXT
);
CREATE TABLE "case_reports" (
    "id" INTEGER PRIMARY KEY,
    "filed_at" TEXT, "filed_by" TEXT, "category" TEXT, "report" TEXT
);
CREATE TABLE "case_refunds" (
    "id" INTEGER PRIMARY KEY,
    "invoice_id" INTEGER, "account_user_id" INTEGER,
    "amount_cents" INTEGER, "issued_at" TEXT,
    "reason" TEXT, "login_used" TEXT, "status" TEXT
);
CREATE TABLE "case_badge_events" (
    "id" INTEGER PRIMARY KEY,
    "person_id" INTEGER, "door" TEXT, "direction" TEXT, "occurred_at" TEXT
);
CREATE TABLE "case_statements" (
    "id" INTEGER PRIMARY KEY,
    "person_id" INTEGER, "taken_at" TEXT, "taken_by" TEXT, "statement" TEXT
);
CREATE TABLE "case_emails" (
    "id" INTEGER PRIMARY KEY,
    "sender_person_id" INTEGER, "recipient_person_id" INTEGER,
    "sent_at" TEXT, "subject" TEXT, "body" TEXT
);
CREATE TABLE "case_tips" (
    "id" INTEGER PRIMARY KEY,
    "received_at" TEXT, "tip" TEXT
);
CREATE TABLE "case_account_links" (
    "account_user_id" INTEGER,
    "recovery_phone" TEXT, "card_fingerprint" TEXT, "signup_device" TEXT
);
CREATE TABLE "case_accusations" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT
);
"""

_CASE_TABLES = {
    "case_persons": {
        "description": "StreamHub staff roster: roles, phones, and door badges.",
        "grain": "one row per employee",
        "columns": ["id", "name", "role", "team", "email", "phone", "badge_serial", "hire_date"],
        "types": {
            "id": "integer", "name": "text", "role": "text", "team": "text",
            "email": "text", "phone": "text", "badge_serial": "text", "hire_date": "date",
        },
        "keys": {"primary": ["id"], "foreign": []},
    },
    "case_reports": {
        "description": "Internal reports filed by staff: audits, facilities notes, IT tickets.",
        "grain": "one row per report",
        "columns": ["id", "filed_at", "filed_by", "category", "report"],
        "types": {"id": "integer", "filed_at": "datetime", "filed_by": "text", "category": "text", "report": "text"},
        "keys": {"primary": ["id"], "foreign": []},
    },
    "case_refunds": {
        "description": "Every refund issued through the support desk this year.",
        "grain": "one row per refund",
        "columns": ["id", "invoice_id", "account_user_id", "amount_cents", "issued_at", "reason", "login_used", "status"],
        "types": {
            "id": "integer", "invoice_id": "integer", "account_user_id": "integer",
            "amount_cents": "integer", "issued_at": "datetime", "reason": "text",
            "login_used": "text", "status": "text",
        },
        "keys": {"primary": ["id"], "foreign": ["invoice_id -> invoices.id", "account_user_id -> users.id"]},
    },
    "case_badge_events": {
        "description": "Door badge swipes across the StreamHub offices.",
        "grain": "one row per swipe",
        "columns": ["id", "person_id", "door", "direction", "occurred_at"],
        "types": {"id": "integer", "person_id": "integer", "door": "text", "direction": "text", "occurred_at": "datetime"},
        "keys": {"primary": ["id"], "foreign": ["person_id -> case_persons.id"]},
    },
    "case_statements": {
        "description": "Witness statements taken during the investigation.",
        "grain": "one row per statement",
        "columns": ["id", "person_id", "taken_at", "taken_by", "statement"],
        "types": {"id": "integer", "person_id": "integer", "taken_at": "datetime", "taken_by": "text", "statement": "text"},
        "keys": {"primary": ["id"], "foreign": ["person_id -> case_persons.id"]},
    },
    "case_emails": {
        "description": "Internal emails relevant to the refund investigation.",
        "grain": "one row per email",
        "columns": ["id", "sender_person_id", "recipient_person_id", "sent_at", "subject", "body"],
        "types": {"id": "integer", "sender_person_id": "integer", "recipient_person_id": "integer", "sent_at": "datetime", "subject": "text", "body": "text"},
        "keys": {"primary": ["id"], "foreign": ["sender_person_id -> case_persons.id", "recipient_person_id -> case_persons.id"]},
    },
    "case_tips": {
        "description": "Anonymous tips received by the investigation.",
        "grain": "one row per tip",
        "columns": ["id", "received_at", "tip"],
        "types": {"id": "integer", "received_at": "datetime", "tip": "text"},
        "keys": {"primary": ["id"], "foreign": []},
    },
    "case_account_links": {
        "description": "Payment and recovery details shared across customer accounts.",
        "grain": "one row per account",
        "columns": ["account_user_id", "recovery_phone", "card_fingerprint", "signup_device"],
        "types": {"account_user_id": "integer", "recovery_phone": "text", "card_fingerprint": "text", "signup_device": "text"},
        "keys": {"primary": [], "foreign": ["account_user_id -> users.id"]},
    },
    "case_accusations": {
        "description": "Accusations placed by the investigator (case checkpoint).",
        "grain": "one row per accusation",
        "columns": ["id", "name"],
        "types": {"id": "integer", "name": "text"},
        "keys": {"primary": ["id"], "foreign": []},
    },
}

TABLES = {**streamhub.TABLES, **_CASE_TABLES}

_CASE_RELATIONSHIPS = [
    {"from_table": "case_refunds", "from_column": "account_user_id", "to_table": "users", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "case_refunds", "from_column": "invoice_id", "to_table": "invoices", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "case_badge_events", "from_column": "person_id", "to_table": "case_persons", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "case_statements", "from_column": "person_id", "to_table": "case_persons", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "case_emails", "from_column": "sender_person_id", "to_table": "case_persons", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "case_emails", "from_column": "recipient_person_id", "to_table": "case_persons", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "case_account_links", "from_column": "account_user_id", "to_table": "users", "to_column": "id", "cardinality": "many-to-one"},
]

RELATIONSHIPS = streamhub.RELATIONSHIPS + _CASE_RELATIONSHIPS

# --------------------------------------------------------------------------- cast

_PERSONS = [
    # id, name, role, team, email, phone, badge, hire_date
    (1, "Dana Voss", "Revenue Assurance Analyst", "Finance", "dana.voss@streamhub.example", "+1-555-0147", "B-1187", "2023-04-17"),
    (2, "Vera Eriksen", "Infrastructure Engineer (night)", "Platform", "vera.eriksen@streamhub.example", "+1-555-0112", "B-1042", "2021-09-06"),
    (3, "Marcus Reyes", "Support Supervisor", "Customer Support", "marcus.reyes@streamhub.example", "+1-555-0123", "B-1330", "2022-02-14"),
    (4, "Tomas Fischer", "IT Administrator", "IT", "tomas.fischer@streamhub.example", "+1-555-0131", "B-1205", "2022-11-02"),
    (5, "June Okafor", "Support Lead", "Customer Support", "june.okafor@streamhub.example", "+1-555-0136", "B-1355", "2023-06-19"),
    (6, "Zane Diallo", "Security Officer", "Facilities", "zane.diallo@streamhub.example", "+1-555-0139", "B-1011", "2020-03-30"),
    (7, "Iris Kumar", "Financial Analyst", "Finance", "iris.kumar@streamhub.example", "+1-555-0119", "B-1160", "2024-01-08"),
]

_REPORTS = [
    (1, "2026-06-05 09:12:00", "Iris Kumar", "refund audit",
     "Q2 refund audit: six accounts show a 100% refund rate - eighteen refunds, $539.82, February to May 2026. "
     "Company average refund rate is 1.8%. Recommending a full investigation."),
    (2, "2026-05-02 14:40:00", "Zane Diallo", "facilities",
     "Recurring cooling alarms on the finance floor. Maintenance scheduled with the night engineer."),
    (3, "2026-04-20 11:05:00", "Tomas Fischer", "it",
     "Ticket 8841 - refund station 2 lacks per-user session logging. Flagged, not prioritized."),
]

_REFUND_NIGHTS = ["2026-02-11", "2026-03-17", "2026-04-08", "2026-05-19"]

# account_id -> sock account details; refunds are (night_index, time) in order,
# and the k-th refund uses the account's k-th invoice.
_SOCK = {
    401: {"name": "Zoe Haddad", "signup": "2025-12-28", "sub": 801, "inv": [3201, 3202, 3203],
          "refunds": [(0, "23:26:41"), (1, "23:12:05"), (2, "23:41:22")]},
    402: {"name": "Omar Silva", "signup": "2026-01-04", "sub": 802, "inv": [3204, 3205, 3206],
          "refunds": [(0, "23:31:05"), (2, "22:58:47"), (3, "23:16:10")]},
    403: {"name": "Elif Tanaka", "signup": "2026-01-19", "sub": 803, "inv": [3207, 3208, 3209],
          "refunds": [(0, "23:47:22"), (2, "23:20:55"), (3, "23:29:41")]},
    404: {"name": "Noah Petrov", "signup": "2026-02-02", "sub": 804, "inv": [3210, 3211, 3212],
          "refunds": [(1, "23:29:18"), (2, "23:07:36"), (3, "23:48:02")]},
    405: {"name": "Mia Alvarez", "signup": "2026-02-02", "sub": 805, "inv": [3213, 3214, 3215],
          "refunds": [(1, "23:44:51"), (2, "23:52:14"), (3, "22:56:33")]},
    406: {"name": "Leo Ito", "signup": "2026-02-16", "sub": 806, "inv": [3216, 3217, 3218],
          "refunds": [(1, "23:58:09"), (2, "23:33:40"), (3, "23:41:55")]},
}

_SOCK_REASONS = ["duplicate charge", "accidental renewal", "unrecognized charge"]

_NORMAL_REFUND_DAYS = [
    "2026-01-12 10:22:00", "2026-01-27 15:03:00", "2026-02-04 09:41:00", "2026-02-19 16:18:00",
    "2026-03-03 11:07:00", "2026-03-24 14:55:00", "2026-04-02 13:20:00", "2026-04-16 10:48:00",
    "2026-04-29 17:12:00", "2026-05-07 09:33:00", "2026-05-21 15:44:00", "2026-05-27 12:01:00",
]

_STATEMENTS = [
    (1, 2, "2026-06-09 09:20:00", "Iris Kumar",
     "Night work is mine, yes. The finance floor sits on my cooling route when the AC acts up - you'll find my "
     "maintenance emails. I don't have REFUND-ROOM access and I've never needed it."),
    (2, 3, "2026-06-09 10:05:00", "Iris Kumar",
     "refunddesk-2 is the station login the whole support floor knows. I keep it alive for coverage. I can't tell "
     "you who used it at 2 a.m. - that is exactly why June has been asking for per-user accounts for months."),
    (3, 4, "2026-06-09 11:40:00", "Iris Kumar",
     "There is a ticket - 8841 - about per-user session logging on the refund station. It never got prioritized. "
     "The login tells you which station, not which hands."),
    (4, 5, "2026-06-10 09:10:00", "Zane Diallo",
     "Refund room policy: every entry needs an individual badge swipe, no tailgating, since the 2025 audit. The "
     "badge log is the only reliable record of who physically went in."),
    (5, 6, "2026-06-10 10:30:00", "Zane Diallo",
     "I walk the finance floor on patrol, sometimes after midnight. The refund room stays locked unless there is a "
     "work order; my patrol never takes me inside."),
    (6, 1, "2026-06-11 14:25:00", "Iris Kumar",
     "I build the refund analytics. I don't issue refunds. If you think someone got in, check the badge logs - "
     "that's what they're for."),
    (7, 7, "2026-06-11 15:50:00", "Zane Diallo",
     "The audit speaks for itself: eighteen refunds, six accounts, one hundred percent refund rate. Find who was "
     "at the refund station on those nights."),
]

_EMAILS = [
    (1, 5, 3, "2026-01-28 10:12:00", "Shared station login",
     "Marcus - the refund desk still runs on the shared refunddesk-2 login. Half of support has used it. Can we "
     "finally get per-user accounts? - June"),
    (2, 2, 7, "2026-03-16 18:05:00", "Cooling maintenance tonight",
     "Heads up - cooling maintenance on the finance floor tonight 22:45-01:15. Badge stays active. Apologies for "
     "the noise. - Vera"),
    (3, 2, 7, "2026-05-18 17:48:00", "Cooling maintenance tonight",
     "Same drill as March - finance floor cooling checks tonight 22:45-01:15. Don't trip on the cabling. - Vera"),
    (4, 4, 5, "2026-04-20 11:15:00", "Ticket 8841 - refund station sessions",
     "Still queued. Refund station 2 has no per-user session logging, so the login only proves which station was "
     "used. No ETA. - Tomas"),
]

_TIPS = [
    (1, "2026-06-06 08:44:00", "Ask the night engineer what she does on the finance floor. Nobody works that late for fun."),
    (2, "2026-06-07 21:03:00", "That refund desk login half the building knows? Useless. Watch the door, not the mouse."),
    (3, "2026-06-08 19:27:00", "Six accounts, one hand. Follow the money and you'll see where it sleeps."),
]

_NOISE_DOORS = ["LOBBY", "SUPPORT-FLOOR", "DATA-CENTER", "MAILROOM"]


def _authored_badges() -> list[tuple]:
    events = []
    for night in _REFUND_NIGHTS:
        # The refund room sits inside the finance floor: enter floor, then room.
        events.append((1, "FINANCE-FLOOR", "in", f"{night} 22:18:00"))
        events.append((1, "REFUND-ROOM", "in", f"{night} 22:24:00"))
        events.append((1, "REFUND-ROOM", "out", f"{night} 23:59:30"))
        events.append((1, "FINANCE-FLOOR", "out", f"{night} 23:59:59"))
    for index in (1, 3):  # maintenance nights: 2026-03-17 and 2026-05-19
        night = _REFUND_NIGHTS[index]
        events.append((2, "FINANCE-FLOOR", "in", f"{night} 22:47:00"))
        events.append((2, "FINANCE-FLOOR", "out", f"{night} 23:50:00"))
    events.append((6, "FINANCE-FLOOR", "in", f"{_REFUND_NIGHTS[2]} 23:05:00"))  # night patrol
    events.append((6, "FINANCE-FLOOR", "out", f"{_REFUND_NIGHTS[2]} 23:22:00"))
    events.append((4, "REFUND-ROOM", "in", "2026-04-21 14:12:00"))  # monitor swap
    events.append((4, "REFUND-ROOM", "out", "2026-04-21 14:40:00"))
    events.append((5, "REFUND-ROOM", "in", "2026-02-03 10:05:00"))  # daytime visit
    events.append((5, "REFUND-ROOM", "out", "2026-02-03 10:22:00"))
    return events


def ddl() -> str:
    return streamhub.ddl() + "\n" + CASE_DDL


def seed(connection: sqlite3.Connection, size: str = "small") -> None:
    """Seed StreamHub (small tier only) and append the Case 1 layer."""
    streamhub.seed(connection, "small")

    connection.executemany(
        'INSERT INTO "case_persons" (id, name, role, team, email, phone, badge_serial, hire_date) VALUES (?,?,?,?,?,?,?,?)',
        _PERSONS,
    )
    connection.executemany(
        'INSERT INTO "case_reports" (id, filed_at, filed_by, category, report) VALUES (?,?,?,?,?)',
        _REPORTS,
    )
    connection.executemany(
        'INSERT INTO "case_statements" (id, person_id, taken_at, taken_by, statement) VALUES (?,?,?,?,?)',
        _STATEMENTS,
    )
    connection.executemany(
        'INSERT INTO "case_emails" (id, sender_person_id, recipient_person_id, sent_at, subject, body) VALUES (?,?,?,?,?,?)',
        _EMAILS,
    )
    connection.executemany('INSERT INTO "case_tips" (id, received_at, tip) VALUES (?,?,?)', _TIPS)

    # --- sock accounts: six extra users with a subscription and paid invoices ---
    for account_id, spec in _SOCK.items():
        signup = date.fromisoformat(spec["signup"])
        connection.execute(
            'INSERT INTO "users" (id, name, email, country, city, signup_date, acquisition_channel, birth_year) '
            "VALUES (?,?,?,?,?,?,?,?)",
            (account_id, spec["name"],
             f'{spec["name"].lower().replace(" ", ".")}{account_id}@example.com',
             "United States", "Seattle", spec["signup"], "ads", 1991 + account_id % 12),
        )
        connection.execute(
            'INSERT INTO "subscriptions" (id, user_id, plan_id, started_at, ended_at, status, coupon_code) '
            "VALUES (?,?,?,?,?,?,?)",
            (spec["sub"], account_id, 4, (signup + timedelta(days=3)).isoformat(), None, "active", None),
        )
        for offset, invoice_id in enumerate(spec["inv"]):
            issued = date(2026, 2 + offset, 1)
            connection.execute(
                'INSERT INTO "invoices" (id, subscription_id, issued_at, amount_cents, currency, paid_at, status) '
                "VALUES (?,?,?,?,?,?,?)",
                (invoice_id, spec["sub"], issued.isoformat(), 2999, "USD", issued.isoformat(), "paid"),
            )

    # --- refunds: the 18 suspicious ones, then 12 ordinary ones ------------------
    refund_id = 0
    for account_id, spec in _SOCK.items():
        for index, (night_index, clock) in enumerate(spec["refunds"]):
            refund_id += 1
            connection.execute(
                'INSERT INTO "case_refunds" (id, invoice_id, account_user_id, amount_cents, issued_at, reason, login_used, status) '
                "VALUES (?,?,?,?,?,?,?,?)",
                (refund_id, spec["inv"][index], account_id, 2999,
                 f"{_REFUND_NIGHTS[night_index]} {clock}",
                 _SOCK_REASONS[refund_id % 3], "refunddesk-2", "paid_out"),
            )

    cursor = connection.execute(
        'SELECT MIN(invoices.id) AS invoice_id, subscriptions.user_id, MIN(invoices.amount_cents) AS amount_cents '
        'FROM "invoices" JOIN "subscriptions" ON subscriptions.id = invoices.subscription_id '
        "WHERE invoices.status = 'paid' AND invoices.id < 300 "
        "GROUP BY subscriptions.user_id ORDER BY subscriptions.user_id LIMIT 12"
    )
    ordinary = cursor.fetchall()
    logins = ["refunddesk-1", "refunddesk-3", "j.okafor", "refunddesk-1"]
    for index, (invoice_id, user_id, amount_cents) in enumerate(ordinary):
        refund_id += 1
        connection.execute(
            'INSERT INTO "case_refunds" (id, invoice_id, account_user_id, amount_cents, issued_at, reason, login_used, status) '
            "VALUES (?,?,?,?,?,?,?,?)",
            (refund_id, invoice_id, user_id, amount_cents, _NORMAL_REFUND_DAYS[index],
             "customer request", logins[index % 4], "paid_out"),
        )

    # --- badge events: authored night events + daytime noise ----------------------
    events = list(_authored_badges())
    rng = random.Random(5501)
    for person_id, *_ in _PERSONS:
        day = date(2026, 1, 2)
        while day < date(2026, 6, 12):
            day += timedelta(days=rng.randrange(1, 4))
            if rng.random() < 0.45:
                continue
            hour = rng.randrange(8, 19)
            minute = rng.randrange(60)
            door = rng.choice(_NOISE_DOORS)
            events.append((person_id, door, "in", f"{day.isoformat()} {hour:02d}:{minute:02d}:00"))
            events.append((
                person_id, door, "out",
                f"{day.isoformat()} {hour:02d}:{min(rng.randrange(10, 59) + minute, 59):02d}:00",
            ))
    connection.executemany(
        'INSERT INTO "case_badge_events" (person_id, door, direction, occurred_at) VALUES (?,?,?,?)',
        events,
    )

    # --- account links: six sock accounts share one phone/card; two innocent
    #     households share a phone across two accounts each (the decoy rule).
    links = [(account_id, "+1-555-0147", "VISA-****4417", "D-8841") for account_id in _SOCK]
    links += [(42, "+1-555-0166", "MC-****2210", "shared kiosk"), (117, "+1-555-0166", "VISA-****8802", "shared kiosk")]
    links += [(201, "+1-555-0178", "VISA-****3315", "family ipad"), (344, "+1-555-0178", "MC-****7741", "family ipad")]
    connection.executemany(
        'INSERT INTO "case_account_links" (account_user_id, recovery_phone, card_fingerprint, signup_device) VALUES (?,?,?,?)',
        links,
    )

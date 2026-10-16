"""StreamHub dataset: a streaming/SaaS product.

Deterministic generator (fixed RNG seed): identical data on every run, which keeps
grading stable. Realistic traits on purpose: NULLs, churned subscriptions, unpaid
invoices, duplicate events, and session-based event streams.
"""

import random
import sqlite3
from datetime import date, datetime, timedelta

_ID = "streamhub"

_SIZES = {
    "small": {"users": 400, "subscriptions": 800, "invoices": 3200, "events": 9000, "tickets": 260},
    "perf": {"users": 4000, "subscriptions": 8000, "invoices": 90000, "events": 200000, "tickets": 3000},
}

_CITIES = {
    "United States": ["New York", "Austin", "Seattle", "Chicago"],
    "Germany": ["Berlin", "Munich"],
    "United Kingdom": ["London", "Manchester"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro"],
    "India": ["Mumbai", "Bengaluru"],
    "Japan": ["Tokyo", "Osaka"],
    "France": ["Paris", "Lyon"],
    "Canada": ["Toronto", "Vancouver"],
    "Australia": ["Sydney", "Melbourne"],
    "Netherlands": ["Amsterdam", "Rotterdam"],
}

_FIRST_NAMES = [
    "Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Iris", "Leo", "Nina", "Omar",
    "Ravi", "Sofia", "Tomas", "Uma", "Victor", "Wren", "Xi", "Yara", "Zane", "Ana",
    "Bruno", "Cleo", "Dario", "Elif",
]
_LAST_NAMES = [
    "Alvarez", "Bauer", "Chen", "Diallo", "Eriksen", "Fischer", "Garcia", "Haddad",
    "Ito", "Jensen", "Kumar", "Lopez", "Meyer", "Novak", "Okafor", "Petrov",
    "Quinn", "Reyes", "Silva", "Tanaka", "Ueda", "Voss", "Weber", "Zhao",
]

_PLANS = [
    (1, "Free", "free", 0),
    (2, "Basic", "basic", 999),
    (3, "Standard", "standard", 1899),
    (4, "Premium", "premium", 2999),
]

_GENRES = ["Pop", "Rock", "Jazz", "Electronic", "Hip-Hop", "Classical", "Podcast", "Documentary", "Kids", "World"]
_TITLE_WORDS = [
    "Midnight", "Sunrise", "Echo", "Harbor", "Neon", "Silver", "Wild", "Golden", "Quiet", "Electric",
    "Velvet", "Coastal", "Northern", "Crimson", "Paper", "Glass", "Orbit", "Meadow", "Signal", "Ember",
]
_TITLE_NOUNS = [
    "Sessions", "Stories", "Horizons", "Waves", "Footprints", "Letters", "Seasons", "Machines", "Gardens",
    "Highways", "Signals", "Tides", "Frequencies", "Roads", "Dreams", "Secrets", "Circles", "Lanterns",
]

_CHANNELS = ["organic", "ads", "referral", "social", "partner"]
_DEVICES = ["web", "ios", "android", "tv"]
_EVENT_TYPES = ["play", "pause", "search", "browse", "login"]
_TICKET_CATEGORIES = ["billing", "playback", "account", "content"]
_TICKET_PRIORITIES = ["low", "medium", "high", "urgent"]

TABLES = {
    "users": {
        "description": "StreamHub account holders and how they signed up.",
        "grain": "one row per user",
        "columns": ["id", "name", "email", "country", "city", "signup_date", "acquisition_channel", "birth_year"],
        "types": {"id": "integer", "name": "text", "email": "text", "country": "text", "city": "text", "signup_date": "date", "acquisition_channel": "text", "birth_year": "integer"},
        "keys": {"primary": ["id"], "foreign": []},
    },
    "plans": {
        "description": "Subscription plans and their monthly price in cents.",
        "grain": "one row per plan",
        "columns": ["id", "name", "tier", "monthly_price_cents"],
        "types": {"id": "integer", "name": "text", "tier": "text", "monthly_price_cents": "integer"},
        "keys": {"primary": ["id"], "foreign": []},
    },
    "subscriptions": {
        "description": "A user's plan history; ended_at is NULL while the subscription is active.",
        "grain": "one row per subscription period",
        "columns": ["id", "user_id", "plan_id", "started_at", "ended_at", "status", "coupon_code"],
        "types": {"id": "integer", "user_id": "integer", "plan_id": "integer", "started_at": "date", "ended_at": "date", "status": "text", "coupon_code": "text"},
        "keys": {"primary": ["id"], "foreign": ["user_id -> users.id", "plan_id -> plans.id"]},
    },
    "invoices": {
        "description": "Monthly invoices; paid_at is NULL when the invoice was never paid.",
        "grain": "one row per invoice",
        "columns": ["id", "subscription_id", "issued_at", "amount_cents", "currency", "paid_at", "status"],
        "types": {"id": "integer", "subscription_id": "integer", "issued_at": "date", "amount_cents": "integer", "currency": "text", "paid_at": "date", "status": "text"},
        "keys": {"primary": ["id"], "foreign": ["subscription_id -> subscriptions.id"]},
    },
    "events": {
        "description": "App activity events such as plays, searches, and logins.",
        "grain": "one row per event (contains duplicates on purpose)",
        "columns": ["id", "user_id", "event_type", "content_id", "occurred_at", "device", "session_id"],
        "types": {"id": "integer", "user_id": "integer", "event_type": "text", "content_id": "integer", "occurred_at": "datetime", "device": "text", "session_id": "text"},
        "keys": {"primary": [], "foreign": ["user_id -> users.id", "content_id -> contents.id"]},
    },
    "contents": {
        "description": "The streaming catalog: titles, genres, and runtime.",
        "grain": "one row per title",
        "columns": ["id", "title", "genre", "release_year", "duration_minutes", "rating"],
        "types": {"id": "integer", "title": "text", "genre": "text", "release_year": "integer", "duration_minutes": "integer", "rating": "decimal"},
        "keys": {"primary": ["id"], "foreign": []},
    },
    "support_tickets": {
        "description": "Support tickets; closed_at and satisfaction_score are NULL while a ticket is open.",
        "grain": "one row per ticket",
        "columns": ["id", "user_id", "opened_at", "closed_at", "category", "priority", "satisfaction_score"],
        "types": {"id": "integer", "user_id": "integer", "opened_at": "datetime", "closed_at": "datetime", "category": "text", "priority": "text", "satisfaction_score": "integer"},
        "keys": {"primary": ["id"], "foreign": ["user_id -> users.id"]},
    },
    "campaigns": {
        "description": "Marketing campaigns with their channel, run dates, and spend in cents.",
        "grain": "one row per campaign",
        "columns": ["id", "name", "channel", "started_at", "ended_at", "spend_cents", "target_country"],
        "types": {"id": "integer", "name": "text", "channel": "text", "started_at": "date", "ended_at": "date", "spend_cents": "integer", "target_country": "text"},
        "keys": {"primary": ["id"], "foreign": []},
    },
}

RELATIONSHIPS = [
    {"from_table": "subscriptions", "from_column": "user_id", "to_table": "users", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "subscriptions", "from_column": "plan_id", "to_table": "plans", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "invoices", "from_column": "subscription_id", "to_table": "subscriptions", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "events", "from_column": "user_id", "to_table": "users", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "events", "from_column": "content_id", "to_table": "contents", "to_column": "id", "cardinality": "many-to-one"},
    {"from_table": "support_tickets", "from_column": "user_id", "to_table": "users", "to_column": "id", "cardinality": "many-to-one"},
]

_SQLITE_TYPES = {"integer": "INTEGER", "text": "TEXT", "decimal": "NUMERIC", "date": "TEXT", "boolean": "INTEGER", "datetime": "TEXT"}


def ddl() -> str:
    statements = []
    for name, spec in TABLES.items():
        columns = ", ".join(f'"{column}" {_SQLITE_TYPES[spec["types"][column]]}' for column in spec["columns"])
        primary = spec["keys"]["primary"]
        if primary:
            columns += ", PRIMARY KEY (" + ", ".join(f'"{column}"' for column in primary) + ")"
        statements.append(f'CREATE TABLE "{name}" ({columns})')
    return ";\n".join(statements) + ";"


def _day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randrange((end - start).days + 1))


def _stamp(rng: random.Random, day: date, hour_range=(7, 23)) -> str:
    hour = rng.randrange(hour_range[0], hour_range[1])
    return f"{day.isoformat()} {hour:02d}:{rng.randrange(60):02d}:{rng.randrange(60):02d}"


def seed(connection: sqlite3.Connection, size: str = "small") -> None:
    counts = _SIZES.get(size, _SIZES["small"])
    rng = random.Random(20260416)

    # --- users -----------------------------------------------------------
    countries = list(_CITIES)
    users = []
    for user_id in range(1, counts["users"] + 1):
        country = rng.choice(countries)
        name = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
        signup = _day(rng, date(2024, 1, 1), date(2025, 12, 31))
        users.append((
            user_id,
            name,
            f"{name.lower().replace(' ', '.')}{user_id}@example.com",
            country,
            rng.choice(_CITIES[country]),
            signup.isoformat(),
            rng.choice(_CHANNELS),
            rng.randrange(1960, 2006),
        ))

    # --- contents --------------------------------------------------------
    contents = []
    for content_id in range(1, 121):
        contents.append((
            content_id,
            f"{rng.choice(_TITLE_WORDS)} {rng.choice(_TITLE_NOUNS)}",
            rng.choice(_GENRES),
            rng.randrange(1995, 2026),
            rng.randrange(12, 180),
            round(rng.uniform(2.5, 4.9), 1),
        ))

    # --- campaigns (ends often NULL for running campaigns) ---------------
    campaigns = []
    for campaign_id in range(1, 13):
        started = _day(rng, date(2025, 1, 1), date(2025, 11, 1))
        running = campaign_id % 5 == 0
        ended = None if running else (started + timedelta(days=rng.randrange(20, 90))).isoformat()
        campaigns.append((
            campaign_id,
            f"{rng.choice(_TITLE_WORDS)} push #{campaign_id}",
            rng.choice(_CHANNELS),
            started.isoformat(),
            ended,
            rng.randrange(500_00, 40_000_00),
            None if rng.random() < 0.3 else rng.choice(countries),
        ))

    # --- subscriptions ---------------------------------------------------
    plan_weights = [1, 3, 5, 3]  # free is rare
    statuses = []
    subscriptions = []
    for sub_id in range(1, counts["subscriptions"] + 1):
        user = rng.choice(users)
        user_id = user[0]
        started = _day(rng, date.fromisoformat(user[5]), date(2025, 12, 31))
        plan_id = rng.choices([1, 2, 3, 4], weights=plan_weights)[0]
        active = rng.random() < 0.62
        if active:
            ended = None
            status = "paused" if rng.random() < 0.06 else "active"
        else:
            period = rng.randrange(30, 500)
            ended_date = min(started + timedelta(days=period), date(2026, 6, 30))
            ended = ended_date.isoformat() if ended_date > started else None
            status = "churned" if ended else "active"
        coupon = None if rng.random() < 0.75 else rng.choice(["WELCOME10", "STAY20", "WINBACK15", "STAY20"])
        subscriptions.append((sub_id, user_id, plan_id, started.isoformat(), ended, status, coupon))
        statuses.append((sub_id, user_id, plan_id, started, ended, status))

    # --- invoices (bounded per subscription) ------------------------------
    invoice_cap = 6 if size == "small" else 14
    prices = {plan[0]: plan[3] for plan in _PLANS}
    invoices = []
    invoice_id = 0
    today = date(2026, 6, 30)
    while invoice_id < counts["invoices"]:
        progressed = False
        for sub_id, _user_id, plan_id, started, ended, status in statuses:
            if invoice_id >= counts["invoices"]:
                break
            months = 0
            issued = started.replace(day=1)
            while months < invoice_cap:
                if issued > (date.fromisoformat(ended) if ended else today):
                    break
                if issued >= date(2024, 1, 1):
                    if invoice_id >= counts["invoices"]:
                        break
                    invoice_id += 1
                    amount = prices[plan_id]
                    if amount == 0:
                        continue
                    if rng.random() < 0.12:
                        amount = int(amount * 0.85)
                    age_days = (today - issued).days
                    if rng.random() < 0.9:
                        paid = issued + timedelta(days=rng.randrange(0, 6))
                        paid_at = paid.isoformat() if paid <= today else None
                        status_ = "paid" if paid_at else "open"
                    else:
                        paid_at = None
                        status_ = "overdue" if age_days > 35 else "open"
                    invoices.append((invoice_id, sub_id, issued.isoformat(), amount, "USD", paid_at, status_))
                    progressed = True
                next_month = issued.month + 1
                year = issued.year + (1 if next_month > 12 else 0)
                issued = date(year, 1 if next_month > 12 else next_month, 1)
                months += 1
        if not progressed:
            break

    # --- events (with duplicate rows for dedupe practice) -----------------
    events = []
    event_id = 0
    dup_every = 40
    while len(events) < counts["events"]:
        user = rng.choice(users)
        day = _day(rng, date(2025, 10, 1), date(2026, 6, 30))
        session = f"s{rng.randrange(1, 999999):06d}"
        session_events = rng.randrange(1, 6)
        for _ in range(session_events):
            if len(events) >= counts["events"]:
                break
            event_id += 1
            event_type = rng.choices(_EVENT_TYPES, weights=[5, 2, 2, 3, 2])[0]
            content_id = rng.choice(contents)[0] if event_type in {"play", "pause", "browse"} else None
            events.append((event_id, user[0], event_type, content_id, _stamp(rng, day), rng.choice(_DEVICES), session))
        if len(events) % dup_every == 0 and len(events) < counts["events"] and events:
            events.append(events[-2])  # intentional duplicate row (same id is fine in this fixture)

    # --- support tickets ---------------------------------------------------
    tickets = []
    for ticket_id in range(1, counts["tickets"] + 1):
        user = rng.choice(users)
        opened_day = _day(rng, date(2025, 10, 1), date(2026, 6, 25))
        opened = _stamp(rng, opened_day, (8, 22))
        closed_roll = rng.random()
        if closed_roll < 0.82:
            closed_day = min(opened_day + timedelta(days=rng.randrange(0, 12)), date(2026, 6, 30))
            closed = _stamp(rng, closed_day, (8, 23))
            satisfaction = None if rng.random() < 0.15 else rng.randrange(1, 6)
        else:
            closed = None
            satisfaction = None
        tickets.append((
            ticket_id,
            user[0],
            opened,
            closed,
            rng.choice(_TICKET_CATEGORIES),
            rng.choices(_TICKET_PRIORITIES, weights=[4, 4, 2, 1])[0],
            satisfaction,
        ))

    # --- insert ------------------------------------------------------------
    for name, rows in (
        ("plans", [(p[0], p[1], p[2], p[3]) for p in _PLANS]),
        ("users", users),
        ("contents", contents),
        ("campaigns", campaigns),
        ("subscriptions", subscriptions),
        ("invoices", invoices),
        ("events", events),
        ("support_tickets", tickets),
    ):
        spec = TABLES[name]
        quoted = ", ".join(f'"{column}"' for column in spec["columns"])
        placeholders = ", ".join("?" for _ in spec["columns"])
        connection.executemany(f'INSERT INTO "{name}" ({quoted}) VALUES ({placeholders})', rows)

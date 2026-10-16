"""Bookings dataset: one deliberately dirty denormalized table.

Built for data cleaning, validation, and schema-design lessons: mixed date formats,
inconsistent casing and whitespace, duplicate references, missing emails, and
promo-code typos.
"""

import random
import sqlite3

_ID = "bookings"

_SIZES = {"small": 1200, "perf": 12000}

_HOTELS = [
    ("Grand Meridian", "Lisbon"),
    ("Harbor View Inn", "Amsterdam"),
    ("Alpine Lodge", "Zurich"),
    ("Casa del Sol", "Seville"),
    ("Northern Lights", "Oslo"),
    ("Blue Reef Resort", "Cancun"),
]
_ROOM_TYPES = ["Standard", "Double", "Suite", "Family", "Deluxe"]
_FIRST_NAMES = ["Ana", "Ben", "Cara", "Dario", "Elena", "Felix", "Greta", "Hugo", "Ines", "Jonas", "Kaia", "Luca", "Mara", "Nils", "Olga", "Piet", "Rosa", "Sven", "Tina", "Ugo"]
_LAST_NAMES = ["Anders", "Bianchi", "Costa", "Duarte", "Eriksen", "Fischer", "Gomez", "Hansen", "Ivanov", "Jansen", "Keller", "Larsen", "Moreau", "Novak", "Olsen", "Pereira"]
_PROMOS = ["SAVE10", "SAVE10", "STAY15", "WINTER20", "EARLYBIRD"]
_PROMO_TYPOS = ["save10", "SAVE 10", "SAVE-10", "sav10", "StAy15", "winter 20"]
_FORMATS = ["iso", "us", "month", "dotted"]

TABLES = {
    "bookings_raw": {
        "description": "Raw hotel booking extract: duplicated references, mixed date formats, messy text fields.",
        "grain": "one row per booking record (duplicates included)",
        "columns": ["booking_ref", "guest_name", "email", "phone", "hotel_name", "hotel_city", "room_type", "check_in", "check_out", "nights", "rate_text", "promo_code", "notes"],
        "types": {"booking_ref": "text", "guest_name": "text", "email": "text", "phone": "text", "hotel_name": "text", "hotel_city": "text", "room_type": "text", "check_in": "text", "check_out": "text", "nights": "integer", "rate_text": "text", "promo_code": "text", "notes": "text"},
        "keys": {"primary": [], "foreign": []},
    },
}

RELATIONSHIPS = []

_SQLITE_TYPES = {"integer": "INTEGER", "text": "TEXT"}

_RATE = {"Standard": 95, "Double": 130, "Suite": 240, "Family": 180, "Deluxe": 310}
_NOTES = [
    "late check-in requested",
    "allergic to feather pillows",
    "anniversary stay",
    "needs parking",
    None,
    None,
    None,
]


def ddl() -> str:
    statements = []
    for name, spec in TABLES.items():
        columns = ", ".join(f'"{column}" {_SQLITE_TYPES[spec["types"][column]]}' for column in spec["columns"])
        statements.append(f'CREATE TABLE "{name}" ({columns})')
    return ";\n".join(statements) + ";"


def _format_date(value, style: str) -> str:
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if style == "iso":
        return value.isoformat()
    if style == "us":
        return f"{value.month:02d}/{value.day:02d}/{value.year}"
    if style == "month":
        return f"{month_names[value.month - 1]} {value.day}, {value.year}"
    return f"{value.day}.{value.month}.{value.year}"


def _phone(rng: random.Random) -> str:
    style = rng.randrange(3)
    if style == 0:
        return f"+1 555-{rng.randrange(1000, 9999)}"
    if style == 1:
        return f"(555) 01{rng.randrange(0, 10)}-{rng.randrange(1000, 9999)}"
    return f"555.{rng.randrange(100, 999)}.{rng.randrange(1000, 9999)}"


def seed(connection: sqlite3.Connection, size: str = "small") -> None:
    count = _SIZES.get(size, _SIZES["small"])
    rng = random.Random(77321)

    import datetime

    rows = []
    for index in range(1, count + 1):
        first, last = rng.choice(_FIRST_NAMES), rng.choice(_LAST_NAMES)
        guest = f"{first} {last}" if rng.random() > 0.15 else f" {first.lower()} {last.upper()} "
        hotel, city = rng.choice(_HOTELS)
        room = rng.choice(_ROOM_TYPES)
        check_in = datetime.date(2025, 1, 1) + datetime.timedelta(days=rng.randrange(0, 700))
        nights = rng.randrange(1, 9)
        check_out = check_in + datetime.timedelta(days=nights)
        style = rng.choice(_FORMATS)
        reported_nights = nights + (rng.choice([-1, 1]) if rng.random() < 0.3 else 0)
        rate = _RATE[room] + rng.choice([-20, -10, 0, 0, 0, 10, 25])
        rate_style = rng.randrange(4)
        if rate_style == 0:
            rate_text = f"${rate}.00"
        elif rate_style == 1:
            rate_text = f"{rate}"
        elif rate_style == 2:
            rate_text = f"EUR {rate}"
        else:
            rate_text = f"${rate}.50"
        promo = rng.choice(_PROMOS)
        if rng.random() < 0.18:
            promo = rng.choice(_PROMO_TYPOS)
        elif rng.random() < 0.25:
            promo = None
        email = None
        if rng.random() > 0.12:
            email = f"{first.lower()}.{last.lower()}@example.com"
            if rng.random() < 0.03:
                email = email.replace(".", "..")
        duplicate = rng.random() < 0.06 and rows
        if duplicate:
            source = rng.choice(rows)
            booking_ref = source[0]
            guest = source[1].title()
            email = source[2]
        else:
            booking_ref = f"BK-{2025 + index // 400}-{index:04d}"
        rows.append((
            booking_ref,
            guest,
            email,
            _phone(rng) if rng.random() > 0.05 else "",
            hotel,
            city,
            room if rng.random() > 0.1 else room.lower(),
            _format_date(check_in, style),
            _format_date(check_out, style),
            reported_nights,
            rate_text,
            promo,
            rng.choice(_NOTES),
        ))

    spec = TABLES["bookings_raw"]
    quoted = ", ".join(f'"{column}"' for column in spec["columns"])
    placeholders = ", ".join("?" for _ in spec["columns"])
    connection.executemany(f'INSERT INTO "bookings_raw" ({quoted}) VALUES ({placeholders})', rows)

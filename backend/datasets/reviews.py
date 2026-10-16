"""Reviews dataset: product reviews with JSON attributes and uneven text quality."""

import json
import random
import sqlite3
from datetime import date, timedelta

_ID = "reviews"

_SIZES = {"small": 1500, "perf": 12000}

_PRODUCT_WORDS = [
    "Aurora", "Nimbus", "Trail", "Lumen", "Cobalt", "Willow", "Ranger", "Pulse",
    "Ember", "Drift", "Onyx", "Zephyr", "Cedar", "Solar", "Atlas", "Pixel",
]
_PRODUCT_NOUNS = ["Headphones", "Speaker", "Backpack", "Lamp", "Keyboard", "Bottle", "Jacket", "Watch", "Chair", "Camera"]
_FIRST_NAMES = ["Alex", "Bianca", "Carlos", "Dana", "Emil", "Fatima", "Grace", "Hiro", "Ines", "Jon", "Kira", "Liam", "Maya", "Noor", "Oscar", "Priya", "Quinn", "Rita", "Sam", "Tara"]
_LAST_INITIALS = list("ABCDEFGHIJKLMNOPRSTVWZ")

_POSITIVE = [
    "Works exactly as described. Very happy with this purchase.",
    "Excellent quality for the price. Would buy again.",
    "Arrived fast and works perfectly. No complaints at all.",
    "A big upgrade over what I had before. Recommended.",
    "Sturdy, well made, and easy to set up.",
]
_NEUTRAL = [
    "Does the job. Nothing special, nothing terrible.",
    "Decent, but the instructions could be clearer.",
    "Okay for the price. I expected slightly better finish.",
    "It is fine. I might look at other options next time.",
]
_NEGATIVE = [
    "Stopped working after two weeks. Disappointed.",
    "Arrived scratched and the box was damaged.",
    "Not worth the price. I am returning it.",
    "The description was misleading. Would not recommend.",
]
_COLORS = ["black", "white", "silver", "blue", "green", "red", None]
_SIZES_OPT = ["S", "M", "L", "XL", None]

TABLES = {
    "reviews": {
        "description": "Product reviews with a JSON attributes column (size, color, votes, photos).",
        "grain": "one row per review",
        "columns": ["review_id", "product_id", "product_name", "reviewer", "rating", "review_text", "attributes", "created_at", "verified"],
        "types": {"review_id": "integer", "product_id": "integer", "product_name": "text", "reviewer": "text", "rating": "integer", "review_text": "text", "attributes": "text", "created_at": "datetime", "verified": "boolean"},
        "keys": {"primary": ["review_id"], "foreign": []},
    },
}

RELATIONSHIPS = []

_SQLITE_TYPES = {"integer": "INTEGER", "text": "TEXT", "boolean": "INTEGER", "datetime": "TEXT"}


def ddl() -> str:
    statements = []
    for name, spec in TABLES.items():
        columns = ", ".join(f'"{column}" {_SQLITE_TYPES[spec["types"][column]]}' for column in spec["columns"])
        primary = spec["keys"]["primary"]
        if primary:
            columns += ", PRIMARY KEY (" + ", ".join(f'"{column}"' for column in primary) + ")"
        statements.append(f'CREATE TABLE "{name}" ({columns})')
    return ";\n".join(statements) + ";"


def seed(connection: sqlite3.Connection, size: str = "small") -> None:
    count = _SIZES.get(size, _SIZES["small"])
    rng = random.Random(481516)

    products = []
    for product_id in range(1, 49):
        products.append((product_id, f"{rng.choice(_PRODUCT_WORDS)} {rng.choice(_PRODUCT_NOUNS)}"))

    rows = []
    start = date(2025, 1, 1)
    for review_id in range(1, count + 1):
        product_id, product_name = rng.choice(products)
        rating = rng.choices([1, 2, 3, 4, 5], weights=[1, 2, 3, 6, 8])[0]
        text = rng.choice(_POSITIVE if rating >= 4 else _NEGATIVE if rating <= 2 else _NEUTRAL)
        attributes = {
            "color": rng.choice(_COLORS),
            "size": rng.choice(_SIZES_OPT),
            "helpful_votes": rng.randrange(0, 60),
            "photos": rng.randrange(0, 5),
        }
        if rng.random() < 0.25:
            attributes.pop("size", None)
        if rng.random() < 0.2:
            attributes["verified_buyer"] = bool(rng.random() < 0.8)
        when = start + timedelta(days=rng.randrange(0, 560), hours=rng.randrange(24), minutes=rng.randrange(60))
        rows.append((
            review_id,
            product_id,
            product_name,
            f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_INITIALS)}.",
            rating,
            text,
            json.dumps({key: value for key, value in attributes.items() if value is not None}, separators=(",", ":")),
            when.strftime("%Y-%m-%d %H:%M:%S"),
            1 if rng.random() < 0.72 else 0,
        ))

    spec = TABLES["reviews"]
    quoted = ", ".join(f'"{column}"' for column in spec["columns"])
    placeholders = ", ".join("?" for _ in spec["columns"])
    connection.executemany(f'INSERT INTO "reviews" ({quoted}) VALUES ({placeholders})', rows)

"""Dataset registry shared by every learning runner.

A dataset is a named SQLite fixture with:
  - ``ddl()`` returning CREATE TABLE statements,
  - ``seed(connection, size)`` inserting deterministic rows,
  - ``TABLES`` metadata (columns, types, keys, grain) for the schema navigator,
  - ``RELATIONSHIPS`` for the navigator's relationship hints.

Small tiers are cheap enough to rebuild per attempt; the ``perf`` tier is reserved
for performance and efficiency lessons.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

if __package__:
    from . import bookings, case_streamhub, northwind, reviews, streamhub
else:
    import bookings
    import case_streamhub
    import northwind
    import reviews
    import streamhub


@dataclass(frozen=True)
class Dataset:
    id: str
    name: str
    summary: str
    module: object


DATASETS = {
    "northwind": Dataset(
        id="northwind",
        name="Northwind",
        summary="The classic business schema: customers, orders, products, and shipping.",
        module=northwind,
    ),
    "streamhub": Dataset(
        id="streamhub",
        name="StreamHub",
        summary="A streaming product: users, subscriptions, invoices, events, and support tickets.",
        module=streamhub,
    ),
    "bookings": Dataset(
        id="bookings",
        name="Bookings",
        summary="A deliberately messy hotel bookings extract for cleaning and schema design.",
        module=bookings,
    ),
    "reviews": Dataset(
        id="reviews",
        name="Reviews",
        summary="Product reviews with JSON attributes for JSON and text analysis.",
        module=reviews,
    ),
    "case_streamhub": Dataset(
        id="case_streamhub",
        name="StreamHub Case File",
        summary="StreamHub's product data plus the case layer for the refund investigation: staff, refunds, badge events, statements, emails, and tips.",
        module=case_streamhub,
    ),
}

DEFAULT_SIZE = "small"
_SIZES = ("small", "perf")


class UnknownDataset(KeyError):
    pass


def dataset_ids() -> list[str]:
    return list(DATASETS)


def get(dataset_id: str) -> Dataset:
    dataset = DATASETS.get(dataset_id)
    if dataset is None:
        raise UnknownDataset(dataset_id)
    return dataset


def connect(dataset_id: str, size: str = DEFAULT_SIZE) -> sqlite3.Connection:
    """Return a fresh in-memory connection with the dataset seeded."""
    module = get(dataset_id).module
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(module.ddl())
    module.seed(connection, size if size in _SIZES else DEFAULT_SIZE)
    connection.commit()
    return connection


def write_dataset_file(dataset_id: str, size: str, path: Path, *, read_only: bool = True) -> None:
    """Seed the dataset into a real file.

    Challenge bridge files are read-only. SQL Scratch workspace copies opt out so
    the learner can create tables and modify the isolated copy.
    """
    module = get(dataset_id).module
    connection = sqlite3.connect(path)
    try:
        connection.executescript(module.ddl())
        module.seed(connection, size if size in _SIZES else DEFAULT_SIZE)
        connection.commit()
    finally:
        connection.close()
    try:
        path.chmod(0o444 if read_only else 0o600)
    except OSError:
        pass


def table_rows(dataset_id: str, tables: list[str], size: str = DEFAULT_SIZE, limit: int = 200) -> dict[str, list[dict]]:
    """Rows as dictionaries, for the guided Python runner."""
    connection = connect(dataset_id, size)
    try:
        data: dict[str, list[dict]] = {}
        for table in tables:
            rows = connection.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,)).fetchall()
            data[table] = [dict(row) for row in rows]
        return data
    finally:
        connection.close()


def schema_metadata(dataset_id: str, tables: Optional[list[str]] = None) -> dict:
    """Schema shape consumed by the frontend navigator."""
    module = get(dataset_id).module
    table_specs = module.TABLES
    names = [name for name in table_specs if not tables or name in tables]
    return {
        "tables": [{"name": name, **table_specs[name]} for name in names],
        "relationships": [
            relationship
            for relationship in module.RELATIONSHIPS
            if relationship["from_table"] in names and relationship["to_table"] in names
        ],
    }


def all_metadata() -> list[dict]:
    """Everything the frontend needs to switch datasets and explore schemas."""
    metadata = []
    for dataset in DATASETS.values():
        shape = schema_metadata(dataset.id)
        metadata.append(
            {
                "id": dataset.id,
                "name": dataset.name,
                "summary": dataset.summary,
                "tables": shape["tables"],
                "relationships": shape["relationships"],
            }
        )
    return metadata

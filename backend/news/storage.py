"""Cached articles storage, deduplication, and expiry for the news feature."""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .models import FeedConfig, FeedFetchResult, NewsItem, NewsResponse


class NewsStorage:
    """Thread-safe file-based storage for cached news items."""

    def __init__(
        self,
        cache_path: Path,
        max_total_items: int = 100,
        max_age_hours: int = 48,
    ):
        self.cache_path = cache_path
        self.max_total_items = max_total_items
        self.max_age = timedelta(hours=max_age_hours)
        self._lock = Lock()
        self._ensure_cache_file()

    def _ensure_cache_file(self) -> None:
        """Create cache file with empty structure if it doesn't exist."""
        if not self.cache_path.exists():
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._write({"items": [], "fetchedAt": None, "stale": True})

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                with self.cache_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {"items": [], "fetchedAt": None, "stale": True}
        return data

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            tmp_path = self.cache_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=self._json_default)
            tmp_path.replace(self.cache_path)

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def get_response(self, limit: int = 5) -> NewsResponse:
        """Get cached items as a NewsResponse, newest first, limited."""
        data = self._read()
        items_data = data.get("items", [])
        fetched_at_str = data.get("fetchedAt")
        stale = data.get("stale", True)

        items = [NewsItem(**item) for item in items_data]
        items.sort(key=lambda x: x.publishedAt, reverse=True)

        fetched_at = datetime.fromisoformat(fetched_at_str) if fetched_at_str else datetime.now(timezone.utc)

        return NewsResponse(
            items=items[:limit],
            fetchedAt=fetched_at,
            stale=stale,
        )

    def update_from_feed_results(self, results: list[FeedFetchResult], feed_configs: list[FeedConfig]) -> None:
        """
        Merge feed fetch results into cache.

        - Deduplicates by stable ID
        - Keeps newest items up to max_total_items
        - Removes items older than max_age
        - Updates fetchedAt to the latest successful fetch time
        - Sets stale=False only if at least one feed succeeded
        """
        data = self._read()
        existing_items: dict[str, dict] = {item["id"]: item for item in data.get("items", [])}

        any_success = False
        latest_success_time = None

        for result in results:
            if not result.success:
                continue

            any_success = True
            if latest_success_time is None or result.fetchedAt > latest_success_time:
                latest_success_time = result.fetchedAt

            for item in result.items:
                item_dict = item.model_dump(mode="json")
                existing_items[item.id] = item_dict

        # Remove expired items
        cutoff = datetime.now(timezone.utc) - self.max_age
        valid_items = [
            item for item in existing_items.values()
            if datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")) >= cutoff
        ]

        # Sort newest first and cap total
        valid_items.sort(key=lambda x: x["publishedAt"], reverse=True)
        valid_items = valid_items[: self.max_total_items]

        fetched_at = latest_success_time or datetime.now(timezone.utc)
        self._write({
            "items": valid_items,
            "fetchedAt": fetched_at.isoformat(),
            "stale": not any_success,
        })

    def clear(self) -> None:
        """Clear all cached items (used for testing)."""
        self._write({"items": [], "fetchedAt": None, "stale": True})


def create_stable_id(source: str, guid_or_link: str) -> str:
    """Create a stable deduplication ID from source and feed entry GUID/link."""
    import hashlib

    # Normalize the source name to lowercase, no spaces
    source_key = source.lower().replace(" ", "")
    # Use a hash of the GUID/link for uniqueness
    hash_suffix = hashlib.sha256(guid_or_link.encode()).hexdigest()[:16]
    return f"{source_key}|{hash_suffix}"
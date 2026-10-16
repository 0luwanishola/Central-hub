"""Feed fetching, parsing, and normalization for the news feature."""

import asyncio
import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import httpx

from .models import FeedConfig, FeedFetchResult, NewsItem
from .storage import create_stable_id

logger = logging.getLogger(__name__)

# Feed fetching constraints
FETCH_TIMEOUT = 10.0  # seconds
MAX_FEED_SIZE = 1_000_000  # 1 MB
USER_AGENT = "CentralHub/1.0 (+https://centralhub.example/bot)"


def parse_feed_date(entry: dict) -> datetime | None:
    """Extract publication date from a feedparser entry."""
    # feedparser provides parsed dates in several fields
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        if entry.get(field):
            try:
                return datetime(*entry[field][:6], tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue

    # Fallback: try string fields
    for field in ("published", "updated", "created"):
        if entry.get(field):
            try:
                # feedparser also provides *_parsed but sometimes we only have string
                parsed = feedparser.parse(entry[field])
                if parsed.entries and parsed.entries[0].get("published_parsed"):
                    return datetime(*parsed.entries[0]["published_parsed"][:6], tzinfo=timezone.utc)
            except Exception:
                continue

    return None


def extract_entry_guid(entry: dict, feed_url: str) -> str:
    """Extract a stable identifier from a feed entry."""
    # Try standard GUID field
    if entry.get("id"):
        return entry["id"]
    if entry.get("guid"):
        return entry["guid"]
    # Fallback to link
    if entry.get("link"):
        return entry["link"]
    # Last resort: hash of title + feed URL
    title = entry.get("title", "")
    import hashlib

    return hashlib.sha256(f"{feed_url}|{title}".encode()).hexdigest()[:32]


def clean_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode entities properly: feeds mix plain text with escaped markup, and the
    # old hand-rolled list was effectively a no-op for everything but &nbsp;.
    text = html.unescape(text)
    # Normalize whitespace (this also folds decoded non-breaking spaces).
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_entry(entry: dict, feed_config: FeedConfig, fetch_time: datetime) -> NewsItem | None:
    """Convert a feedparser entry to a NewsItem."""
    title = clean_html(entry.get("title", ""))
    if not title:
        return None

    link = entry.get("link", "")
    if not link:
        return None

    # Validate URL
    try:
        parsed = urlparse(link)
        if not parsed.scheme or not parsed.netloc:
            return None
    except Exception:
        return None

    published = parse_feed_date(entry)
    if published is None:
        published = fetch_time

    guid = extract_entry_guid(entry, str(feed_config.url))
    item_id = create_stable_id(feed_config.name, guid)

    return NewsItem(
        id=item_id,
        title=title,
        url=link,
        source=feed_config.name,
        publishedAt=published,
    )


async def fetch_single_feed(
    client: httpx.AsyncClient,
    feed_config: FeedConfig,
) -> FeedFetchResult:
    """Fetch and parse a single RSS/Atom feed."""
    fetch_time = datetime.now(timezone.utc)
    source = feed_config.name
    url = str(feed_config.url)

    try:
        response = await client.get(
            url,
            timeout=FETCH_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_FEED_SIZE:
            raise ValueError(f"Feed too large: {content_length} bytes")

        content = response.text
        if len(content) > MAX_FEED_SIZE:
            raise ValueError(f"Feed content too large: {len(content)} bytes")

        # Parse with feedparser
        parsed = feedparser.parse(content)

        if parsed.bozo and parsed.get("bozo_exception"):
            logger.warning("Feed parse warning for %s: %s", source, parsed.bozo_exception)

        items: list[NewsItem] = []
        for entry in parsed.entries[: feed_config.maxItems]:
            try:
                item = normalize_entry(entry, feed_config, fetch_time)
                if item:
                    items.append(item)
            except Exception as e:
                logger.debug("Failed to normalize entry from %s: %s", source, e)
                continue

        logger.info("Fetched %d items from %s", len(items), source)
        return FeedFetchResult(
            source=source,
            items=items,
            fetchedAt=fetch_time,
            error=None,
        )

    except httpx.TimeoutException:
        error = f"Timeout fetching {source}"
        logger.warning(error)
        return FeedFetchResult(source=source, items=[], fetchedAt=fetch_time, error=error)
    except httpx.HTTPStatusError as e:
        error = f"HTTP {e.response.status_code} from {source}"
        logger.warning(error)
        return FeedFetchResult(source=source, items=[], fetchedAt=fetch_time, error=error)
    except Exception as e:
        error = f"Failed to fetch {source}: {e}"
        logger.warning(error)
        return FeedFetchResult(source=source, items=[], fetchedAt=fetch_time, error=error)


async def fetch_all_feeds(
    client: httpx.AsyncClient,
    feed_configs: list[FeedConfig],
) -> list[FeedFetchResult]:
    """Fetch all configured feeds concurrently."""
    tasks = [fetch_single_feed(client, config) for config in feed_configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed: list[FeedFetchResult] = []
    for config, result in zip(feed_configs, results, strict=False):
        if isinstance(result, FeedFetchResult):
            processed.append(result)
        elif isinstance(result, Exception):
            logger.error("Unexpected error fetching %s: %s", config.name, result)
            processed.append(
                FeedFetchResult(
                    source=config.name,
                    items=[],
                    fetchedAt=datetime.now(timezone.utc),
                    error=str(result),
                )
            )
        else:
            processed.append(
                FeedFetchResult(
                    source=config.name,
                    items=[],
                    fetchedAt=datetime.now(timezone.utc),
                    error="Unknown error",
                )
            )

    return processed
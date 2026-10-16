"""Normalized article and response schemas for the news feature."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl


class NewsItem(BaseModel):
    """A single normalized news article for the homepage feed."""

    id: Annotated[str, Field(description="Stable deduplication ID")]
    title: Annotated[str, Field(min_length=1, max_length=500, description="Article headline")]
    url: Annotated[HttpUrl, Field(description="Publisher article URL")]
    source: Annotated[str, Field(min_length=1, max_length=100, description="Publisher name")]
    publishedAt: Annotated[datetime, Field(description="Publication timestamp in UTC")]

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "arstechnica|https://arstechnica.com/example-article/",
                "title": "New breakthrough in quantum computing",
                "url": "https://arstechnica.com/example-article/",
                "source": "Ars Technica",
                "publishedAt": "2026-10-08T12:00:00Z",
            }
        }
    }


class NewsResponse(BaseModel):
    """Response for GET /api/news/latest."""

    items: Annotated[list[NewsItem], Field(description="Latest news items, newest first")]
    fetchedAt: Annotated[datetime, Field(description="When the cache was last successfully refreshed")]
    stale: Annotated[bool, Field(description="True if the last refresh failed and data may be outdated")]

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": "arstechnica|https://arstechnica.com/example-article/",
                        "title": "New breakthrough in quantum computing",
                        "url": "https://arstechnica.com/example-article/",
                        "source": "Ars Technica",
                        "publishedAt": "2026-10-08T12:00:00Z",
                    }
                ],
                "fetchedAt": "2026-10-08T12:05:00Z",
                "stale": False,
            }
        }
    }


class FeedConfig(BaseModel):
    """Configuration for a single RSS/Atom feed source."""

    name: Annotated[str, Field(min_length=1, max_length=100, description="Friendly publisher name")]
    url: Annotated[HttpUrl, Field(description="Feed URL")]
    maxItems: Annotated[int, Field(ge=1, le=50, default=20, description="Max items to keep from this feed")]


class FeedFetchResult(BaseModel):
    """Result of fetching and parsing a single feed."""

    source: Annotated[str, Field(description="Publisher name")]
    items: Annotated[list[NewsItem], Field(description="Normalized items from this feed")]
    fetchedAt: Annotated[datetime, Field(description="When this feed was fetched")]
    error: Annotated[str | None, Field(default=None, description="Error message if fetch failed")]

    @property
    def success(self) -> bool:
        return self.error is None
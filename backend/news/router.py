"""Homepage news API endpoint."""

from fastapi import APIRouter, Query, Request

from .models import NewsResponse
from .storage import NewsStorage

router = APIRouter(prefix="/api/news", tags=["news"])


def get_news_storage(request: Request) -> NewsStorage:
    """Get the news storage instance from app state."""
    return request.app.state.news_storage


@router.get("/latest", response_model=NewsResponse)
async def get_latest_news(
    request: Request,
    limit: int = Query(5, ge=1, le=10, description="Maximum number of items to return"),
) -> NewsResponse:
    """
    Get the latest cached news headlines.

    Returns up to `limit` items (default 5, max 10), newest first.
    The response includes fetch metadata for freshness indication.
    """
    storage = get_news_storage(request)
    return storage.get_response(limit=limit)
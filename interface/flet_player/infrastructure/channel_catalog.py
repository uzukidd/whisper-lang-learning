"""Channel browse catalog facade routed by channel source."""

from __future__ import annotations

from ..domain.youtube_models import DEFAULT_CHANNEL_SOURCE, YouTubeVideoSummary
from .error_log import print_error
from .youtube_catalog import (
    fetch_channel_avatar_url as _fetch_youtube_channel_avatar_url,
    fetch_channel_video_count as _fetch_youtube_channel_video_count,
    fetch_channel_videos_page as _fetch_youtube_channel_videos_page,
)


def _require_youtube(source: str) -> None:
    if source != DEFAULT_CHANNEL_SOURCE:
        print_error("_require_youtube", f"unsupported channel source: {source}")
        raise ValueError(f"Unsupported channel source: {source}")


def fetch_channel_videos_page(
    channel_url: str,
    *,
    source: str = DEFAULT_CHANNEL_SOURCE,
    page: int = 1,
    page_size: int = 5,
    proxy_url: str | None = None,
) -> tuple[list[YouTubeVideoSummary], int | None]:
    _require_youtube(source)
    return _fetch_youtube_channel_videos_page(
        channel_url,
        page=page,
        page_size=page_size,
        proxy_url=proxy_url,
    )


def fetch_channel_video_count(
    channel_url: str,
    *,
    source: str = DEFAULT_CHANNEL_SOURCE,
    proxy_url: str | None = None,
) -> int | None:
    _require_youtube(source)
    return _fetch_youtube_channel_video_count(channel_url, proxy_url=proxy_url)


def fetch_channel_avatar_url(
    channel_url: str,
    *,
    source: str = DEFAULT_CHANNEL_SOURCE,
    proxy_url: str | None = None,
) -> str | None:
    _require_youtube(source)
    return _fetch_youtube_channel_avatar_url(channel_url, proxy_url=proxy_url)

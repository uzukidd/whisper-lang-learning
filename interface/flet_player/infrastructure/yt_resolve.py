"""Resolve a YouTube page URL to a direct media URL via pytubefix."""

from __future__ import annotations

import asyncio

from .proxy_settings import load_proxy_settings
from .youtube_downloader import resolve_stream_url


async def resolve_youtube_stream_url(page_url: str, format_selector: str = "worst") -> str:
    del format_selector
    proxy_url = load_proxy_settings().effective_proxy_url()
    return await asyncio.to_thread(resolve_stream_url, page_url.strip(), proxy_url)

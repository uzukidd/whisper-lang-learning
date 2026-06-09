"""Download YouTube thumbnails through the configured proxy."""

from __future__ import annotations

import urllib.request
from pathlib import Path


def fetch_thumbnail_cached(
    video_id: str,
    url: str,
    cache_dir: str | Path,
    proxy_url: str | None,
) -> Path | None:
    if not video_id or not url:
        return None

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{video_id}.jpg"
    if dest.is_file() and dest.stat().st_size > 0:
        return dest.resolve()

    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        if proxy_url:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            )
        else:
            opener = urllib.request.build_opener()
        with opener.open(request, timeout=30) as response:
            dest.write_bytes(response.read())
        return dest.resolve()
    except Exception:
        return None

"""YouTube metadata and downloads via yt-dlp with proxy and browser cookies."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ..domain.youtube_models import YouTubeVideoDetail, YouTubeVideoSummary, normalize_watch_url
from .proxy_settings import ProxySettings, load_proxy_settings, yt_dlp_network_args, yt_dlp_proxy_args
from .yt_dlp_common import yt_dlp_command

_DEFAULT_TIMEOUT = 120


def _settings(proxy_url: str | None, settings: ProxySettings | None) -> ProxySettings:
    if settings is not None:
        return settings
    loaded = load_proxy_settings()
    if proxy_url is None:
        return loaded
    return ProxySettings(
        enabled=loaded.enabled,
        proxy_url=proxy_url,
        cookies_from_browser=loaded.cookies_from_browser,
    )


def _network_args(
    proxy_url: str | None,
    settings: ProxySettings | None,
    *,
    use_cookies: bool = True,
) -> list[str]:
    resolved = _settings(proxy_url, settings)
    effective_proxy = proxy_url if proxy_url is not None else resolved.effective_proxy_url()
    if not use_cookies:
        return yt_dlp_proxy_args(effective_proxy)
    return yt_dlp_network_args(resolved, proxy_url)


def _run_yt_dlp(
    args: list[str],
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
    *,
    use_cookies: bool = True,
) -> subprocess.CompletedProcess[str]:
    resolved = _settings(proxy_url, settings)
    try:
        proc = subprocess.run(
            [*yt_dlp_command(), *_network_args(proxy_url, settings, use_cookies=use_cookies), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"yt-dlp timed out after {timeout}s") from exc
    if (
        proc.returncode != 0
        and use_cookies
        and resolved.effective_cookies_browser()
        and "cookie" in ((proc.stderr or "") + (proc.stdout or "")).lower()
    ):
        return _run_yt_dlp(
            args,
            proxy_url=proxy_url,
            settings=settings,
            timeout=timeout,
            use_cookies=False,
        )
    print(proc.stdout)
    return proc


def _parse_yt_dlp_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for line in reversed(raw.splitlines()):
            candidate = line.strip()
            if not candidate.startswith("{"):
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        raise RuntimeError("yt-dlp returned invalid JSON")


def _run_yt_dlp_json(
    args: list[str],
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Any:
    proc = _run_yt_dlp(args, proxy_url=proxy_url, settings=settings, timeout=timeout)
    raw = (proc.stdout or "").strip()
    if raw:
        try:
            return _parse_yt_dlp_json(raw)
        except RuntimeError:
            if proc.returncode == 0:
                raise
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "yt-dlp failed"
        raise RuntimeError(msg)
    raise RuntimeError("yt-dlp returned empty output")


def fetch_video_description(
    video_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> str:
    proc = _run_yt_dlp(
        [
            "--no-playlist",
            "--skip-download",
            "--no-warnings",
            "--print",
            "description",
            video_url.strip(),
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=45,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "yt-dlp failed"
        raise RuntimeError(msg)
    return (proc.stdout or "").strip()


def fetch_video_detail(
    video_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> YouTubeVideoDetail:
    payload = _run_yt_dlp_json(
        ["--dump-single-json", "--no-playlist", "--skip-download", "--no-warnings", video_url.strip()],
        proxy_url=proxy_url,
        settings=settings,
        timeout=60,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("Invalid video metadata from yt-dlp")
    return YouTubeVideoDetail.from_yt_dlp_entry(payload)


def _playlist_total(payload: dict[str, Any]) -> int | None:
    count = payload.get("playlist_count")
    if count is None:
        return None
    if isinstance(count, int):
        return max(0, count)
    try:
        return max(0, int(count))
    except (TypeError, ValueError):
        return None


def _pick_channel_avatar_url(payload: dict[str, Any]) -> str | None:
    thumbnails = payload.get("thumbnails")
    if not isinstance(thumbnails, list):
        return None
    for thumb in thumbnails:
        if not isinstance(thumb, dict):
            continue
        if thumb.get("id") == "avatar_uncropped":
            url = thumb.get("url")
            if isinstance(url, str) and url:
                return url
    for thumb in thumbnails:
        if not isinstance(thumb, dict):
            continue
        url = thumb.get("url")
        if isinstance(url, str) and url:
            return url
    return None


def _videos_from_playlist_payload(payload: Any) -> list[YouTubeVideoSummary]:
    if not isinstance(payload, dict):
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    return [YouTubeVideoSummary.from_yt_dlp_entry(entry) for entry in entries if isinstance(entry, dict)]


def fetch_channel_videos(
    channel_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> list[YouTubeVideoSummary]:
    payload = _run_yt_dlp_json(
        ["--flat-playlist", "--dump-single-json", channel_url.strip()],
        proxy_url=proxy_url,
        settings=settings,
        timeout=90,
    )
    return _videos_from_playlist_payload(payload)


def fetch_channel_video_count(
    channel_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> int | None:
    """Fetch playlist_count with minimal entries (--playlist-end 1)."""
    proc = _run_yt_dlp(
        [
            "--flat-playlist",
            "--skip-download",
            "--no-warnings",
            "--print",
            "playlist_count",
            "--playlist-end",
            "1",
            channel_url.strip(),
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=45,
    )
    if proc.returncode == 0:
        text = (proc.stdout or "").strip()
        if text.isdigit():
            return max(0, int(text))
    payload = _run_yt_dlp_json(
        [
            "--flat-playlist",
            "--dump-single-json",
            "--playlist-end",
            "1",
            channel_url.strip(),
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=45,
    )
    if isinstance(payload, dict):
        return _playlist_total(payload)
    return None


def fetch_channel_avatar_url(
    channel_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> str | None:
    payload = _run_yt_dlp_json(
        [
            "--flat-playlist",
            "--dump-single-json",
            "--playlist-end",
            "1",
            channel_url.strip(),
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=45,
    )
    if isinstance(payload, dict):
        return _pick_channel_avatar_url(payload)
    return None


def fetch_channel_videos_page(
    channel_url: str,
    page: int = 1,
    page_size: int = 5,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> tuple[list[YouTubeVideoSummary], int | None]:
    page = max(1, page)
    page_size = max(1, page_size)
    start = (page - 1) * page_size + 1
    end = page * page_size
    payload = _run_yt_dlp_json(
        [
            "--flat-playlist",
            "--dump-single-json",
            "--playlist-items",
            f"{start}:{end}",
            channel_url.strip(),
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=90,
    )
    if not isinstance(payload, dict):
        return [], None
    return _videos_from_playlist_payload(payload), _playlist_total(payload)


def download_video_for_practice(
    video_url: str,
    cache_dir: str | Path,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    detail = fetch_video_detail(video_url, proxy_url=proxy_url, settings=settings)
    for path in sorted(cache_dir.glob(f"{detail.id}.*")):
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}:
            return path.resolve()

    output_template = str(cache_dir / f"{detail.id}.%(ext)s")
    proc = _run_yt_dlp(
        [
            "-f",
            "worst[ext=mp4]/worst",
            "--no-playlist",
            "-o",
            output_template,
            normalize_watch_url(detail.id, video_url),
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=600,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "yt-dlp download failed"
        raise RuntimeError(msg)

    for path in sorted(cache_dir.glob(f"{detail.id}.*")):
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}:
            return path.resolve()
    raise RuntimeError(f"Download finished but file not found for video {detail.id}")

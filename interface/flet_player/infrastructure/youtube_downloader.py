"""YouTube metadata and downloads via pytubefix with yt-dlp cookie fallback."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from typing import Any

_PYTUBEFIX_DOWNLOAD_TIMEOUT = 300

DownloadProgressCallback = Callable[[float, str], None]

from pytubefix import Channel, YouTube

from ..domain.youtube_models import YouTubeVideoDetail, YouTubeVideoSummary, normalize_watch_url
from . import youtube_ytdlp
from .error_log import print_error
from .proxy_settings import ProxySettings, load_proxy_settings


def _resolve_proxy_url(proxy_url: str | None) -> str | None:
    if proxy_url is not None:
        return proxy_url or None
    return load_proxy_settings().effective_proxy_url()


def _settings(proxy_url: str | None = None) -> ProxySettings:
    loaded = load_proxy_settings()
    if proxy_url is None:
        return loaded
    return ProxySettings(
        enabled=loaded.enabled,
        proxy_url=proxy_url,
        cookies_from_browser=loaded.cookies_from_browser,
    )


def _proxy_dict(proxy_url: str | None) -> dict[str, str] | None:
    effective = _resolve_proxy_url(proxy_url)
    if not effective:
        return None
    return {"http": effective, "https": effective}


def _format_duration(seconds: Any) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _upload_date_text(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y%m%d")


def _build_youtube(video_url: str, proxy_url: str | None = None) -> YouTube:
    return YouTube(video_url.strip(), proxies=_proxy_dict(proxy_url))


def _summary_from_youtube(yt: YouTube) -> YouTubeVideoSummary:
    video_id = str(yt.video_id or "")
    thumbnail_url = str(getattr(yt, "thumbnail_url", "") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
    return YouTubeVideoSummary(
        id=video_id,
        title=str(yt.title or "Untitled"),
        thumbnail_url=thumbnail_url,
        webpage_url=normalize_watch_url(video_id, str(getattr(yt, "watch_url", "") or "")),
        upload_date=_upload_date_text(getattr(yt, "publish_date", None)),
        duration_text=_format_duration(getattr(yt, "length", None)),
    )


def _sort_videos_newest_first(videos: list[YouTubeVideoSummary]) -> list[YouTubeVideoSummary]:
    def sort_key(video: YouTubeVideoSummary) -> tuple[int, str]:
        if video.upload_date.isdigit() and len(video.upload_date) == 8:
            return (1, video.upload_date)
        return (0, video.id)

    return sorted(videos, key=sort_key, reverse=True)


def _video_id_from_url(url: str) -> str:
    marker = "v="
    if marker in url:
        return url.split(marker, 1)[1].split("&", 1)[0]
    return ""


def _summary_from_video_url(url: str, proxy_url: str | None = None) -> YouTubeVideoSummary | None:
    video_id = _video_id_from_url(url)
    if not video_id:
        return None
    try:
        return _summary_from_youtube(_build_youtube(url, proxy_url))
    except Exception as exc:
        print_error("_summary_from_video_url", exc)
        return YouTubeVideoSummary(
            id=video_id,
            title="Video",
            thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            webpage_url=normalize_watch_url(video_id, url),
            upload_date="",
            duration_text="",
        )


def _fetch_channel_videos_pytubefix(channel_url: str, proxy_url: str | None = None) -> list[YouTubeVideoSummary]:
    channel = Channel(channel_url.strip(), proxies=_proxy_dict(proxy_url))
    videos: list[YouTubeVideoSummary] = []
    for url in channel.video_urls:
        summary = _summary_from_video_url(url, proxy_url)
        if summary is not None:
            videos.append(summary)
    return _sort_videos_newest_first(videos)


def fetch_channel_videos(channel_url: str, proxy_url: str | None = None) -> list[YouTubeVideoSummary]:
    settings = _settings(proxy_url)
    videos: list[YouTubeVideoSummary] = []
    try:
        videos = youtube_ytdlp.fetch_channel_videos(channel_url, proxy_url, settings=settings)
    except Exception as exc:
        print_error("fetch_channel_videos yt-dlp", exc)
        videos = []
    if not videos:
        try:
            videos = _fetch_channel_videos_pytubefix(channel_url, proxy_url)
        except Exception as exc:
            print_error("fetch_channel_videos pytubefix", exc)
            videos = []
    return _sort_videos_newest_first(videos)


def fetch_channel_videos_page(
    channel_url: str,
    page: int = 1,
    page_size: int = 5,
    proxy_url: str | None = None,
) -> tuple[list[YouTubeVideoSummary], int | None]:
    settings = _settings(proxy_url)
    page = max(1, page)
    page_size = max(1, page_size)
    try:
        videos, total = youtube_ytdlp.fetch_channel_videos_page(
            channel_url,
            page=page,
            page_size=page_size,
            proxy_url=proxy_url,
            settings=settings,
        )
        if videos or total is not None:
            return _sort_videos_newest_first(videos), total
    except Exception as exc:
        print_error("fetch_channel_videos_page", exc)
    return [], None


def fetch_channel_video_count(channel_url: str, proxy_url: str | None = None) -> int | None:
    settings = _settings(proxy_url)
    try:
        return youtube_ytdlp.fetch_channel_video_count(channel_url, proxy_url, settings=settings)
    except Exception as exc:
        print_error("fetch_channel_video_count", exc)
        return None


def fetch_channel_avatar_url(channel_url: str, proxy_url: str | None = None) -> str | None:
    settings = _settings(proxy_url)
    try:
        return youtube_ytdlp.fetch_channel_avatar_url(channel_url, proxy_url, settings=settings)
    except Exception as exc:
        print_error("fetch_channel_avatar_url", exc)
        return None


def _fetch_video_description_pytubefix(video_url: str, proxy_url: str | None = None) -> str:
    yt = _build_youtube(video_url, proxy_url)
    return str(yt.description or "").strip()


def fetch_video_description(video_url: str, proxy_url: str | None = None) -> str:
    settings = _settings(proxy_url)
    try:
        description = youtube_ytdlp.fetch_video_description(
            video_url,
            proxy_url,
            settings=settings,
        )
        if description:
            return description
    except Exception as exc:
        print_error("fetch_video_description yt-dlp", exc)
    try:
        description = _fetch_video_description_pytubefix(video_url, proxy_url)
        if description:
            return description
    except Exception as exc:
        print_error("fetch_video_description pytubefix", exc)
    return ""


def _fetch_video_detail_pytubefix(video_url: str, proxy_url: str | None = None) -> YouTubeVideoDetail:
    yt = _build_youtube(video_url, proxy_url)
    summary = _summary_from_youtube(yt)
    return YouTubeVideoDetail.from_summary(summary, description=str(yt.description or "").strip())


def _is_usable_video_detail(detail: YouTubeVideoDetail) -> bool:
    return bool(detail.id and detail.title and detail.title != "Untitled")


def fetch_video_detail(video_url: str, proxy_url: str | None = None) -> YouTubeVideoDetail:
    settings = _settings(proxy_url)
    try:
        detail = youtube_ytdlp.fetch_video_detail(video_url, proxy_url, settings=settings)
        if _is_usable_video_detail(detail):
            return detail
        print_error("fetch_video_detail yt-dlp", "metadata unusable")
    except Exception as exc:
        print_error("fetch_video_detail yt-dlp", exc)
    try:
        detail = _fetch_video_detail_pytubefix(video_url, proxy_url)
    except Exception as exc:
        print_error("fetch_video_detail pytubefix", exc)
        raise RuntimeError("Could not fetch video detail") from exc
    if _is_usable_video_detail(detail):
        return detail
    print_error("fetch_video_detail", "pytubefix metadata unusable")
    raise RuntimeError("Could not fetch video detail")


def _pick_download_stream(yt: YouTube):
    stream = (
        yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").asc().first()
    )
    if stream is not None:
        return stream
    return yt.streams.get_lowest_resolution()


def _download_video_pytubefix(
    video_url: str,
    cache_dir: str | Path,
    proxy_url: str | None = None,
    *,
    on_progress: DownloadProgressCallback | None = None,
) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    yt = _build_youtube(video_url, proxy_url)
    video_id = str(yt.video_id or "")
    if not video_id:
        raise RuntimeError("Could not resolve YouTube video id")

    for path in sorted(cache_dir.glob(f"{video_id}.*")):
        if path.is_file() and path.suffix.lower() not in {".part", ".tmp"}:
            if on_progress is not None:
                on_progress(1.0, "Using cached file")
            return path.resolve()

    stream = _pick_download_stream(yt)
    if stream is None:
        raise RuntimeError("No downloadable stream found")

    def _on_chunk_progress(stream_obj, _chunk, bytes_remaining) -> None:
        if on_progress is None:
            return
        total_size = stream_obj.filesize or 0
        if total_size <= 0:
            on_progress(0.0, "Downloading...")
            return
        downloaded = total_size - bytes_remaining
        on_progress(downloaded / total_size, "Downloading...")

    if on_progress is not None:
        on_progress(0.0, "Downloading video...")

    downloaded = stream.download(
        output_path=str(cache_dir),
        filename=video_id,
        skip_existing=True,
        on_progress_callback=_on_chunk_progress,
    )
    if on_progress is not None:
        on_progress(1.0, "Download completed")
    if downloaded:
        return Path(downloaded).resolve()

    for path in sorted(cache_dir.glob(f"{video_id}.*")):
        if path.is_file() and path.suffix.lower() not in {".part", ".tmp"}:
            return path.resolve()
    raise RuntimeError(f"Download finished but file not found for video {video_id}")


def _download_video_pytubefix_with_timeout(
    video_url: str,
    cache_dir: str | Path,
    proxy_url: str | None = None,
    *,
    on_progress: DownloadProgressCallback | None = None,
) -> Path:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            _download_video_pytubefix,
            video_url,
            cache_dir,
            proxy_url,
            on_progress=on_progress,
        )
        try:
            return future.result(timeout=_PYTUBEFIX_DOWNLOAD_TIMEOUT)
        except FuturesTimeoutError as exc:
            raise RuntimeError(f"pytubefix download timed out after {_PYTUBEFIX_DOWNLOAD_TIMEOUT}s") from exc


def download_video_for_practice(
    video_url: str,
    cache_dir: str | Path,
    proxy_url: str | None = None,
    *,
    video_id: str | None = None,
    on_progress: DownloadProgressCallback | None = None,
) -> Path:
    settings = _settings(proxy_url)
    errors: list[str] = []
    try:
        return youtube_ytdlp.download_video_for_practice(
            video_url,
            cache_dir,
            proxy_url=proxy_url,
            settings=settings,
            video_id=video_id,
            on_progress=on_progress,
        )
    except Exception as exc:
        errors.append(f"yt-dlp: {exc}")
    try:
        return _download_video_pytubefix_with_timeout(
            video_url,
            cache_dir,
            proxy_url,
            on_progress=on_progress,
        )
    except Exception as exc:
        errors.append(f"pytubefix: {exc}")
    raise RuntimeError("Video download failed. " + " | ".join(errors))


def resolve_stream_url(page_url: str, proxy_url: str | None = None) -> str:
    settings = _settings(proxy_url)
    try:
        yt = _build_youtube(page_url, proxy_url)
        stream = _pick_download_stream(yt)
        if stream is None:
            raise RuntimeError("No stream URL found")
        url = stream.url
        if not url:
            raise RuntimeError("Stream URL is empty")
        return url
    except Exception as exc:
        print_error("resolve_stream_url pytubefix", exc)
        proc = youtube_ytdlp._run_yt_dlp(
            ["-g", "-f", "worst", page_url.strip()],
            proxy_url=proxy_url,
            settings=settings,
            timeout=60,
        )
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip() or "yt-dlp failed"
            print_error("resolve_stream_url yt-dlp", msg)
            raise RuntimeError(msg)
        line = (proc.stdout or "").strip().splitlines()
        if not line:
            print_error("resolve_stream_url yt-dlp", "returned no URL")
            raise RuntimeError("yt-dlp returned no URL")
        return line[0].strip()

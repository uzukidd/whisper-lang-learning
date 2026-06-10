"""YouTube metadata and downloads via yt-dlp with proxy and browser cookies."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

DownloadProgressCallback = Callable[[float, str], None]

from ..domain.youtube_models import (
    YouTubeVideoDetail,
    YouTubeVideoSummary,
    extract_video_id_from_url,
    normalize_watch_url,
)
from .error_log import print_error
from .proxy_settings import (
    ProxySettings,
    load_proxy_settings,
    sync_yt_dlp_cookies_work_file,
    yt_dlp_network_args,
    yt_dlp_proxy_args,
)
from .yt_dlp_common import (
    iter_yt_dlp_output_lines,
    parse_yt_dlp_download_fraction,
    summarize_yt_dlp_output,
    yt_dlp_command,
)

_DEFAULT_TIMEOUT = 120
_YTDLP_SINGLE_VIDEO_META_ARGS = [
    "--no-playlist",
    "--skip-download",
    "--no-warnings",
    "--ignore-no-formats-error",
]
_YTDLP_PRACTICE_FORMAT = (
    "worst[ext=mp4]/worstvideo[ext=mp4]+worstaudio[ext=m4a]/"
    "worstvideo+worstaudio/worst/best"
)


def _should_retry_without_cookies(error_text: str) -> bool:
    """Retry without cookies only when the cookie file itself failed, not on bot checks."""
    lower = error_text.lower()
    if "sign in to confirm" in lower or "not a bot" in lower:
        return False
    if "use --cookies" in lower or "pass cookies" in lower:
        return False
    cookie_failure_markers = (
        "failed to load cookies",
        "invalid cookie",
        "could not copy",
        "failed to decrypt",
        "no cookies could be",
    )
    return any(marker in lower for marker in cookie_failure_markers)


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
    return yt_dlp_network_args(resolved, proxy_url, use_cookies=use_cookies)


def _run_yt_dlp(
    args: list[str],
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
    *,
    use_cookies: bool = True,
) -> subprocess.CompletedProcess[str]:
    resolved = _settings(proxy_url, settings)
    if use_cookies:
        sync_yt_dlp_cookies_work_file(resolved)
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
        print_error("_run_yt_dlp timeout", exc)
        raise RuntimeError(f"yt-dlp timed out after {timeout}s") from exc
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "yt-dlp failed"
        print_error("_run_yt_dlp", msg)
    combined = (proc.stderr or "") + (proc.stdout or "")
    if (
        proc.returncode != 0
        and use_cookies
        and resolved.uses_yt_dlp_cookies()
        and _should_retry_without_cookies(combined)
    ):
        return _run_yt_dlp(
            args,
            proxy_url=proxy_url,
            settings=settings,
            timeout=timeout,
            use_cookies=False,
        )
    return proc


def _emit_download_progress(
    on_progress: DownloadProgressCallback | None,
    fraction: float,
    message: str,
) -> None:
    if on_progress is not None:
        on_progress(max(0.0, min(1.0, fraction)), message)


def _handle_yt_dlp_output_line(
    line: str,
    on_progress: DownloadProgressCallback | None,
    output_lines: list[str],
    *,
    last_fraction: float,
) -> float:
    stripped = line.strip()
    if not stripped:
        return last_fraction
    output_lines.append(line if line.endswith("\n") else f"{line}\n")
    fraction = parse_yt_dlp_download_fraction(stripped, last_fraction=last_fraction)
    if fraction is not None:
        last_fraction = fraction
        _emit_download_progress(on_progress, last_fraction, stripped)
    elif "100%" in stripped or "Download completed" in stripped or "[Merger] Merging" in stripped:
        _emit_download_progress(on_progress, 1.0, stripped)
        last_fraction = 1.0
    elif on_progress is not None and (stripped.startswith("[youtube]") or stripped.startswith("[info]")):
        _emit_download_progress(on_progress, last_fraction, stripped)
    return last_fraction


def _run_yt_dlp_download(
    args: list[str],
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
    timeout: int = 600,
    *,
    on_progress: DownloadProgressCallback | None = None,
) -> None:
    resolved = _settings(proxy_url, settings)
    last_error = "yt-dlp download failed"
    for use_cookies in (True, False):
        if use_cookies:
            sync_yt_dlp_cookies_work_file(resolved)
        cmd = [
            *yt_dlp_command(),
            *_network_args(proxy_url, settings, use_cookies=use_cookies),
            "--newline",
            "--no-warnings",
            *args,
        ]
        output_lines: list[str] = []
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            last_fraction = 0.0
            if proc.stdout is not None:
                for line in iter_yt_dlp_output_lines(proc.stdout):
                    last_fraction = _handle_yt_dlp_output_line(
                        line,
                        on_progress,
                        output_lines,
                        last_fraction=last_fraction,
                    )
            return_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            print_error("_run_yt_dlp_download timeout", exc)
            raise RuntimeError(f"yt-dlp timed out after {timeout}s") from exc

        if return_code == 0:
            _emit_download_progress(on_progress, 1.0, "Download completed")
            return

        combined = "".join(output_lines)
        last_error = combined.strip() or "yt-dlp download failed"
        if (
            use_cookies
            and resolved.uses_yt_dlp_cookies()
            and _should_retry_without_cookies(combined)
        ):
            continue
        break
    raise RuntimeError(summarize_yt_dlp_output(last_error))


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
        print_error("_parse_yt_dlp_json", "yt-dlp returned invalid JSON")
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
        except RuntimeError as exc:
            print_error("_run_yt_dlp_json parse", exc)
            if proc.returncode == 0:
                raise
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or "yt-dlp failed"
        print_error("_run_yt_dlp_json", msg)
        raise RuntimeError(msg)
    print_error("_run_yt_dlp_json", "yt-dlp returned empty output")
    raise RuntimeError("yt-dlp returned empty output")


def fetch_video_description(
    video_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> str:
    proc = _run_yt_dlp(
        [
            *_YTDLP_SINGLE_VIDEO_META_ARGS,
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
        print_error("fetch_video_description", msg)
        raise RuntimeError(msg)
    return (proc.stdout or "").strip()


def fetch_video_detail(
    video_url: str,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
) -> YouTubeVideoDetail:
    payload = _run_yt_dlp_json(
        ["--dump-single-json", *_YTDLP_SINGLE_VIDEO_META_ARGS, video_url.strip()],
        proxy_url=proxy_url,
        settings=settings,
        timeout=60,
    )
    if not isinstance(payload, dict):
        print_error("fetch_video_detail", "invalid video metadata from yt-dlp")
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


def _resolve_download_video_id(video_url: str, video_id: str | None = None) -> str:
    resolved = (video_id or "").strip() or extract_video_id_from_url(video_url)
    if resolved:
        return resolved
    print_error("_resolve_download_video_id", f"could not resolve id from url={video_url!r}")
    raise RuntimeError("Could not resolve YouTube video id for download")


def download_video_for_practice(
    video_url: str,
    cache_dir: str | Path,
    proxy_url: str | None = None,
    settings: ProxySettings | None = None,
    *,
    video_id: str | None = None,
    on_progress: DownloadProgressCallback | None = None,
) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    _emit_download_progress(on_progress, 0.0, "Checking cache...")
    resolved_id = _resolve_download_video_id(video_url, video_id)
    watch_url = normalize_watch_url(resolved_id, video_url)

    for path in sorted(cache_dir.glob(f"{resolved_id}.*")):
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}:
            _emit_download_progress(on_progress, 1.0, "Using cached file")
            return path.resolve()

    output_template = str(cache_dir / f"{resolved_id}.%(ext)s")
    _emit_download_progress(on_progress, 0.0, "Downloading video...")
    _run_yt_dlp_download(
        [
            "-f",
            _YTDLP_PRACTICE_FORMAT,
            "--no-playlist",
            "-o",
            output_template,
            watch_url,
        ],
        proxy_url=proxy_url,
        settings=settings,
        timeout=600,
        on_progress=on_progress,
    )

    for path in sorted(cache_dir.glob(f"{resolved_id}.*")):
        if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}:
            return path.resolve()
    print_error("download_video_for_practice", f"file not found for video {resolved_id}")
    raise RuntimeError(f"Download finished but file not found for video {resolved_id}")

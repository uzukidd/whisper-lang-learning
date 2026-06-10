"""Shared yt-dlp executable helpers."""

from __future__ import annotations

import re
import shutil
import sys
from collections.abc import Iterator

_DOWNLOAD_PERCENT_RE = re.compile(r"\[download\]\s+([\d.]+)%")
_DOWNLOAD_FRAG_RE = re.compile(r"\(frag\s+(\d+)/(\d+)\)")


def yt_dlp_command() -> list[str]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        print(f"[ERROR] yt_dlp_command: yt-dlp not found: {exc}", flush=True)
        raise RuntimeError("yt-dlp not found; install: pip install yt-dlp") from exc
    return [sys.executable, "-m", "yt_dlp"]


def find_yt_dlp_exe() -> str:
    return yt_dlp_command()[0]


def yt_dlp_youtube_args() -> list[str]:
    return ["--js-runtimes", "node", "--remote-components", "ejs:github"]


def iter_yt_dlp_output_lines(stream) -> Iterator[str]:
    pending = ""
    for chunk in iter(lambda: stream.read(4096), ""):
        pending += chunk
        parts = re.split(r"[\r\n]+", pending)
        pending = parts.pop() if parts else pending
        for part in parts:
            if part.strip():
                yield part
    if pending.strip():
        yield pending


def parse_yt_dlp_download_fraction(line: str, *, last_fraction: float = 0.0) -> float | None:
    """Parse yt-dlp download progress.

    Example:
        [download]  22.6% of ~   8.90MiB at  111.15KiB/s ETA 01:05 (frag 23/107)
    Prefer fragment index for HLS downloads because the percent estimate can move backwards.
    """
    stripped = line.strip()
    if "[download]" not in stripped:
        return None
    frag_match = _DOWNLOAD_FRAG_RE.search(stripped)
    if frag_match:
        total = int(frag_match.group(2))
        if total > 0:
            current = int(frag_match.group(1))
            return max(0.0, min(1.0, current / total))
    percent_match = _DOWNLOAD_PERCENT_RE.search(stripped)
    if percent_match:
        fraction = float(percent_match.group(1)) / 100.0
        fraction = max(0.0, min(1.0, fraction))
        return max(last_fraction, fraction)
    return None


def summarize_yt_dlp_output(text: str) -> str:
    """Return a short yt-dlp failure message without full download progress spam."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "yt-dlp failed"
    for line in reversed(lines):
        if line.startswith("ERROR:"):
            return line
    for line in reversed(lines):
        if not line.startswith("[download]"):
            return line
    return lines[-1]

"""Shared yt-dlp executable helpers."""

from __future__ import annotations

import shutil
import sys


def yt_dlp_command() -> list[str]:
    exe = shutil.which("yt-dlp") or shutil.which("youtube-dl")
    if exe:
        return [exe]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("yt-dlp not found; install: pip install yt-dlp") from exc
    return [sys.executable, "-m", "yt_dlp"]


def find_yt_dlp_exe() -> str:
    return yt_dlp_command()[0]

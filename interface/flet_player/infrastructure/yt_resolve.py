"""Resolve a YouTube page URL to a direct media URL via yt-dlp."""

from __future__ import annotations

import asyncio
import shutil


async def resolve_youtube_stream_url(page_url: str, format_selector: str = "worst") -> str:
    exe = shutil.which("yt-dlp") or shutil.which("youtube-dl")
    if not exe:
        raise RuntimeError("yt-dlp not found on PATH; install: pip install yt-dlp")

    proc = await asyncio.create_subprocess_exec(
        exe,
        "-g",
        "-f",
        format_selector,
        page_url.strip(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        msg = (err or b"").decode("utf-8", errors="replace").strip() or "yt-dlp failed"
        raise RuntimeError(msg)
    line = (out or b"").decode("utf-8", errors="replace").strip().splitlines()
    if not line:
        raise RuntimeError("yt-dlp returned no URL")
    return line[0].strip()

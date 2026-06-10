"""CLI template: download a YouTube video with a terminal progress bar."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from interface.flet_player.infrastructure.proxy_settings import (  # noqa: E402
    load_proxy_settings,
    sync_yt_dlp_cookies_work_file,
    yt_dlp_network_args,
)
from interface.flet_player.infrastructure.yt_dlp_common import (  # noqa: E402
    iter_yt_dlp_output_lines,
    parse_yt_dlp_download_fraction,
    yt_dlp_command,
)

_DEFAULT_FORMAT = (
    "worst[ext=mp4]/worstvideo[ext=mp4]+worstaudio[ext=m4a]/"
    "worstvideo+worstaudio/worst/best"
)
_DEFAULT_OUTPUT_DIR = ROOT / "assets" / "cache" / "youtube"


def _render_progress(fraction: float, message: str, *, bar_width: int = 30) -> None:
    fraction = max(0.0, min(1.0, fraction))
    filled = int(bar_width * fraction)
    bar = "#" * filled + "-" * (bar_width - filled)
    line = f"\r[{bar}] {fraction * 100:5.1f}% {message[:100]}"
    sys.stdout.write(line)
    sys.stdout.flush()
    if fraction >= 1.0:
        sys.stdout.write("\n")
        sys.stdout.flush()


def download_video(url: str, output_template: str) -> int:
    settings = load_proxy_settings()
    sync_yt_dlp_cookies_work_file(settings)
    cmd = [
        *yt_dlp_command(),
        *yt_dlp_network_args(settings),
        "--newline",
        "-f",
        _DEFAULT_FORMAT,
        "--no-playlist",
        "-o",
        output_template,
        url,
    ]
    print("command:", " ".join(cmd), flush=True)
    _render_progress(0.0, "Starting download...")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    last_fraction = 0.0
    if proc.stdout is not None:
        for line in iter_yt_dlp_output_lines(proc.stdout):
            stripped = line.strip()
            fraction = parse_yt_dlp_download_fraction(stripped, last_fraction=last_fraction)
            if fraction is not None:
                last_fraction = fraction
                _render_progress(last_fraction, stripped)
            elif stripped.startswith("[youtube]") or stripped.startswith("[info]"):
                _render_progress(last_fraction, stripped)
            elif "100%" in stripped or "Merging" in stripped or "Download completed" in stripped:
                last_fraction = 1.0
                _render_progress(1.0, stripped)
    return proc.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a video with yt-dlp and a progress bar.")
    parser.add_argument("url", help="Video URL")
    parser.add_argument(
        "-o",
        "--output",
        default=str(_DEFAULT_OUTPUT_DIR / "%(id)s.%(ext)s"),
        help="Output template, default: assets/cache/youtube/%(id)s.%(ext)s",
    )
    args = parser.parse_args()
    if "%(" in args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    return download_video(args.url, args.output)


if __name__ == "__main__":
    raise SystemExit(main())

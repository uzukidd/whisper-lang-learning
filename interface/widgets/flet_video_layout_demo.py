#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry: Flet video player (QT6_VideoPlayer port with decoupled logic).

  conda activate env_whisper_listening
  pip install flet flet-video yt-dlp
  python interface/widgets/flet_video_layout_demo.py [optional_initial_uri_or_path]

Env:
  WHISPER_MODEL — whisper model name (default: base)
  WHISPER_DEVICE — cuda or cpu (optional, auto if unset)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root on sys.path for `interface.*` imports when run as a script.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import flet as ft

from interface.flet_player.ui.flet_video_player_page import build_video_player_page


def main(page: ft.Page) -> None:
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    if initial and not initial.startswith(("http://", "https://")):
        p = Path(initial)
        if p.is_file():
            initial = p.resolve().as_uri()
    build_video_player_page(page, initial_video_uri=initial)


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP)

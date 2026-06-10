#!/usr/bin/env python3
"""Root entrypoint for the Flet video player."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Sequence


def _resolve_initial_arg(argv: Sequence[str]) -> str | None:
    initial = argv[1] if len(argv) > 1 else None
    if initial and not initial.startswith(("http://", "https://")):
        path = Path(initial)
        if path.is_file():
            return path.resolve().as_uri()
    return initial


def run(
    argv: Sequence[str] | None = None,
    app_runner: Callable | None = None,
    flet_module=None,
    page_builder: Callable | None = None,
) -> None:
    argv = list(argv or sys.argv)
    if flet_module is None:
        import flet as ft

        flet_module = ft
    if page_builder is None:
        from interface.flet_player.ui.flet_video_player_page import build_video_player_page

        page_builder = build_video_player_page

    initial = _resolve_initial_arg(argv)

    def main(page) -> None:
        from interface.flet_player.ui.app_lifecycle import install_force_exit_on_window_close

        install_force_exit_on_window_close(page)
        page_builder(page, initial_video_uri=initial)

    runner = app_runner or flet_module.run
    runner(main, view=flet_module.AppView.FLET_APP)


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""Root entrypoint for the YouTube-style browse UI."""

from __future__ import annotations

import flet as ft

from interface.flet_player.ui.app_lifecycle import install_force_exit_on_window_close
from interface.flet_player.ui.youtube_browse_page import build_youtube_browse_page


def main(page: ft.Page) -> None:
    install_force_exit_on_window_close(page)
    build_youtube_browse_page(page)


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP)

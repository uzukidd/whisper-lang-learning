"""Flet app lifecycle helpers."""

from __future__ import annotations

import os

import flet as ft


def install_force_exit_on_window_close(page: ft.Page) -> None:
    """Terminate the process immediately when the desktop window closes."""

    def _on_window_event(event: ft.WindowEvent) -> None:
        if event.data == "close":
            os._exit(0)

    page.window.on_event = _on_window_event

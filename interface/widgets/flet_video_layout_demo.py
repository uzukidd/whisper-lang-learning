#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flet layout mirroring QT6_VideoPlayer.py (video + caption input + caption + control row + bottom inset).

Run in conda env env_whisper_listening (listed as env_whisper_listening under Anaconda; activate before pip/run):
  conda activate env_whisper_listening
  pip install flet flet-video
  python interface/widgets/flet_video_layout_demo.py
"""

from __future__ import annotations

import asyncio

import flet as ft
import flet_video as ftv

# Sample clip from Flet video docs (replace with local file via ftv.VideoMedia("file:///...") if needed).
_SAMPLE_MP4 = (
    "https://user-images.githubusercontent.com/28951144/"
    "229373720-14d69157-1a56-4a78-a2f4-d7a134d7c3e9.mp4"
)


def _format_hms_from_ms(total_ms: int) -> str:
    total_ms = max(0, int(total_ms))
    total_s = total_ms // 1000
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _lineedit_style() -> dict:
    # Approximate QT stylesheet(black bg, grey text, bold small).
    return {
        "bgcolor": ft.Colors.BLACK,
        "color": "#585858",
        "border_color": ft.Colors.TRANSPARENT,
        "text_size": 11,
        "read_only": True,
    }


def main(page: ft.Page) -> None:
    page.title = "Flet layout (QT6_VideoPlayer-like)"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    lbl = ft.TextField(value="00:00:00", width=70, **_lineedit_style())
    elbl = ft.TextField(value="00:00:00", width=70, **_lineedit_style())
    position_slider = ft.Slider(
        min=0,
        max=1,
        value=0,
        expand=True,
        active_color="#729fcf",
        inactive_color="#444444",
    )

    caption_input = ft.TextField(
        hint_text="caption input",
        bgcolor=ft.Colors.BLACK,
        color=ft.Colors.WHITE70,
        border_color=ft.Colors.TRANSPARENT,
        text_size=15,
    )
    caption_display = ft.TextField(
        value="",
        read_only=True,
        bgcolor=ft.Colors.BLACK,
        color=ft.Colors.WHITE70,
        border_color=ft.Colors.TRANSPARENT,
        text_size=15,
    )

    play_btn = ft.IconButton(
        icon=ft.Icons.PLAY_ARROW,
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLACK,
        tooltip="Play / Pause",
    )

    video = ftv.Video(
        expand=True,
        playlist=[ftv.VideoMedia(_SAMPLE_MP4)],
        playlist_mode=ftv.PlaylistMode.LOOP,
        fill_color=ft.Colors.BLACK,
        aspect_ratio=16 / 9,
        volume=80.0,
        autoplay=False,
        show_controls=False,
    )

    tick_armed = False

    async def _sync_slider_from_video() -> None:
        while True:
            try:
                pos = await video.get_current_position()
                ms = pos.in_milliseconds
                position_slider.value = float(ms)
                lbl.value = _format_hms_from_ms(ms)
                page.update()
            except Exception:
                pass
            await asyncio.sleep(0.25)

    def _on_video_load(_: ft.ControlEvent) -> None:
        nonlocal tick_armed

        async def _setup() -> None:
            try:
                dur = await video.get_duration()
                dms = max(dur.in_milliseconds, 1)
                position_slider.max = float(dms)
                elbl.value = _format_hms_from_ms(dms)
            except Exception:
                position_slider.max = 1.0
            page.update()

        page.run_task(_setup)
        if not tick_armed:
            tick_armed = True
            page.run_task(_sync_slider_from_video)

    video.on_load = _on_video_load

    async def _toggle_play(_: ft.ControlEvent) -> None:
        await video.play_or_pause()
        playing = await video.is_playing()
        play_btn.icon = ft.Icons.PAUSE if playing else ft.Icons.PLAY_ARROW
        page.update()

    play_btn.on_click = _toggle_play

    async def _on_slider_commit(e: ft.ControlEvent) -> None:
        ms = int(float(e.control.value))
        await video.seek(ft.Duration.from_unit(milliseconds=ms))

    position_slider.on_change_end = _on_slider_commit

    control_row = ft.Row(
        [play_btn, lbl, position_slider, elbl],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    # STRETCH: default Column uses horizontal_alignment=START so children keep intrinsic width;
    # with STRETCH, children get the full cross-axis width (like Qt expanding in a QVBoxLayout).
    input_col = ft.Column(
        [caption_input, caption_display],
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # Match Qt: layout.setContentsMargins(0, 0, 0, 250) — Column has no padding in this Flet version.
    root = ft.Container(
        expand=True,
        padding=ft.padding.only(bottom=250),
        content=ft.Column(
            [
                video,
                input_col,
                control_row,
            ],
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )

    page.add(root)


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP)

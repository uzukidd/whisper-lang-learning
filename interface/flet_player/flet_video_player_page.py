"""Flet UI for QT6_VideoPlayer-equivalent (controls + menus + keyboard)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import flet as ft
import flet_video as ftv

from .caption_session import CaptionSession
from .flet_video_backend import FletVideoBackend
from .video_player_presenter import PlayerViewHooks, VideoPlayerPresenter

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_VIDEO = _REPO_ROOT / "assets" / "Don't click this! Unless you want to cry all over again.mp4"

_VIDEO_FILETYPES = [
    (
        "Media",
        "*.webm *.mp4 *.ts *.avi *.mpeg *.mpg *.mkv *.m4v *.3gp "
        "*.mp3 *.m4a *.wav *.ogg *.flac *.m3u *.m3u8",
    ),
    ("All files", "*.*"),
]
_CAPTION_FILETYPES = [("Caption", "*.caption"), ("All files", "*.*")]


def _native_open_filename(title: str, filetypes: list[tuple[str, str]]) -> Optional[str]:
    """Desktop file dialog without Flet FilePicker (avoids unknown-control on some clients)."""
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return path if path else None


def _native_clipboard_get() -> Optional[str]:
    """Read system clipboard text without ft.Clipboard (unknown control on some clients)."""
    from tkinter import TclError, Tk

    root = Tk()
    root.withdraw()
    try:
        root.update()
        raw = root.clipboard_get()
    except TclError:
        return None
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    if raw is None:
        return None
    return str(raw).strip() or None


def _snack(page: ft.Page, message: str, bgcolor: str) -> None:
    page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=bgcolor)
    page.snack_bar.open = True
    page.update()


def build_video_player_page(
    page: ft.Page,
    initial_video_uri: Optional[str] = None,
) -> None:
    page.title = "Flet Video Player"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    time_w = 108
    line_style = {
        "bgcolor": ft.Colors.BLACK,
        "color": "#585858",
        "border_color": ft.Colors.TRANSPARENT,
        "text_size": 11,
        "read_only": True,
        "content_padding": ft.padding.symmetric(horizontal=6, vertical=8),
    }

    lbl = ft.TextField(value="00:00:00", width=time_w, text_align=ft.TextAlign.CENTER, **line_style)
    elbl = ft.TextField(value="00:00:00", width=time_w, text_align=ft.TextAlign.CENTER, **line_style)
    position_slider = ft.Slider(
        min=0.0,
        max=1.0,
        value=0.0,
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

    if initial_video_uri:
        start_uri = initial_video_uri
    elif _DEFAULT_VIDEO.is_file():
        start_uri = _DEFAULT_VIDEO.resolve().as_uri()
    else:
        start_uri = (
            "https://user-images.githubusercontent.com/28951144/"
            "229373720-14d69157-1a56-4a78-a2f4-d7a134d7c3e9.mp4"
        )

    video = ftv.Video(
        expand=True,
        playlist=[ftv.VideoMedia(start_uri)],
        playlist_mode=ftv.PlaylistMode.LOOP,
        fill_color=ft.Colors.BLACK,
        aspect_ratio=16 / 9,
        volume=80.0,
        autoplay=False,
        show_controls=False,
    )

    control_row = ft.Row(
        [play_btn, lbl, position_slider, elbl],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
        visible=True,
    )

    input_col = ft.Column(
        [caption_input, caption_display],
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )

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

    backend = FletVideoBackend(page, video)
    session = CaptionSession()

    async def confirm_finish_practice() -> bool:
        done = asyncio.Event()
        holder: dict[str, bool] = {"ok": False}
        dlg_holder: dict[str, ft.AlertDialog] = {}

        def close(ok: bool) -> None:
            holder["ok"] = ok
            d = dlg_holder.get("d")
            if d is not None:
                d.open = False
            done.set()
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Finish practice"),
            content=ft.Text("Are you sure to finish the practice?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: close(False)),
                ft.TextButton("OK", on_click=lambda _: close(True)),
            ],
        )
        dlg_holder["d"] = dlg
        page.overlay.append(dlg)
        dlg.open = True
        page.update()
        await done.wait()
        try:
            page.overlay.remove(dlg)
        except ValueError:
            pass
        page.update()
        return holder["ok"]

    def on_language_font(lang: Optional[str]) -> None:
        if lang == "ja":
            caption_input.text_size = 15
            caption_display.text_size = 15
        elif lang == "en":
            caption_input.text_size = 16
            caption_display.text_size = 16

    async def request_exit_app_async() -> None:
        await page.window.close()

    def set_times(a: str, b: str) -> None:
        lbl.value = a
        elbl.value = b

    def set_slider_ratio(r: float) -> None:
        position_slider.value = r

    def set_caption_display(t: str) -> None:
        caption_display.value = t

    def set_caption_input(t: str) -> None:
        caption_input.value = t

    def set_caption_input_enabled(en: bool) -> None:
        caption_input.disabled = not en

    def set_playing(playing: bool) -> None:
        play_btn.icon = ft.Icons.PAUSE if playing else ft.Icons.PLAY_ARROW

    hooks = PlayerViewHooks(
        set_times=set_times,
        set_slider_ratio=set_slider_ratio,
        set_caption_display=set_caption_display,
        set_caption_input=set_caption_input,
        set_caption_input_enabled=set_caption_input_enabled,
        set_playing=set_playing,
        show_error=lambda m: _snack(page, m, ft.Colors.RED_700),
        show_info=lambda m: _snack(page, m, ft.Colors.BLUE_GREY_700),
        confirm_finish_practice=confirm_finish_practice,
        on_language_font=on_language_font,
        request_exit_app=lambda: page.run_task(request_exit_app_async),
    )

    presenter = VideoPlayerPresenter(backend, session, hooks)
    presenter.bind_tick()
    backend.arm_load_handler()

    caption_focused = {"v": False}

    def _cap_focus_in(_: ft.ControlEvent) -> None:
        caption_focused["v"] = True

    def _cap_focus_out(_: ft.ControlEvent) -> None:
        caption_focused["v"] = False

    caption_input.on_focus = _cap_focus_in
    caption_input.on_blur = _cap_focus_out

    async def _toggle_play(_: ft.ControlEvent) -> None:
        await presenter.toggle_play()
        page.update()

    play_btn.on_click = _toggle_play

    def _on_slider_change_start(_: ft.ControlEvent) -> None:
        backend.set_scrubbing(True)

    def _on_slider_commit(e: ft.ControlEvent) -> None:
        ratio = float(e.control.value)

        async def _seek() -> None:
            try:
                await presenter.seek_slider_ratio(ratio)
            finally:
                backend.set_scrubbing(False)

        page.run_task(_seek)

    position_slider.on_change_start = _on_slider_change_start
    position_slider.on_change_end = _on_slider_commit

    caption_input.on_change = lambda e: presenter.on_caption_input_changed(e.control.value or "")

    async def _caption_submit(_: ft.ControlEvent) -> None:
        await presenter.next_caption(False, caption_input.value or "")

    caption_input.on_submit = _caption_submit

    def toggle_controls_visible(_: Optional[ft.ControlEvent] = None) -> None:
        control_row.visible = not control_row.visible
        page.update()

    def set_aspect169(_: Optional[ft.ControlEvent] = None) -> None:
        video.aspect_ratio = 16 / 9
        page.update()

    def set_aspect43(_: Optional[ft.ControlEvent] = None) -> None:
        video.aspect_ratio = 4 / 3
        page.update()

    async def toggle_fullscreen(_: Optional[ft.ControlEvent] = None) -> None:
        page.window.full_screen = not page.window.full_screen
        page.update()

    myinfo = (
        "Flet player (QT6 port)\n\n"
        "UP/DOWN: volume\n"
        "LEFT/RIGHT: seek ±1 min (Shift: ±10 min)\n"
        "S: toggle control bar\n"
        "F: fullscreen\n"
        "Return: replay caption (when caption input focused)\n"
        "Up/Down: prev/next segment (when caption input focused)\n"
    )

    def show_info_dialog(_: Optional[ft.ControlEvent] = None) -> None:
        dlg = ft.AlertDialog(title=ft.Text("Info"), content=ft.Text(myinfo))
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    async def _paste_url(_: Optional[ft.ControlEvent] = None) -> None:
        try:
            u = await asyncio.to_thread(_native_clipboard_get)
        except ImportError:
            hooks.show_error("tkinter is not available for clipboard read.")
            return
        if not u:
            hooks.show_error("Clipboard is empty or non-text.")
            return
        try:
            await presenter.play_clipboard_url(u)
        except Exception as ex:
            hooks.show_error(str(ex))

    async def _paste_yt(_: Optional[ft.ControlEvent] = None) -> None:
        try:
            u = await asyncio.to_thread(_native_clipboard_get)
        except ImportError:
            hooks.show_error("tkinter is not available for clipboard read.")
            return
        if not u:
            hooks.show_error("Clipboard is empty or non-text.")
            return
        try:
            await presenter.play_youtube_clipboard(u)
        except Exception as ex:
            hooks.show_error(str(ex))

    async def _pick_open_video() -> None:
        try:
            p = await asyncio.to_thread(_native_open_filename, "Open Movie", _VIDEO_FILETYPES)
        except ImportError:
            _snack(page, "tkinter is not available for file browse.", ft.Colors.RED_700)
            return
        if p:
            await presenter.load_local_path(p, True)

    async def _pick_open_caption() -> None:
        try:
            p = await asyncio.to_thread(_native_open_filename, "Open Caption", _CAPTION_FILETYPES)
        except ImportError:
            _snack(page, "tkinter is not available for file browse.", ft.Colors.RED_700)
            return
        if p:
            presenter.load_caption_path(p)
            page.update()

    menu = ft.PopupMenuButton(
        icon=ft.Icons.MENU,
        items=[
            ft.PopupMenuItem(
                content="Open video file…",
                on_click=lambda _: page.run_task(_pick_open_video),
            ),
            ft.PopupMenuItem(
                content="Open caption…",
                on_click=lambda _: page.run_task(_pick_open_caption),
            ),
            ft.PopupMenuItem(
                content="Transcribe (Whisper)",
                on_click=lambda _: page.run_task(presenter.run_whisper_transcript),
            ),
            ft.PopupMenuItem(
                content="Practice mode",
                on_click=lambda _: (presenter.toggle_practice_mode(), page.update()),
            ),
            ft.PopupMenuItem(
                content="Show caption",
                on_click=lambda _: (presenter.toggle_show_caption(), page.update()),
            ),
            ft.PopupMenuItem(content="Play URL from clipboard", on_click=lambda _: page.run_task(_paste_url)),
            ft.PopupMenuItem(
                content="YouTube URL from clipboard (yt-dlp)",
                on_click=lambda _: page.run_task(_paste_yt),
            ),
            ft.PopupMenuItem(content="Toggle control bar (S)", on_click=lambda _: toggle_controls_visible()),
            ft.PopupMenuItem(content="Fullscreen (F)", on_click=lambda _: page.run_task(toggle_fullscreen)),
            ft.PopupMenuItem(content="16 : 9", on_click=lambda _: set_aspect169()),
            ft.PopupMenuItem(content="4 : 3", on_click=lambda _: set_aspect43()),
            ft.PopupMenuItem(content="Info (I)", on_click=lambda _: show_info_dialog()),
            ft.PopupMenuItem(content="Exit", on_click=lambda _: page.run_task(request_exit_app_async)),
        ],
    )

    top_bar = ft.Row([menu], alignment=ft.MainAxisAlignment.END)

    async def on_key(e: ft.KeyboardEvent) -> None:
        if e.alt or e.ctrl or e.meta:
            return
        k = e.key
        if k in ("S", "s"):
            toggle_controls_visible()
        elif k in ("F", "f"):
            await toggle_fullscreen()
        elif k in ("I", "i"):
            show_info_dialog()
        elif k in ("Arrow Up", "Up"):
            if caption_focused["v"]:
                await presenter.last_caption()
            else:
                await presenter.volume_delta(5.0)
            page.update()
        elif k in ("Arrow Down", "Down"):
            if caption_focused["v"]:
                await presenter.next_caption(True, caption_input.value or "")
            else:
                await presenter.volume_delta(-5.0)
            page.update()
        elif k in ("Arrow Left", "Left"):
            ms = 600000 if e.shift else 60000
            await presenter.seek_delta_ms(-ms)
        elif k in ("Arrow Right", "Right"):
            ms = 600000 if e.shift else 60000
            await presenter.seek_delta_ms(ms)
        elif k in ("Enter", "Numpad Enter") and caption_focused["v"]:
            await presenter.replay_caption()
            page.update()

    page.on_keyboard_event = on_key

    def on_video_error(ev: ft.ControlEvent) -> None:
        hooks.show_error(str(ev.data) if ev.data else "Video error")

    video.on_error = on_video_error

    page.add(ft.Column([top_bar, root], expand=True, spacing=0))

"""Flet UI for the decoupled video player."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import flet as ft
import flet_video as ftv

from ..application.asr import AsrService
from ..application.practice_service import PracticeService
from ..application.presenter import PlayerViewHooks, VideoPlayerPresenter
from ..domain.caption_session import CaptionSession
from ..domain.scoring import NormalizedExactSentenceScorer
from ..infrastructure.caption_repository import CaptionRepository
from ..infrastructure.flet_video_backend import FletVideoBackend
from ..infrastructure.whisper_provider import WhisperAsrProvider

_VIDEO_FILETYPES = [
    ("Media", "*.webm *.mp4 *.ts *.avi *.mpeg *.mpg *.mkv *.m4v *.3gp *.mp3 *.m4a *.wav *.ogg *.flac *.m3u *.m3u8"),
    ("All files", "*.*"),
]
_CAPTION_FILETYPES = [("Caption", "*.caption"), ("All files", "*.*")]
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _default_video_path() -> Optional[Path]:
    assets = _REPO_ROOT / "assets"
    for name in [
        "Don't click this! Unless you want to cry all over again.mp4",
        "Dont click this! Unless you want to cry all over again.mp4",
    ]:
        candidate = assets / name
        if candidate.is_file():
            return candidate
    candidates = sorted(assets.glob("*.mp4"))
    return candidates[0] if candidates else None


def _native_open_filename(title: str, filetypes: list[tuple[str, str]]) -> Optional[str]:
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
    return str(raw).strip() if raw else None


def _snack(page: ft.Page, message: str, bgcolor: str) -> None:
    page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=bgcolor)
    page.snack_bar.open = True
    page.update()


def build_video_player_page(page: ft.Page, initial_video_uri: Optional[str] = None) -> None:
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
    position_slider = ft.Slider(min=0.0, max=1.0, value=0.0, expand=True, active_color="#729fcf", inactive_color="#444444")
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
    sentence_feedback = ft.Text(value="", visible=False)
    current_video_text = ft.Text("Video: None", size=12, color=ft.Colors.WHITE70)
    current_caption_text = ft.Text("Caption: None", size=12, color=ft.Colors.WHITE70)
    current_media_info = ft.Column(
        [current_video_text, current_caption_text],
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.START,
    )
    practice_mode_text = ft.Text("Practice: OFF", size=12, color=ft.Colors.WHITE70)
    play_btn = ft.IconButton(
        icon=ft.Icons.PLAY_ARROW,
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLACK,
        tooltip="Play / Pause",
    )

    default_video = _default_video_path()
    video = ftv.Video(
        expand=True,
        playlist=[
            ftv.VideoMedia(
                initial_video_uri
                if initial_video_uri
                else (
                    str(default_video.resolve())
                    if default_video is not None
                    else "https://user-images.githubusercontent.com/28951144/229373720-14d69157-1a56-4a78-a2f4-d7a134d7c3e9.mp4"
                )
            )
        ],
        playlist_mode=ftv.PlaylistMode.LOOP,
        fill_color=ft.Colors.BLACK,
        aspect_ratio=16 / 9,
        volume=80.0,
        autoplay=False,
        show_controls=False,
    )

    control_row = ft.Row([play_btn, lbl, position_slider, elbl], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, visible=True)
    input_col = ft.Column([caption_input, caption_display, sentence_feedback], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    transcribe_loading = ft.AlertDialog(
        modal=True,
        title=ft.Text("Transcribing"),
        content=ft.Row([ft.ProgressRing(), ft.Text("Loading, please wait...")], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )
    root = ft.Container(
        expand=True,
        padding=0,
        content=ft.Column([video, input_col, control_row], expand=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
    )

    backend = FletVideoBackend(page, video)
    session = CaptionSession()

    async def confirm_finish_practice() -> bool:
        done = asyncio.Event()
        holder: dict[str, bool] = {"ok": False}
        dlg_holder: dict[str, ft.AlertDialog] = {}

        def close(ok: bool) -> None:
            holder["ok"] = ok
            dialog = dlg_holder.get("d")
            if dialog is not None:
                dialog.open = False
            done.set()
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Finish practice"),
            content=ft.Text("Are you sure to finish the practice?"),
            actions=[ft.TextButton("Cancel", on_click=lambda _: close(False)), ft.TextButton("OK", on_click=lambda _: close(True))],
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

    def set_slider_ratio(ratio: float) -> None:
        position_slider.value = ratio

    def set_caption_display(text: str) -> None:
        caption_display.value = text

    def set_current_video_name(name: str) -> None:
        current_video_text.value = f"Video: {name}"

    def set_current_caption_name(name: str) -> None:
        current_caption_text.value = f"Caption: {name}"

    def set_caption_input(text: str) -> None:
        caption_input.value = text

    def focus_caption_input() -> None:
        page.run_task(caption_input.focus)

    def set_sentence_feedback(words: list[tuple[str, bool]], visible: bool) -> None:
        if not visible or not words:
            sentence_feedback.visible = False
            sentence_feedback.value = ""
            sentence_feedback.spans = None
            return
        spans: list[ft.TextSpan] = []
        for idx, (word, ok) in enumerate(words):
            if idx > 0:
                spans.append(ft.TextSpan(text=" "))
            spans.append(ft.TextSpan(text=word, style=ft.TextStyle(color=ft.Colors.GREEN_400 if ok else ft.Colors.RED_400, weight=ft.FontWeight.W_600)))
        sentence_feedback.value = ""
        sentence_feedback.spans = spans
        sentence_feedback.visible = True

    def set_caption_input_enabled(enabled: bool) -> None:
        caption_input.disabled = not enabled

    def set_caption_input_read_only(read_only: bool) -> None:
        caption_input.read_only = read_only

    def set_slider_enabled(enabled: bool) -> None:
        position_slider.disabled = not enabled

    def set_practice_mode_text(text: str) -> None:
        practice_mode_text.value = text

    def set_playing(playing: bool) -> None:
        play_btn.icon = ft.Icons.PAUSE if playing else ft.Icons.PLAY_ARROW

    def set_transcribe_busy(busy: bool, message: str) -> None:
        if message:
            transcribe_loading.title = ft.Text(message)
        if transcribe_loading not in page.overlay:
            page.overlay.append(transcribe_loading)
        transcribe_loading.open = busy
        page.update()

    hooks = PlayerViewHooks(
        set_times=set_times,
        set_slider_ratio=set_slider_ratio,
        set_current_video_name=set_current_video_name,
        set_current_caption_name=set_current_caption_name,
        set_caption_display=set_caption_display,
        set_caption_input=set_caption_input,
        focus_caption_input=focus_caption_input,
        set_sentence_feedback=set_sentence_feedback,
        set_caption_input_enabled=set_caption_input_enabled,
        set_caption_input_read_only=set_caption_input_read_only,
        set_slider_enabled=set_slider_enabled,
        set_practice_mode_text=set_practice_mode_text,
        set_playing=set_playing,
        show_error=lambda message: _snack(page, message, ft.Colors.RED_700),
        show_info=lambda message: _snack(page, message, ft.Colors.BLUE_GREY_700),
        set_transcribe_busy=set_transcribe_busy,
        confirm_finish_practice=confirm_finish_practice,
        on_language_font=on_language_font,
        request_exit_app=lambda: page.run_task(request_exit_app_async),
    )

    scorer = NormalizedExactSentenceScorer()
    presenter = VideoPlayerPresenter(
        backend,
        session,
        hooks,
        scorer=scorer,
        caption_repository=CaptionRepository(),
        asr_service=AsrService(WhisperAsrProvider()),
        practice_service=PracticeService(scorer),
    )
    presenter.bind_tick()
    backend.arm_load_handler()

    caption_focused = {"v": False}
    caption_input.on_focus = lambda _: caption_focused.__setitem__("v", True)
    caption_input.on_blur = lambda _: caption_focused.__setitem__("v", False)

    async def _toggle_play(_: ft.ControlEvent) -> None:
        await presenter.toggle_play()
        page.update()

    play_btn.on_click = _toggle_play

    def _on_slider_change_start(_: ft.ControlEvent) -> None:
        if presenter.session.practice_mode:
            return
        backend.set_scrubbing(True)

    def _on_slider_commit(e: ft.ControlEvent) -> None:
        if presenter.session.practice_mode:
            return
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
        if presenter.is_submit_locked():
            return
        await presenter.submit_caption(caption_input.value or "")
        page.update()

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
        "Whisper© Learning\n\n"
        "UP/DOWN: switch lines in practice mode\n"
        "LEFT/RIGHT: seek ±1 min (Shift: ±10 min)\n"
        "S: toggle control bar\n"
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
            url = await asyncio.to_thread(_native_clipboard_get)
        except ImportError:
            hooks.show_error("tkinter is not available for clipboard read.")
            return
        if not url:
            hooks.show_error("Clipboard is empty or non-text.")
            return
        try:
            await presenter.play_clipboard_url(url)
        except Exception as exc:
            hooks.show_error(str(exc))

    async def _paste_yt(_: Optional[ft.ControlEvent] = None) -> None:
        try:
            url = await asyncio.to_thread(_native_clipboard_get)
        except ImportError:
            hooks.show_error("tkinter is not available for clipboard read.")
            return
        if not url:
            hooks.show_error("Clipboard is empty or non-text.")
            return
        try:
            await presenter.play_youtube_clipboard(url)
        except Exception as exc:
            hooks.show_error(str(exc))

    async def _pick_open_video() -> None:
        try:
            path = await asyncio.to_thread(_native_open_filename, "Open Movie", _VIDEO_FILETYPES)
        except ImportError:
            _snack(page, "tkinter is not available for file browse.", ft.Colors.RED_700)
            return
        if path:
            try:
                await presenter.load_local_path(path, True)
            except Exception as exc:
                hooks.show_error(str(exc))

    async def _pick_open_caption() -> None:
        try:
            path = await asyncio.to_thread(_native_open_filename, "Open Caption", _CAPTION_FILETYPES)
        except ImportError:
            _snack(page, "tkinter is not available for file browse.", ft.Colors.RED_700)
            return
        if path:
            presenter.load_caption_path(path)
            page.update()

    menu = ft.PopupMenuButton(
        icon=ft.Icons.MENU,
        items=[
            ft.PopupMenuItem(content="Open video file…", on_click=lambda _: page.run_task(_pick_open_video)),
            ft.PopupMenuItem(content="Open caption…", on_click=lambda _: page.run_task(_pick_open_caption)),
            ft.PopupMenuItem(content="Transcribe (Whisper)", on_click=lambda _: page.run_task(presenter.run_whisper_transcript)),
            ft.PopupMenuItem(content="Practice mode: Full-text", on_click=lambda _: (presenter.set_practice_mode("full_text"), page.update())),
            ft.PopupMenuItem(content="Practice mode: Sentence-by-sentence", on_click=lambda _: (presenter.set_practice_mode("sentence_by_sentence"), page.update())),
            ft.PopupMenuItem(content="Practice mode: OFF", on_click=lambda _: (presenter.disable_practice_mode(), page.update())),
            ft.PopupMenuItem(content="Show caption", on_click=lambda _: (presenter.toggle_show_caption(), page.update())),
            ft.PopupMenuItem(content="Play URL from clipboard", on_click=lambda _: page.run_task(_paste_url)),
            ft.PopupMenuItem(content="YouTube URL from clipboard (yt-dlp)", on_click=lambda _: page.run_task(_paste_yt)),
            ft.PopupMenuItem(content="Toggle control bar (S)", on_click=lambda _: toggle_controls_visible()),
            ft.PopupMenuItem(content="16 : 9", on_click=lambda _: set_aspect169()),
            ft.PopupMenuItem(content="4 : 3", on_click=lambda _: set_aspect43()),
            ft.PopupMenuItem(content="Info (I)", on_click=lambda _: show_info_dialog()),
            ft.PopupMenuItem(content="Exit", on_click=lambda _: page.run_task(request_exit_app_async)),
        ],
    )
    top_bar = ft.Row([practice_mode_text, menu], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    async def on_key(e: ft.KeyboardEvent) -> None:
        if e.alt or e.ctrl or e.meta:
            return
        key = e.key
        if caption_focused["v"] and key not in ("Arrow Up", "Up", "Arrow Down", "Down"):
            return
        if key in ("S", "s"):
            toggle_controls_visible()
        elif key in ("I", "i"):
            show_info_dialog()
        elif key in ("Arrow Up", "Up"):
            if presenter.session.practice_mode:
                await presenter.last_caption()
            page.update()
        elif key in ("Arrow Down", "Down"):
            if presenter.session.practice_mode:
                await presenter.next_caption(True, caption_input.value or "")
            page.update()
        elif key in ("Arrow Left", "Left"):
            await presenter.seek_delta_ms(-(600000 if e.shift else 60000))
        elif key in ("Arrow Right", "Right"):
            await presenter.seek_delta_ms(600000 if e.shift else 60000)

    page.on_keyboard_event = on_key
    video.on_error = lambda ev: hooks.show_error(str(ev.data) if ev.data else "Video error")
    if initial_video_uri:
        set_current_video_name(Path(initial_video_uri).name if "://" not in initial_video_uri else initial_video_uri)
    elif default_video is not None:
        set_current_video_name(default_video.name)

    page.add(ft.Column([top_bar, current_media_info, root], expand=True, spacing=0))

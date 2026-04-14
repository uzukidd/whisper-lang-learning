"""Coordinates PlaybackPort + CaptionSession + file paths (no Flet controls)."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .caption_io import load_caption_pickle, save_result_log
from .caption_session import CaptionSession
from .flet_video_backend import FletVideoBackend
from .time_format import format_hms_from_us
from .whisper_service import transcribe_media_to_caption_segments
from .yt_resolve import resolve_youtube_stream_url


@dataclass
class PlayerViewHooks:
    set_times: Callable[[str, str], None]
    set_slider_ratio: Callable[[float], None]
    set_caption_display: Callable[[str], None]
    set_caption_input: Callable[[str], None]
    set_caption_input_enabled: Callable[[bool], None]
    set_playing: Callable[[bool], None]
    show_error: Callable[[str], None]
    show_info: Callable[[str], None]
    confirm_finish_practice: Callable[[], Awaitable[bool]]
    on_language_font: Callable[[Optional[str]], None]
    request_exit_app: Callable[[], None]


class VideoPlayerPresenter:
    def __init__(self, backend: FletVideoBackend, session: CaptionSession, hooks: PlayerViewHooks) -> None:
        self.backend = backend
        self.session = session
        self.hooks = hooks
        self.media_source: Optional[str] = None
        self._volume = 80.0
        self.whisper_model_name = os.environ.get("WHISPER_MODEL", "base")
        self.whisper_device: Optional[str] = os.environ.get("WHISPER_DEVICE")

    def bind_tick(self) -> None:
        self.backend.set_on_tick(self._on_tick)

    async def _on_tick(self, pos_us: int, dur_us: int) -> None:
        pos_ms = pos_us // 1000
        if self.session.practice_should_pause(pos_ms):
            await self.backend.pause()
        cap = self.session.caption_display_text(pos_ms)
        self.hooks.set_caption_display(cap)
        self.hooks.set_times(format_hms_from_us(pos_us), format_hms_from_us(dur_us))
        if not self.backend.scrubbing and dur_us > 0:
            self.hooks.set_slider_ratio(self.backend.slider_ratio_from_position(pos_us))

    async def toggle_play(self) -> None:
        await self.backend.play_or_pause()
        playing = await self.backend.is_playing()
        self.hooks.set_playing(playing)

    async def seek_slider_ratio(self, ratio: float) -> None:
        await self.backend.seek_slider_ratio(ratio)

    def on_caption_input_changed(self, text: str) -> None:
        self.session.save_input_to_answer(text)

    async def load_local_path(self, path: str, load_sidecar_caption: bool = True) -> None:
        p = Path(path)
        self.media_source = str(p.resolve())
        uri = p.resolve().as_uri()
        await self.backend.set_playlist_uri(uri, autoplay=True)
        self.hooks.set_times("00:00:00", format_hms_from_us(self.backend.duration_us))
        if load_sidecar_caption:
            cap_path = p.parent / (p.stem + ".caption")
            if cap_path.is_file():
                self.load_caption_path(str(cap_path))

    async def load_stream_uri(self, uri: str) -> None:
        self.media_source = None
        await self.backend.set_playlist_uri(uri, autoplay=True)
        self.hooks.set_times("00:00:00", format_hms_from_us(self.backend.duration_us))

    async def play_clipboard_url(self, url: str) -> None:
        await self.load_stream_uri(url.strip())

    async def play_youtube_clipboard(self, page_url: str) -> None:
        direct = await resolve_youtube_stream_url(page_url.strip())
        await self.load_stream_uri(direct)

    def load_caption_path(self, path: str) -> None:
        data = load_caption_pickle(path)
        self.session.load_caption_data(data)
        self.hooks.on_language_font(self.session.caption_language())
        if self.session.caption_answer is not None and self.session.caption_idx >= 0:
            self.hooks.set_caption_input(self.session.caption_answer[self.session.caption_idx])

    async def replay_caption(self) -> None:
        ms = self.session.replay_start_ms()
        if ms is not None:
            await self.backend.seek_microseconds(ms * 1000)
            await self.backend.play()

    async def last_caption(self) -> None:
        action, text = self.session.last_caption()
        if action == "replay":
            self.hooks.set_caption_input(text)
            await self.replay_caption()

    async def next_caption(self, next_flag: bool, current_input: str) -> None:
        action, text = self.session.next_caption(next_flag, current_input)
        if action == "replay":
            self.hooks.set_caption_input(text)
            await self.replay_caption()
        elif action == "advance":
            self.hooks.set_caption_input(text)
            await self.replay_caption()
        elif action == "finish_prompt":
            await self.backend.pause()
            ok = await self.hooks.confirm_finish_practice()
            if ok:
                if self.session.caption_text and self.session.caption_answer:
                    save_result_log(self.session.caption_text, self.session.caption_answer, ".")
                self.hooks.request_exit_app()

    def toggle_practice_mode(self) -> None:
        self.session.toggle_practice_mode()
        self.hooks.set_caption_input_enabled(self.session.practice_mode)
        if not self.session.practice_mode:
            self.hooks.set_caption_display("")

    def toggle_show_caption(self) -> None:
        self.session.toggle_caption_show()
        if not self.session.caption_show:
            self.hooks.set_caption_display("")

    async def volume_delta(self, delta: float) -> None:
        self._volume = max(0.0, min(100.0, self._volume + delta))
        await self.backend.set_volume(self._volume)

    async def seek_delta_ms(self, delta_ms: int) -> None:
        pos = await self.backend.get_position_us()
        await self.backend.seek_microseconds(pos + delta_ms * 1000)

    async def run_whisper_transcript(self) -> None:
        if not self.media_source:
            self.hooks.show_error("No local media loaded for transcription.")
            return
        await self.backend.pause()
        try:
            segments, cap_path = await asyncio.to_thread(
                transcribe_media_to_caption_segments,
                self.media_source,
                self.whisper_model_name,
                self.whisper_device,
            )
        except Exception as e:
            self.hooks.show_error(str(e))
            return
        self.session.load_caption_data(segments)
        self.hooks.on_language_font(self.session.caption_language())
        self.hooks.set_caption_input(self.session.caption_answer[0] if self.session.caption_answer else "")
        self.hooks.show_info(f"Transcription saved: {cap_path}")

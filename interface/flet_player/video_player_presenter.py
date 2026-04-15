"""Coordinates PlaybackPort + CaptionSession + file paths (no Flet controls)."""

from __future__ import annotations

import asyncio
import os
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .caption_io import load_caption_pickle, save_result_log
from .caption_session import CaptionSession, PracticeType
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
    focus_caption_input: Callable[[], None]
    set_sentence_feedback: Callable[[list[tuple[str, bool]], bool], None]
    set_caption_input_enabled: Callable[[bool], None]
    set_slider_enabled: Callable[[bool], None]
    set_practice_mode_text: Callable[[str], None]
    set_playing: Callable[[bool], None]
    show_error: Callable[[str], None]
    show_info: Callable[[str], None]
    set_transcribe_busy: Callable[[bool, str], None]
    confirm_finish_practice: Callable[[], Awaitable[bool]]
    on_language_font: Callable[[Optional[str]], None]
    request_exit_app: Callable[[], None]


class VideoPlayerPresenter:
    def __init__(self, backend: FletVideoBackend, session: CaptionSession, hooks: PlayerViewHooks) -> None:
        self.backend = backend
        self.session = session
        self.hooks = hooks
        self.media_source: Optional[str] = None
        self.whisper_model_name = os.environ.get("WHISPER_MODEL", "base")
        self.whisper_device: Optional[str] = os.environ.get("WHISPER_DEVICE")
        self._submit_locked = False

    def bind_tick(self) -> None:
        self.backend.set_on_tick(self._on_tick)

    def _caption_or_progress(self, position_ms: int) -> str:
        cap = self.session.caption_display_text(position_ms)
        if cap:
            return cap
        if self.session.caption_text is not None and not self.session.caption_show:
            return self.session.caption_progress_text()
        return ""

    @staticmethod
    def _normalize_token(token: str) -> str:
        punct = string.punctuation + "“”‘’，。！？；：、…"
        return token.strip().strip(punct).lower()

    def _compare_sentence_words(self, user_input: str, expected_caption: str) -> tuple[list[tuple[str, bool]], bool]:
        user_tokens = [t for t in user_input.split() if t]
        expected_tokens = [t for t in expected_caption.split() if t]
        word_marks: list[tuple[str, bool]] = []
        all_ok = len(user_tokens) == len(expected_tokens)
        for i, expected in enumerate(expected_tokens):
            user_word = user_tokens[i] if i < len(user_tokens) else ""
            ok = bool(user_word) and self._normalize_token(user_word) == self._normalize_token(expected)
            word_marks.append((expected, ok))
            if not ok:
                all_ok = False
        return word_marks, all_ok

    async def _on_tick(self, pos_us: int, dur_us: int) -> None:
        pos_ms = pos_us // 1000
        if self.session.practice_should_pause(pos_ms):
            await self.backend.pause()
        cap = self._caption_or_progress(pos_ms)
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

    def is_submit_locked(self) -> bool:
        return self._submit_locked

    def on_caption_input_changed(self, text: str) -> None:
        self.session.save_input_to_answer(text)

    async def submit_caption(self, current_input: str) -> None:
        if self._submit_locked:
            return
        if self.session.is_sentence_practice_mode():
            await self._submit_sentence_practice(current_input)
            return
        await self.next_caption(False, current_input)

    async def _submit_sentence_practice(self, current_input: str) -> None:
        if self.session.caption_text is None:
            return
        self._submit_locked = True
        self.hooks.focus_caption_input()
        self.session.save_input_to_answer(current_input)
        expected = self.session.current_caption_text()
        word_marks, is_match = self._compare_sentence_words(current_input, expected)
        self.hooks.set_sentence_feedback(word_marks, True)
        try:
            await asyncio.sleep(1.0)
            if is_match:
                await self.next_caption(True, current_input)
            else:
                self.hooks.set_caption_input("")
                self.session.save_input_to_answer("")
                await self.replay_caption()
            self.hooks.set_sentence_feedback([], False)
            self.hooks.focus_caption_input()
        finally:
            self._submit_locked = False

    async def load_local_path(self, path: str, load_sidecar_caption: bool = True) -> None:
        p = Path(path)
        self.media_source = str(p.resolve())
        candidates: list[str] = []
        # 1) Absolute local path (works for many backends).
        candidates.append(self.media_source)
        # 2) file:// URI fallback.
        candidates.append(p.resolve().as_uri())
        # 3) Relative path fallback for Windows absolute-path parser edge-cases.
        try:
            candidates.append(str(p.resolve().relative_to(Path.cwd())))
        except Exception:
            pass

        last_error: Optional[Exception] = None
        for uri in dict.fromkeys(candidates):
            try:
                await self.backend.set_playlist_uri(uri, autoplay=True)
                last_error = None
                break
            except Exception as e:
                last_error = e

        if last_error is not None:
            raise RuntimeError(
                "Failed to open local video. Tried path/file URI variants.\n"
                f"Path: {self.media_source}\n"
                f"Error: {last_error}"
            )
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
        self.hooks.set_caption_display(self._caption_or_progress(0))

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
        if self.session.practice_mode:
            self.disable_practice_mode()
        else:
            self.set_practice_mode("full_text")

    def set_practice_mode(self, mode_type: PracticeType) -> None:
        self.session.set_practice_mode(True, mode_type)
        self.hooks.set_practice_mode_text(
            "Practice: Full-text" if mode_type == "full_text" else "Practice: Sentence-by-sentence"
        )
        self.hooks.set_caption_input_enabled(True)
        self.hooks.set_slider_enabled(False)
        if mode_type != "sentence_by_sentence":
            self.hooks.set_sentence_feedback([], False)

    def disable_practice_mode(self) -> None:
        self.session.set_practice_mode(False, self.session.practice_type)
        self.hooks.set_practice_mode_text("Practice: OFF")
        self.hooks.set_caption_input_enabled(False)
        self.hooks.set_slider_enabled(True)
        self.hooks.set_caption_display("")
        self.hooks.set_sentence_feedback([], False)

    def toggle_show_caption(self) -> None:
        self.session.toggle_caption_show()
        if not self.session.caption_show:
            self.hooks.set_caption_display(self.session.caption_progress_text())

    async def seek_delta_ms(self, delta_ms: int) -> None:
        pos = await self.backend.get_position_us()
        await self.backend.seek_microseconds(pos + delta_ms * 1000)

    async def run_whisper_transcript(self) -> None:
        if not self.media_source:
            self.hooks.show_error("No local media loaded for transcription.")
            return
        self.hooks.set_transcribe_busy(True, f"Transcribing with Whisper ({self.whisper_model_name})...")
        await self.backend.pause()
        try:
            segments, cap_path = await asyncio.to_thread(
                transcribe_media_to_caption_segments,
                self.media_source,
                self.whisper_model_name,
                self.whisper_device,
            )
        except Exception as e:
            self.hooks.set_transcribe_busy(False, "")
            self.hooks.show_error(str(e))
            return
        self.session.load_caption_data(segments)
        self.hooks.on_language_font(self.session.caption_language())
        self.hooks.set_caption_input(self.session.caption_answer[0] if self.session.caption_answer else "")
        self.hooks.set_transcribe_busy(False, "")
        self.hooks.show_info(f"Transcription saved: {cap_path}")

"""Coordinates playback, session state, services, and UI hooks."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from ..domain.caption_session import CaptionSession, PracticeType
from ..domain.scoring import NormalizedExactSentenceScorer, SentenceScorer
from ..infrastructure.caption_pickle_io import save_result_log
from ..infrastructure.caption_repository import CaptionRepository
from ..infrastructure.time_format import format_hms_from_us
from ..infrastructure.whisper_provider import WhisperAsrProvider
from ..infrastructure.yt_resolve import resolve_youtube_stream_url
from .asr import AsrService
from .practice_service import PracticeService


@dataclass
class PlayerViewHooks:
    set_times: Callable[[str, str], None]
    set_slider_ratio: Callable[[float], None]
    set_current_video_name: Callable[[str], None]
    set_current_caption_name: Callable[[str], None]
    set_caption_display: Callable[[str], None]
    set_caption_input: Callable[[str], None]
    focus_caption_input: Callable[[], None]
    set_sentence_feedback: Callable[[list[tuple[str, bool]], bool], None]
    set_caption_input_enabled: Callable[[bool], None]
    set_caption_input_read_only: Callable[[bool], None]
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
    def __init__(
        self,
        backend,
        session: CaptionSession,
        hooks: PlayerViewHooks,
        scorer: SentenceScorer | None = None,
        caption_repository: CaptionRepository | None = None,
        asr_service: AsrService | None = None,
        practice_service: PracticeService | None = None,
    ) -> None:
        self.backend = backend
        self.session = session
        self.hooks = hooks
        scorer = scorer or NormalizedExactSentenceScorer()
        self.caption_repository = caption_repository or CaptionRepository()
        self.asr_service = asr_service or AsrService(WhisperAsrProvider())
        self.practice_service = practice_service or PracticeService(scorer)
        self.media_source: Optional[str] = None
        self.whisper_model_name = os.environ.get("WHISPER_MODEL", "base")
        self.whisper_device: Optional[str] = os.environ.get("WHISPER_DEVICE")
        self._submit_locked = False

    @staticmethod
    def _display_name_from_path(value: str | Path | None) -> str:
        if not value:
            return "None"
        text = str(value).strip()
        if not text:
            return "None"
        try:
            return Path(text).name or text
        except Exception:
            return text

    def bind_tick(self) -> None:
        self.backend.set_on_tick(self._on_tick)

    def _caption_or_progress(self, position_ms: int) -> str:
        cap = self.session.caption_display_text(position_ms)
        if cap:
            return cap
        if self.session.caption_text is not None and not self.session.caption_show:
            return self.session.caption_progress_text()
        return ""

    async def _on_tick(self, pos_us: int, dur_us: int) -> None:
        pos_ms = pos_us // 1000
        if self.session.practice_should_pause(pos_ms):
            await self.backend.pause()
        self.hooks.set_caption_display(self._caption_or_progress(pos_ms))
        self.hooks.set_times(format_hms_from_us(pos_us), format_hms_from_us(dur_us))
        if not self.backend.scrubbing and dur_us > 0:
            self.hooks.set_slider_ratio(self.backend.slider_ratio_from_position(pos_us))

    async def toggle_play(self) -> None:
        await self.backend.play_or_pause()
        self.hooks.set_playing(await self.backend.is_playing())

    async def seek_slider_ratio(self, ratio: float) -> None:
        await self.backend.seek_slider_ratio(ratio)

    def is_submit_locked(self) -> bool:
        return self._submit_locked

    def on_caption_input_changed(self, text: str) -> None:
        self.practice_service.on_input_changed(self.session, text)

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
        try:
            outcome = self.practice_service.submit_sentence(self.session, current_input)
            self.hooks.set_sentence_feedback(outcome.feedback, outcome.show_feedback)
            if outcome.action == "replay":
                await self.replay_caption()
            elif outcome.action == "clear_retry":
                self.hooks.set_caption_input("")
                self.hooks.set_caption_input_read_only(False)
                await self.replay_caption()
            elif outcome.action == "advance":
                await asyncio.sleep(1.0)
                await self.next_caption(True, current_input)
                self.hooks.set_sentence_feedback([], False)
                self.hooks.set_caption_input_read_only(False)
                self.practice_service.reset_retry_state()
            elif outcome.clear_input:
                self.hooks.set_caption_input("")
            self.hooks.focus_caption_input()
        finally:
            self._submit_locked = False

    async def load_local_path(self, path: str, load_sidecar_caption: bool = True) -> None:
        resolved = Path(path).resolve()
        self.media_source = str(resolved)
        self.hooks.set_current_video_name(self._display_name_from_path(resolved))
        candidates: list[str] = [self.media_source, resolved.as_uri()]
        try:
            candidates.append(str(resolved.relative_to(Path.cwd())))
        except Exception:
            pass

        last_error: Optional[Exception] = None
        for uri in dict.fromkeys(candidates):
            try:
                await self.backend.set_playlist_uri(uri, autoplay=True)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise RuntimeError(
                "Failed to open local video. Tried path/file URI variants.\n"
                f"Path: {self.media_source}\n"
                f"Error: {last_error}"
            )
        self.hooks.set_times("00:00:00", format_hms_from_us(self.backend.duration_us))
        if load_sidecar_caption:
            cap_path = resolved.parent / (resolved.stem + ".caption")
            if cap_path.is_file():
                self.load_caption_path(str(cap_path))

    async def load_stream_uri(self, uri: str) -> None:
        self.media_source = None
        self.hooks.set_current_video_name(self._display_name_from_path(uri))
        await self.backend.set_playlist_uri(uri, autoplay=True)
        self.hooks.set_times("00:00:00", format_hms_from_us(self.backend.duration_us))

    async def play_clipboard_url(self, url: str) -> None:
        await self.load_stream_uri(url.strip())

    async def play_youtube_clipboard(self, page_url: str) -> None:
        await self.load_stream_uri(await resolve_youtube_stream_url(page_url.strip()))

    def load_caption_path(self, path: str) -> None:
        data = self.caption_repository.load(path)
        self.session.load_caption_data(data)
        self.hooks.set_current_caption_name(self._display_name_from_path(path))
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
        if action in {"replay", "advance"}:
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
        self.practice_service.reset_retry_state()
        self.hooks.set_practice_mode_text(
            "Practice: Full-text" if mode_type == "full_text" else "Practice: Sentence-by-sentence"
        )
        self.hooks.set_caption_input_enabled(True)
        self.hooks.set_caption_input_read_only(False)
        self.hooks.set_slider_enabled(False)
        if mode_type != "sentence_by_sentence":
            self.hooks.set_sentence_feedback([], False)

    def disable_practice_mode(self) -> None:
        self.session.set_practice_mode(False, self.session.practice_type)
        self.practice_service.reset_retry_state()
        self.hooks.set_practice_mode_text("Practice: OFF")
        self.hooks.set_caption_input_enabled(False)
        self.hooks.set_caption_input_read_only(False)
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
                self.asr_service.transcribe,
                self.media_source,
                model_name=self.whisper_model_name,
                device=self.whisper_device,
            )
        except Exception as exc:
            self.hooks.set_transcribe_busy(False, "")
            self.hooks.show_error(str(exc))
            return
        self.session.load_caption_data(segments)
        self.hooks.set_current_caption_name(self._display_name_from_path(cap_path))
        self.hooks.on_language_font(self.session.caption_language())
        self.hooks.set_caption_input(self.session.caption_answer[0] if self.session.caption_answer else "")
        self.hooks.set_transcribe_busy(False, "")
        self.hooks.show_info(f"Transcription saved: {cap_path}")

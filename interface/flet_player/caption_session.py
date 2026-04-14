"""Caption / practice state machine — same rules as QT6_VideoPlayer (no Flet)."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Any, Optional


def _find_time_interval_index(starts: list[int], ends: list[int], time_ms: int) -> Optional[int]:
    """Mirror QT6 SortedDict + find_time_interval; returns segment index in starts or None."""
    if not starts:
        return None
    pos = bisect.bisect_left(starts, time_ms)
    if pos != len(starts):
        s0, e0 = starts[pos], ends[pos]
        if s0 <= time_ms <= e0:
            return pos
    if pos != 0:
        s1, e1 = starts[pos - 1], ends[pos - 1]
        if s1 <= time_ms <= e1:
            return pos - 1
    return None


@dataclass
class CaptionSession:
    _interval_starts: list[int] = field(default_factory=list)
    _interval_ends: list[int] = field(default_factory=list)
    caption_text: Optional[list[dict[str, Any]]] = None
    caption_answer: Optional[list[str]] = None
    caption_idx: int = -1
    practice_mode: bool = False
    caption_show: bool = False

    def clear_captions(self) -> None:
        self._interval_starts.clear()
        self._interval_ends.clear()
        self.caption_text = None
        self.caption_answer = None
        self.caption_idx = -1

    def load_caption_data(self, caption_text: list[dict[str, Any]]) -> None:
        # Sort by start time so timeline index matches caption_text index (Whisper order).
        ordered = sorted(caption_text, key=lambda s: float(s["start"]))
        self._interval_starts = [int(s["start"] * 1000) for s in ordered]
        self._interval_ends = [int(s["end"] * 1000) for s in ordered]
        self.caption_text = ordered
        self.caption_answer = [""] * len(ordered)
        self.caption_idx = 0

    def caption_language(self) -> Optional[str]:
        if not self.caption_text:
            return None
        first = self.caption_text[0]
        return first.get("language")

    def save_input_to_answer(self, text: str) -> None:
        if self.caption_text is not None and self.caption_answer is not None:
            if 0 <= self.caption_idx < len(self.caption_answer):
                self.caption_answer[self.caption_idx] = text

    def replay_start_ms(self) -> Optional[int]:
        if self.caption_text is None or not (0 <= self.caption_idx < len(self.caption_text)):
            return None
        start_time = int(self.caption_text[self.caption_idx]["start"] * 1000)
        return max(0, start_time)

    def practice_should_pause(self, position_ms: int) -> bool:
        if not self.practice_mode or self.caption_text is None:
            return False
        if not (0 <= self.caption_idx < len(self.caption_text)):
            return False
        seg = self.caption_text[self.caption_idx]
        end_time = int(seg["end"] * 1000)
        return end_time < position_ms

    def caption_display_text(self, position_ms: int) -> str:
        if self.caption_text is None:
            return ""
        if not self.caption_show:
            return ""
        if self.practice_mode:
            if 0 <= self.caption_idx < len(self.caption_text):
                return str(self.caption_text[self.caption_idx].get("text", ""))
            return ""
        res = _find_time_interval_index(self._interval_starts, self._interval_ends, position_ms)
        if res is not None and 0 <= res < len(self.caption_text):
            return str(self.caption_text[res].get("text", ""))
        return ""

    def toggle_practice_mode(self) -> None:
        self.practice_mode = not self.practice_mode

    def toggle_caption_show(self) -> None:
        self.caption_show = not self.caption_show

    def next_caption(
        self,
        next_flag: bool,
        current_input: str,
    ) -> tuple[str, str]:
        if self.caption_text is None:
            return ("noop", "")
        if not next_flag and not current_input:
            return ("replay", self.caption_answer[self.caption_idx] if self.caption_answer else "")

        if self.caption_idx < len(self.caption_text) - 1:
            self.caption_idx += 1
            ans = self.caption_answer[self.caption_idx] if self.caption_answer else ""
            return ("advance", ans)
        return ("finish_prompt", "")

    def last_caption(self) -> tuple[str, str]:
        if self.caption_text is None:
            return ("noop", "")
        if self.caption_idx > 0:
            self.caption_idx -= 1
        ans = self.caption_answer[self.caption_idx] if self.caption_answer else ""
        return ("replay", ans)

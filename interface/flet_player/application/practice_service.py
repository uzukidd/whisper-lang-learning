"""Practice-mode business rules independent from UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..domain.caption_session import CaptionSession
from ..domain.scoring import SentenceScorer

PracticeAction = Literal["replay", "show_feedback", "clear_retry", "advance"]


@dataclass(frozen=True)
class PracticeOutcome:
    action: PracticeAction
    feedback: list[tuple[str, bool]]
    show_feedback: bool
    clear_input: bool
    pending_retry_clear: bool
    is_match: bool


class PracticeService:
    def __init__(self, scorer: SentenceScorer) -> None:
        self.scorer = scorer
        self.pending_retry_clear = False

    def on_input_changed(self, session: CaptionSession, text: str) -> None:
        if self.pending_retry_clear:
            return
        session.save_input_to_answer(text)

    def reset_retry_state(self) -> None:
        self.pending_retry_clear = False

    def submit_sentence(self, session: CaptionSession, current_input: str) -> PracticeOutcome:
        if self.pending_retry_clear:
            self.pending_retry_clear = False
            session.save_input_to_answer("")
            return PracticeOutcome("clear_retry", [], False, True, False, False)

        if not current_input.strip():
            return PracticeOutcome("replay", [], False, False, False, False)

        session.save_input_to_answer(current_input)
        score = self.scorer.score(session.current_caption_text(), current_input)
        feedback = [(item.expected, item.is_match) for item in score.word_matches]
        if score.is_match:
            self.pending_retry_clear = False
            return PracticeOutcome("advance", feedback, True, False, False, True)

        self.pending_retry_clear = True
        return PracticeOutcome("show_feedback", feedback, True, True, True, False)

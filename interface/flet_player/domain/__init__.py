"""Domain models and business rules for the Flet player."""

from .caption_models import CaptionSegment
from .caption_session import CaptionSession, PracticeType
from .scoring import (
    NormalizedExactSentenceScorer,
    SentenceScore,
    SentenceScorer,
    WordMatch,
)

__all__ = [
    "CaptionSegment",
    "CaptionSession",
    "NormalizedExactSentenceScorer",
    "PracticeType",
    "SentenceScore",
    "SentenceScorer",
    "WordMatch",
]

"""Caption repository backed by pickle files."""

from __future__ import annotations

from pathlib import Path

from ..domain.caption_models import CaptionSegment
from .caption_pickle_io import load_caption_pickle, save_caption_pickle


class CaptionRepository:
    def load(self, path: str | Path) -> list[CaptionSegment]:
        raw_segments = load_caption_pickle(path)
        return sorted((CaptionSegment.from_dict(item) for item in raw_segments), key=lambda segment: segment.start)

    def save(self, segments: list[CaptionSegment], path: str | Path) -> None:
        save_caption_pickle([segment.to_dict() for segment in segments], path)

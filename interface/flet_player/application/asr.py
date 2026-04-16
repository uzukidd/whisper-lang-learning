"""ASR abstractions and service entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..domain.caption_models import CaptionSegment


class AsrProvider(Protocol):
    def transcribe(
        self,
        media_path: str | Path,
        model_name: str = "base",
        device: str | None = None,
    ) -> tuple[list[CaptionSegment], str]:
        ...


class AsrService:
    def __init__(self, provider: AsrProvider) -> None:
        self.provider = provider

    def transcribe(
        self,
        media_path: str | Path,
        model_name: str = "base",
        device: str | None = None,
    ) -> tuple[list[CaptionSegment], str]:
        return self.provider.transcribe(media_path, model_name=model_name, device=device)

"""Whisper ASR provider implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..application.asr import AsrProvider
from ..domain.caption_models import CaptionSegment
from .caption_pickle_io import save_caption_pickle


class WhisperAsrProvider(AsrProvider):
    def transcribe(
        self,
        media_path: str | Path,
        model_name: str = "base",
        device: Optional[str] = None,
    ) -> tuple[list[CaptionSegment], str]:
        import torch
        import whisper

        media_path = Path(media_path)
        if not media_path.is_file():
            raise FileNotFoundError(str(media_path))

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        model = whisper.load_model(model_name, device=device)
        result = model.transcribe(str(media_path), verbose=False)
        segments: list[CaptionSegment] = []
        for seg in result["segments"]:
            segments.append(
                CaptionSegment(
                    id=int(seg["id"]),
                    start=float(seg["start"]),
                    end=float(seg["end"]),
                    text=str(seg["text"]),
                    language=result["language"],
                )
            )

        out_path = media_path.parent / (media_path.stem + ".caption")
        save_caption_pickle([segment.to_dict() for segment in segments], out_path)
        return segments, str(out_path)


def transcribe_media_to_caption_segments(
    media_path: str | Path,
    model_name: str = "base",
    device: Optional[str] = None,
) -> tuple[list[CaptionSegment], str]:
    return WhisperAsrProvider().transcribe(media_path, model_name=model_name, device=device)

"""Whisper transcription to .caption pickle (CPU/GPU in worker thread)."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Optional


def transcribe_media_to_caption_segments(
    media_path: str | Path,
    model_name: str = "base",
    device: Optional[str] = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Run whisper.transcribe on media_path.
    Returns (segments list compatible with CaptionSession, caption_file_path).
    """
    import torch
    import whisper

    media_path = Path(media_path)
    if not media_path.is_file():
        raise FileNotFoundError(str(media_path))

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = whisper.load_model(model_name, device=device)
    result = model.transcribe(str(media_path), verbose=False)
    output_text_pkl: list[dict[str, Any]] = []
    for seg in result["segments"]:
        output_text_pkl.append(
            {
                "id": seg["id"],
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "language": result["language"],
            }
        )
    out_path = media_path.parent / (media_path.stem + ".caption")
    with open(out_path, "wb+") as f:
        pickle.dump(output_text_pkl, f)
    return output_text_pkl, str(out_path)

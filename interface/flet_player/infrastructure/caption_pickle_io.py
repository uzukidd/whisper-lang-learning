"""Caption pickle I/O and practice result export."""

from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

from ..domain.caption_models import CaptionSegment


def load_caption_pickle(path: str | Path) -> list[dict[str, Any]]:
    with open(path, "rb") as file_obj:
        return pickle.load(file_obj)


def save_caption_pickle(segments: list[dict[str, Any]], path: str | Path) -> None:
    with open(path, "wb+") as file_obj:
        pickle.dump(segments, file_obj)


def build_result_log(caption_text: list[CaptionSegment], caption_answer: list[str]) -> str:
    result_log = ""
    for idx, (seg, ans) in enumerate(zip(caption_text, caption_answer)):
        result_log += f"idx:{idx}\n"
        result_log += f"text:{seg.text}\n"
        result_log += f"your answer:{ans}\n\n"
    return result_log


def save_result_log(
    caption_text: list[CaptionSegment],
    caption_answer: list[str],
    directory: str | Path = ".",
) -> Path:
    out = Path(directory) / (datetime.now().strftime("%Y-%m-%d-%H-%M-%S") + ".txt")
    out.write_text(build_result_log(caption_text, caption_answer), encoding="utf-8")
    return out

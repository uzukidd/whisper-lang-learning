"""Caption pickle I/O and practice result export (no UI)."""

from __future__ import annotations

import pickle
from datetime import datetime
from pathlib import Path
from typing import Any


def load_caption_pickle(path: str | Path) -> list[dict[str, Any]]:
    with open(path, "rb") as f:
        return pickle.load(f)


def save_caption_pickle(segments: list[dict[str, Any]], path: str | Path) -> None:
    with open(path, "wb+") as f:
        pickle.dump(segments, f)


def build_result_log(caption_text: list[dict[str, Any]], caption_answer: list[str]) -> str:
    result_log = ""
    for idx, (seg, ans) in enumerate(zip(caption_text, caption_answer)):
        text = seg["text"]
        result_log += f"idx:{idx}\n"
        result_log += f"text:{text}\n"
        result_log += f"your answer:{ans}\n"
        result_log += "\n"
    return result_log


def save_result_log(
    caption_text: list[dict[str, Any]],
    caption_answer: list[str],
    directory: str | Path = ".",
) -> Path:
    """Match QT6: ./YYYY-mm-dd-HH-MM-SS.txt"""
    now = datetime.now()
    name = now.strftime("%Y-%m-%d-%H-%M-%S") + ".txt"
    out = Path(directory) / name
    out.write_text(build_result_log(caption_text, caption_answer), encoding="utf-8")
    return out

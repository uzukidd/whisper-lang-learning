"""Caption domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CaptionSegment:
    id: int
    start: float
    end: float
    text: str
    language: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaptionSegment":
        return cls(
            id=int(data["id"]),
            start=float(data["start"]),
            end=float(data["end"]),
            text=str(data.get("text", "")),
            language=data.get("language"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "language": self.language,
        }

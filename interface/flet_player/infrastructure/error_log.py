"""Print errors to console for debugging."""

from __future__ import annotations

import traceback
from typing import Any


def print_error(context: str, exc: Any = "") -> None:
    print(f"[ERROR] {context}: {exc}", flush=True)
    if isinstance(exc, BaseException):
        traceback.print_exception(type(exc), exc, exc.__traceback__)

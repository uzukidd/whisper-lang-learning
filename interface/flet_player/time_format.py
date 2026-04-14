"""Time formatting for playback UI (no Flet dependency)."""


def format_hms_from_us(total_us: int) -> str:
    total_us = max(0, int(total_us))
    total_ms = total_us // 1000
    total_s = total_ms // 1000
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_hms_from_ms(total_ms: int) -> str:
    return format_hms_from_us(int(total_ms) * 1000)

"""YouTube browse domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SubscribedChannel:
    id: str
    name: str
    url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubscribedChannel":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            url=str(data["url"]),
        )


@dataclass(frozen=True)
class YouTubeVideoSummary:
    id: str
    title: str
    thumbnail_url: str
    webpage_url: str
    upload_date: str
    duration_text: str

    @classmethod
    def from_yt_dlp_entry(cls, entry: dict[str, Any]) -> "YouTubeVideoSummary":
        video_id = str(entry.get("id") or "")
        title = str(entry.get("title") or "Untitled")
        raw_url = str(entry.get("webpage_url") or entry.get("url") or "")
        webpage_url = normalize_watch_url(video_id, raw_url)
        thumbnail_url = _pick_thumbnail(entry, video_id)
        upload_date = str(entry.get("upload_date") or "")
        duration_seconds = entry.get("duration")
        duration_text = _format_duration(duration_seconds) if duration_seconds is not None else ""
        return cls(
            id=video_id,
            title=title,
            thumbnail_url=thumbnail_url,
            webpage_url=webpage_url,
            upload_date=upload_date,
            duration_text=duration_text,
        )


@dataclass(frozen=True)
class YouTubeVideoDetail:
    id: str
    title: str
    thumbnail_url: str
    webpage_url: str
    upload_date: str
    duration_text: str
    description: str

    @classmethod
    def from_yt_dlp_entry(cls, entry: dict[str, Any]) -> "YouTubeVideoDetail":
        summary = YouTubeVideoSummary.from_yt_dlp_entry(entry)
        description = str(entry.get("description") or "").strip()
        return cls(
            id=summary.id,
            title=summary.title,
            thumbnail_url=summary.thumbnail_url,
            webpage_url=summary.webpage_url,
            upload_date=summary.upload_date,
            duration_text=summary.duration_text,
            description=description,
        )

    @classmethod
    def from_summary(cls, summary: "YouTubeVideoSummary", description: str = "") -> "YouTubeVideoDetail":
        return cls(
            id=summary.id,
            title=summary.title,
            thumbnail_url=summary.thumbnail_url,
            webpage_url=normalize_watch_url(summary.id, summary.webpage_url),
            upload_date=summary.upload_date,
            duration_text=summary.duration_text,
            description=description,
        )


def normalize_watch_url(video_id: str, webpage_url: str = "") -> str:
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    url = (webpage_url or "").strip()
    if url:
        return url
    raise ValueError("Cannot build YouTube watch URL without video id")


def _pick_thumbnail(entry: dict[str, Any], video_id: str) -> str:
    thumbnail = entry.get("thumbnail")
    if isinstance(thumbnail, str) and thumbnail:
        return thumbnail
    thumbnails = entry.get("thumbnails")
    if isinstance(thumbnails, list) and thumbnails:
        last = thumbnails[-1]
        if isinstance(last, dict) and last.get("url"):
            return str(last["url"])
    if video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return ""


def _format_duration(seconds: Any) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_upload_date(upload_date: str) -> str:
    if len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    return upload_date or "Unknown date"

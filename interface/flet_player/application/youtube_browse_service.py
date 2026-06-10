"""Application service for the YouTube-style browse UI."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

DownloadProgressCallback = Callable[[float, str], None]

from ..domain.youtube_models import (
    SubscribedChannel,
    YouTubeVideoDetail,
    YouTubeVideoSummary,
    derive_channel_id_from_url,
    normalize_channel_videos_url,
    normalize_watch_url,
)
from ..infrastructure.proxy_settings import ProxySettings, load_proxy_settings, save_network_settings
from ..infrastructure.error_log import print_error
from ..infrastructure.thumbnail_fetch import fetch_thumbnail_cached
from ..infrastructure.channel_catalog import (
    fetch_channel_avatar_url,
    fetch_channel_video_count,
    fetch_channel_videos_page,
)
from ..infrastructure.youtube_catalog import (
    download_video_for_practice,
    fetch_video_description,
    fetch_video_detail,
)

DEFAULT_PAGE_SIZE = 5

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CHANNELS_PATH = _REPO_ROOT / "assets" / "channels.json"
_DEFAULT_CACHE_DIR = _REPO_ROOT / "assets" / "cache" / "youtube"
_DEFAULT_THUMB_CACHE_DIR = _REPO_ROOT / "assets" / "cache" / "thumbnails"
_DEFAULT_CHANNEL_ICON_CACHE_DIR = _REPO_ROOT / "assets" / "cache" / "channel_icons"
_DEFAULT_PROXY_PATH = _REPO_ROOT / "assets" / "proxy.json"


class YouTubeBrowseService:
    def __init__(
        self,
        channels_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
        thumb_cache_dir: str | Path | None = None,
        channel_icon_cache_dir: str | Path | None = None,
        proxy_settings: ProxySettings | None = None,
    ) -> None:
        self.channels_path = Path(channels_path or _DEFAULT_CHANNELS_PATH)
        self.cache_dir = Path(cache_dir or _DEFAULT_CACHE_DIR)
        self.thumb_cache_dir = Path(thumb_cache_dir or _DEFAULT_THUMB_CACHE_DIR)
        self.channel_icon_cache_dir = Path(channel_icon_cache_dir or _DEFAULT_CHANNEL_ICON_CACHE_DIR)
        self._proxy_path = Path(_DEFAULT_PROXY_PATH)
        self.proxy_settings = proxy_settings or load_proxy_settings(self._proxy_path)

    def reload_network_settings(self) -> None:
        self.proxy_settings = load_proxy_settings(self._proxy_path)

    def save_network_settings(
        self,
        *,
        proxy_url: str | None = None,
        cookies_text: str | None = None,
    ) -> None:
        self.proxy_settings = save_network_settings(
            proxy_url=proxy_url,
            cookies_text=cookies_text,
            proxy_path=self._proxy_path,
        )

    def load_channels(self) -> list[SubscribedChannel]:
        with open(self.channels_path, encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        channels = payload.get("channels", [])
        if not isinstance(channels, list):
            return []
        return [SubscribedChannel.from_dict(item) for item in channels if isinstance(item, dict)]

    def save_channels(self, channels: list[SubscribedChannel]) -> None:
        payload = {
            "channels": [
                {
                    "id": channel.id,
                    "name": channel.name,
                    "url": channel.url,
                    "source": channel.source,
                }
                for channel in channels
            ]
        }
        self.channels_path.parent.mkdir(parents=True, exist_ok=True)
        self.channels_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def add_channel(self, url: str, name: str | None = None) -> SubscribedChannel:
        normalized_url = normalize_channel_videos_url(url)
        channel_id = derive_channel_id_from_url(normalized_url)
        if not channel_id:
            raise ValueError("Could not derive channel id from URL")
        channels = self.load_channels()
        if any(channel.id == channel_id for channel in channels):
            raise ValueError("Channel already subscribed")
        display_name = (name or "").strip() or channel_id
        channel = SubscribedChannel(
            id=channel_id,
            name=display_name,
            url=normalized_url,
        )
        channels.append(channel)
        self.save_channels(channels)
        return channel

    def remove_channel(self, channel_id: str) -> None:
        channels = [channel for channel in self.load_channels() if channel.id != channel_id]
        self.save_channels(channels)

    def default_channel(self) -> SubscribedChannel | None:
        channels = self.load_channels()
        return channels[0] if channels else None

    def load_channel_videos_page(
        self,
        channel: SubscribedChannel,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[YouTubeVideoSummary], int | None]:
        return fetch_channel_videos_page(
            channel.url,
            source=channel.source,
            page=page,
            page_size=page_size,
            proxy_url=self.proxy_settings.effective_proxy_url(),
        )

    def load_channel_video_count(self, channel: SubscribedChannel) -> int | None:
        return fetch_channel_video_count(
            channel.url,
            source=channel.source,
            proxy_url=self.proxy_settings.effective_proxy_url(),
        )

    def load_video_detail(self, video: YouTubeVideoSummary) -> YouTubeVideoDetail:
        watch_url = normalize_watch_url(video.id, video.webpage_url)
        proxy_url = self.proxy_settings.effective_proxy_url()
        try:
            return fetch_video_detail(watch_url, proxy_url=proxy_url)
        except Exception as exc:
            print_error("load_video_detail", exc)
            description = fetch_video_description(watch_url, proxy_url=proxy_url)
            return YouTubeVideoDetail.from_summary(video, description=description)

    def download_for_practice(
        self,
        video_url: str,
        *,
        video_id: str | None = None,
        on_progress: DownloadProgressCallback | None = None,
    ) -> Path:
        return download_video_for_practice(
            video_url,
            self.cache_dir,
            proxy_url=self.proxy_settings.effective_proxy_url(),
            video_id=video_id,
            on_progress=on_progress,
        )

    def get_thumbnail_src(self, video_id: str, thumbnail_url: str) -> str:
        local_path = fetch_thumbnail_cached(
            video_id,
            thumbnail_url,
            self.thumb_cache_dir,
            self.proxy_settings.effective_proxy_url(),
        )
        if local_path is not None:
            return str(local_path)
        return thumbnail_url

    def get_channel_icon_src(self, channel: SubscribedChannel) -> str:
        cached = self.channel_icon_cache_dir / f"{channel.id}.jpg"
        if cached.is_file() and cached.stat().st_size > 0:
            return str(cached.resolve())

        avatar_url = fetch_channel_avatar_url(
            channel.url,
            source=channel.source,
            proxy_url=self.proxy_settings.effective_proxy_url(),
        )
        if not avatar_url:
            return ""

        local_path = fetch_thumbnail_cached(
            channel.id,
            avatar_url,
            self.channel_icon_cache_dir,
            self.proxy_settings.effective_proxy_url(),
        )
        if local_path is not None:
            return str(local_path)
        return avatar_url

import importlib.util
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_ROOT = _ROOT / "interface" / "flet_player"


def _ensure_package(package_name: str, package_path: Path) -> None:
    if package_name in sys.modules:
        return
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package


def _load_module(module_name: str, relative_path: str):
    module_path = _ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_ensure_package("interface", _ROOT / "interface")
_ensure_package("interface.flet_player", _PACKAGE_ROOT)
_ensure_package("interface.flet_player.domain", _PACKAGE_ROOT / "domain")
_ensure_package("interface.flet_player.infrastructure", _PACKAGE_ROOT / "infrastructure")
_load_module("interface.flet_player.domain.youtube_models", "interface/flet_player/domain/youtube_models.py")
_load_module("interface.flet_player.infrastructure.proxy_settings", "interface/flet_player/infrastructure/proxy_settings.py")
downloader = _load_module(
    "interface.flet_player.infrastructure.youtube_downloader",
    "interface/flet_player/infrastructure/youtube_downloader.py",
)

YouTubeVideoSummary = downloader.YouTubeVideoSummary


class FakeStream:
    def __init__(self, path: str, url: str = "https://example.com/video.mp4") -> None:
        self._path = path
        self.url = url

    def download(self, **_kwargs) -> str:
        Path(self._path).write_bytes(b"video")
        return self._path


class FakeYouTube:
    def __init__(self) -> None:
        self.video_id = "abc123"
        self.title = "Sample Video"
        self.description = "Hello description"
        self.thumbnail_url = "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
        self.watch_url = "https://www.youtube.com/watch?v=abc123"
        self.publish_date = datetime(2026, 3, 1)
        self.length = 125
        self.streams = MagicMock()
        self.streams.filter.return_value.order_by.return_value.asc.return_value.first.return_value = FakeStream(
            str(_ROOT / "tmp_abc123.mp4")
        )
        self.streams.get_lowest_resolution.return_value = None


class YouTubeDownloaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = _ROOT / "tmp_abc123.mp4"
        if self._tmp.exists():
            self._tmp.unlink()

    def tearDown(self) -> None:
        if self._tmp.exists():
            self._tmp.unlink()

    def test_summary_from_youtube_maps_fields(self) -> None:
        summary = downloader._summary_from_youtube(FakeYouTube())

        self.assertEqual("abc123", summary.id)
        self.assertEqual("Sample Video", summary.title)
        self.assertEqual("2:05", summary.duration_text)
        self.assertEqual("20260301", summary.upload_date)

    def test_fetch_video_description(self) -> None:
        original_build = downloader._build_youtube
        downloader._build_youtube = lambda *_args, **_kwargs: FakeYouTube()
        try:
            description = downloader.fetch_video_description("https://www.youtube.com/watch?v=abc123")
        finally:
            downloader._build_youtube = original_build

        self.assertEqual("Hello description", description)

    def test_fetch_video_detail(self) -> None:
        original_build = downloader._build_youtube
        downloader._build_youtube = lambda *_args, **_kwargs: FakeYouTube()
        try:
            detail = downloader.fetch_video_detail("https://www.youtube.com/watch?v=abc123")
        finally:
            downloader._build_youtube = original_build

        self.assertEqual("Hello description", detail.description)
        self.assertEqual("Sample Video", detail.title)

    def test_fetch_channel_videos_page_returns_empty_when_ytdlp_fails(self) -> None:
        original_page = downloader.youtube_ytdlp.fetch_channel_videos_page
        downloader.youtube_ytdlp.fetch_channel_videos_page = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("force failure")
        )
        try:
            page_videos, total = downloader.fetch_channel_videos_page("https://example.com/channel", page=2, page_size=5)
        finally:
            downloader.youtube_ytdlp.fetch_channel_videos_page = original_page

        self.assertIsNone(total)
        self.assertEqual([], page_videos)

    def test_pick_channel_avatar_url_prefers_uncropped_avatar(self) -> None:
        payload = {
            "thumbnails": [
                {"url": "https://example.com/banner.jpg", "id": "0"},
                {"url": "https://example.com/avatar.jpg", "id": "avatar_uncropped"},
            ]
        }
        avatar = downloader.youtube_ytdlp._pick_channel_avatar_url(payload)

        self.assertEqual("https://example.com/avatar.jpg", avatar)

    def test_fetch_channel_video_count_reads_print_output(self) -> None:
        original_count = downloader.youtube_ytdlp.fetch_channel_video_count
        downloader.youtube_ytdlp.fetch_channel_video_count = lambda *_args, **_kwargs: 42
        try:
            total = downloader.fetch_channel_video_count("https://example.com/channel")
        finally:
            downloader.youtube_ytdlp.fetch_channel_video_count = original_count

        self.assertEqual(42, total)

    def test_sort_videos_newest_first(self) -> None:
        older = YouTubeVideoSummary("a", "Old", "", "", "20250101", "")
        newer = YouTubeVideoSummary("b", "New", "", "", "20260301", "")

        sorted_videos = downloader._sort_videos_newest_first([older, newer])

        self.assertEqual("b", sorted_videos[0].id)


if __name__ == "__main__":
    unittest.main()

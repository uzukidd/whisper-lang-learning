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

    def test_fetch_video_description_falls_back_to_pytubefix(self) -> None:
        original_ytdlp = downloader.youtube_ytdlp.fetch_video_description
        original_build = downloader._build_youtube
        downloader.youtube_ytdlp.fetch_video_description = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("yt-dlp failed")
        )
        downloader._build_youtube = lambda *_args, **_kwargs: FakeYouTube()
        try:
            description = downloader.fetch_video_description("https://www.youtube.com/watch?v=abc123")
        finally:
            downloader.youtube_ytdlp.fetch_video_description = original_ytdlp
            downloader._build_youtube = original_build

        self.assertEqual("Hello description", description)

    def test_fetch_video_description_tries_ytdlp_when_pytubefix_empty(self) -> None:
        original_ytdlp = downloader.youtube_ytdlp.fetch_video_description
        original_pytube = downloader._fetch_video_description_pytubefix
        downloader.youtube_ytdlp.fetch_video_description = lambda *_args, **_kwargs: "yt-dlp description"
        downloader._fetch_video_description_pytubefix = lambda *_args, **_kwargs: ""
        try:
            description = downloader.fetch_video_description("https://www.youtube.com/watch?v=abc123")
        finally:
            downloader.youtube_ytdlp.fetch_video_description = original_ytdlp
            downloader._fetch_video_description_pytubefix = original_pytube

        self.assertEqual("yt-dlp description", description)

    def test_fetch_video_detail_falls_back_to_pytubefix(self) -> None:
        original_ytdlp = downloader.youtube_ytdlp.fetch_video_detail
        original_build = downloader._build_youtube
        downloader.youtube_ytdlp.fetch_video_detail = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("yt-dlp failed")
        )
        downloader._build_youtube = lambda *_args, **_kwargs: FakeYouTube()
        try:
            detail = downloader.fetch_video_detail("https://www.youtube.com/watch?v=abc123")
        finally:
            downloader.youtube_ytdlp.fetch_video_detail = original_ytdlp
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

    def test_summarize_yt_dlp_output_skips_download_spam(self) -> None:
        from interface.flet_player.infrastructure.yt_dlp_common import summarize_yt_dlp_output

        text = "\n".join(
            [
                "[download]  22.6% of ~   8.90MiB at  111.15KiB/s ETA 01:05 (frag 23/107)",
                "ERROR: [youtube] abc123: Sign in to confirm you're not a bot",
            ]
        )
        self.assertEqual(
            "ERROR: [youtube] abc123: Sign in to confirm you're not a bot",
            summarize_yt_dlp_output(text),
        )

    def test_parse_yt_dlp_download_percent(self) -> None:
        from interface.flet_player.infrastructure.yt_dlp_common import parse_yt_dlp_download_fraction

        line = "[download]  22.6% of ~   8.90MiB at  111.15KiB/s ETA 01:05 (frag 23/107)"
        fraction = parse_yt_dlp_download_fraction(line)

        self.assertIsNotNone(fraction)
        self.assertAlmostEqual(23 / 107, fraction, places=4)

        plain = "[download]  45.2% of ~  10.50MiB at  1.23MiB/s ETA 00:05"
        self.assertAlmostEqual(0.452, parse_yt_dlp_download_fraction(plain), places=4)

        bounced = parse_yt_dlp_download_fraction(
            "[download]   6.8% of ~  10.82MiB at  127.04KiB/s ETA 00:58 (frag 8/107)",
            last_fraction=0.094,
        )
        self.assertAlmostEqual(8 / 107, bounced, places=4)

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

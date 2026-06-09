import importlib.util
import sys
import types
import unittest
from pathlib import Path

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
youtube_models = _load_module("interface.flet_player.domain.youtube_models", "interface/flet_player/domain/youtube_models.py")
catalog = _load_module("interface.flet_player.infrastructure.youtube_catalog", "interface/flet_player/infrastructure/youtube_catalog.py")

YouTubeVideoSummary = youtube_models.YouTubeVideoSummary
YouTubeVideoDetail = youtube_models.YouTubeVideoDetail


class YouTubeCatalogTests(unittest.TestCase):
    def test_summary_from_entry_builds_thumbnail_and_duration(self) -> None:
        summary = YouTubeVideoSummary.from_yt_dlp_entry(
            {
                "id": "abc123",
                "title": "Sample Video",
                "webpage_url": "https://www.youtube.com/watch?v=abc123",
                "upload_date": "20260301",
                "duration": 125,
            }
        )

        self.assertEqual("abc123", summary.id)
        self.assertEqual("Sample Video", summary.title)
        self.assertIn("abc123", summary.thumbnail_url)
        self.assertEqual("2:05", summary.duration_text)

    def test_detail_includes_description(self) -> None:
        detail = YouTubeVideoDetail.from_yt_dlp_entry(
            {
                "id": "abc123",
                "title": "Sample Video",
                "description": "Hello description",
                "upload_date": "20260301",
            }
        )

        self.assertEqual("Hello description", detail.description)

    def test_normalize_watch_url_prefers_video_id(self) -> None:
        url = youtube_models.normalize_watch_url("abc123", "https://www.youtube.com/@channel/videos")
        self.assertEqual("https://www.youtube.com/watch?v=abc123", url)

    def test_catalog_reexports_downloader(self) -> None:
        self.assertTrue(callable(catalog.fetch_channel_videos))
        self.assertTrue(callable(catalog.fetch_video_detail))
        self.assertTrue(callable(catalog.fetch_video_description))
        self.assertTrue(callable(catalog.download_video_for_practice))


if __name__ == "__main__":
    unittest.main()

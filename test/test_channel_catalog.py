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
_load_module("interface.flet_player.domain.youtube_models", "interface/flet_player/domain/youtube_models.py")
_load_module("interface.flet_player.infrastructure.proxy_settings", "interface/flet_player/infrastructure/proxy_settings.py")
_load_module("interface.flet_player.infrastructure.yt_dlp_common", "interface/flet_player/infrastructure/yt_dlp_common.py")
_load_module("interface.flet_player.infrastructure.youtube_ytdlp", "interface/flet_player/infrastructure/youtube_ytdlp.py")
_load_module("interface.flet_player.infrastructure.youtube_downloader", "interface/flet_player/infrastructure/youtube_downloader.py")
_load_module("interface.flet_player.infrastructure.youtube_catalog", "interface/flet_player/infrastructure/youtube_catalog.py")
channel_catalog = _load_module(
    "interface.flet_player.infrastructure.channel_catalog",
    "interface/flet_player/infrastructure/channel_catalog.py",
)


class ChannelCatalogTests(unittest.TestCase):
    def test_fetch_channel_videos_page_routes_youtube_source(self) -> None:
        called: dict[str, object] = {}

        def fake_fetch(channel_url, page=1, page_size=5, proxy_url=None):
            called["channel_url"] = channel_url
            called["page"] = page
            called["page_size"] = page_size
            return [], 12

        original = channel_catalog._fetch_youtube_channel_videos_page
        channel_catalog._fetch_youtube_channel_videos_page = fake_fetch
        try:
            videos, total = channel_catalog.fetch_channel_videos_page(
                "https://www.youtube.com/@demo/videos",
                source="youtube",
                page=2,
                page_size=5,
            )
        finally:
            channel_catalog._fetch_youtube_channel_videos_page = original

        self.assertEqual([], videos)
        self.assertEqual(12, total)
        self.assertEqual(2, called["page"])

    def test_unsupported_source_raises(self) -> None:
        with self.assertRaises(ValueError):
            channel_catalog.fetch_channel_video_count(
                "https://example.com/channel",
                source="bilibili",
            )


if __name__ == "__main__":
    unittest.main()

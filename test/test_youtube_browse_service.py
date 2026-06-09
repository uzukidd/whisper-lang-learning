import importlib.util
import json
import sys
import tempfile
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
_ensure_package("interface.flet_player.application", _PACKAGE_ROOT / "application")
_load_module("interface.flet_player.domain.youtube_models", "interface/flet_player/domain/youtube_models.py")
_load_module("interface.flet_player.infrastructure.youtube_catalog", "interface/flet_player/infrastructure/youtube_catalog.py")
browse_service_module = _load_module(
    "interface.flet_player.application.youtube_browse_service",
    "interface/flet_player/application/youtube_browse_service.py",
)

YouTubeBrowseService = browse_service_module.YouTubeBrowseService


class YouTubeBrowseServiceTests(unittest.TestCase):
    def test_load_channels_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            channels_path = Path(temp_dir) / "channels.json"
            channels_path.write_text(
                json.dumps(
                    {
                        "channels": [
                            {
                                "id": "samekosaba",
                                "name": "SamekoSaba",
                                "url": "https://www.youtube.com/@SamekoSaba/videos",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            service = YouTubeBrowseService(channels_path=channels_path, cache_dir=temp_dir)

            channels = service.load_channels()
            default_channel = service.default_channel()

        self.assertEqual(1, len(channels))
        self.assertEqual("SamekoSaba", channels[0].name)
        self.assertIsNotNone(default_channel)
        self.assertEqual("samekosaba", default_channel.id)

    def test_get_channel_icon_src_uses_disk_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            channels_path = temp_path / "channels.json"
            channels_path.write_text(
                json.dumps(
                    {
                        "channels": [
                            {
                                "id": "samekosaba",
                                "name": "SamekoSaba",
                                "url": "https://www.youtube.com/@SamekoSaba/videos",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            icon_cache = temp_path / "channel_icons"
            icon_cache.mkdir()
            cached_icon = icon_cache / "samekosaba.jpg"
            cached_icon.write_bytes(b"icon")
            service = YouTubeBrowseService(
                channels_path=channels_path,
                cache_dir=temp_path,
                channel_icon_cache_dir=icon_cache,
            )
            channel = service.load_channels()[0]

            src = service.get_channel_icon_src(channel)

        self.assertEqual(str(cached_icon.resolve()), src)

if __name__ == "__main__":
    unittest.main()

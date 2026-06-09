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
_ensure_package("interface.flet_player.infrastructure", _PACKAGE_ROOT / "infrastructure")
proxy_settings = _load_module(
    "interface.flet_player.infrastructure.proxy_settings",
    "interface/flet_player/infrastructure/proxy_settings.py",
)

ProxySettings = proxy_settings.ProxySettings
load_proxy_settings = proxy_settings.load_proxy_settings
yt_dlp_proxy_args = proxy_settings.yt_dlp_proxy_args
yt_dlp_network_args = proxy_settings.yt_dlp_network_args


class ProxySettingsTests(unittest.TestCase):
    def test_load_proxy_settings_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proxy_path = Path(temp_dir) / "proxy.json"
            proxy_path.write_text(
                json.dumps({"enabled": True, "proxy_url": "http://127.0.0.1:7890"}),
                encoding="utf-8",
            )
            settings = load_proxy_settings(proxy_path)

        self.assertTrue(settings.enabled)
        self.assertEqual("http://127.0.0.1:7890", settings.effective_proxy_url())
        self.assertIsNone(settings.effective_cookies_browser())

    def test_load_proxy_settings_uses_cookies_only_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proxy_path = Path(temp_dir) / "proxy.json"
            proxy_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "proxy_url": "http://127.0.0.1:7890",
                        "cookies_from_browser": "chrome",
                    }
                ),
                encoding="utf-8",
            )
            settings = load_proxy_settings(proxy_path)

        self.assertEqual("chrome", settings.effective_cookies_browser())

    def test_disabled_proxy_returns_none(self) -> None:
        settings = ProxySettings(enabled=False, proxy_url="http://127.0.0.1:7890")
        self.assertIsNone(settings.effective_proxy_url())

    def test_yt_dlp_proxy_args(self) -> None:
        self.assertEqual(["--proxy", "http://127.0.0.1:7890"], yt_dlp_proxy_args("http://127.0.0.1:7890"))
        self.assertEqual([], yt_dlp_proxy_args(None))

    def test_yt_dlp_network_args_without_cookies(self) -> None:
        settings = ProxySettings(enabled=True, proxy_url="http://127.0.0.1:7890")
        self.assertEqual(["--proxy", "http://127.0.0.1:7890"], yt_dlp_network_args(settings))

    def test_yt_dlp_network_args_include_browser_cookies(self) -> None:
        settings = ProxySettings(
            enabled=True,
            proxy_url="http://127.0.0.1:7890",
            cookies_from_browser="edge",
        )
        self.assertEqual(
            ["--proxy", "http://127.0.0.1:7890", "--cookies-from-browser", "edge"],
            yt_dlp_network_args(settings),
        )


if __name__ == "__main__":
    unittest.main()

import importlib.util

import json

import sys

import tempfile

import types

import unittest

from pathlib import Path

from unittest.mock import patch



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

sync_yt_dlp_cookies_work_file = proxy_settings.sync_yt_dlp_cookies_work_file

read_cookies_text = proxy_settings.read_cookies_text

save_network_settings = proxy_settings.save_network_settings

_EJS_ARGS = ["--js-runtimes", "node", "--remote-components", "ejs:github"]


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

        with patch.object(proxy_settings, "_DEFAULT_COOKIES_FILE", Path("missing-cookies.txt")):

            settings = ProxySettings(enabled=True, proxy_url="http://127.0.0.1:7890")

            self.assertEqual(["--proxy", "http://127.0.0.1:7890", *_EJS_ARGS], yt_dlp_network_args(settings))



    def test_yt_dlp_network_args_include_browser_cookies(self) -> None:

        with patch.object(proxy_settings, "_DEFAULT_COOKIES_FILE", Path("missing-cookies.txt")):

            settings = ProxySettings(

                enabled=True,

                proxy_url="http://127.0.0.1:7890",

                cookies_from_browser="edge",

            )

            self.assertEqual(

                ["--proxy", "http://127.0.0.1:7890", *_EJS_ARGS, "--cookies-from-browser", "edge"],

                yt_dlp_network_args(settings),

            )



    def test_yt_dlp_network_args_prefers_cookies_file(self) -> None:

        with tempfile.TemporaryDirectory() as temp_dir:

            temp_path = Path(temp_dir)

            cookies_path = temp_path / "cookies.txt"

            cookies_path.write_text("# Netscape HTTP Cookie File\n.example\tTRUE\t/\tFALSE\t0\tSID\tabc\n", encoding="utf-8")

            work_path = temp_path / ".cookies.ytdlp.work.txt"

            with patch.object(proxy_settings, "_DEFAULT_COOKIES_FILE", cookies_path), patch.object(

                proxy_settings, "_YTDLP_COOKIES_WORK_FILE", work_path

            ):

                settings = ProxySettings(

                    enabled=True,

                    proxy_url="http://127.0.0.1:7890",

                    cookies_from_browser="edge",

                )

                self.assertEqual(str(cookies_path.resolve()), settings.effective_cookies_file())
                sync_yt_dlp_cookies_work_file(settings)
                args = yt_dlp_network_args(settings)
                self.assertEqual(
                    ["--proxy", "http://127.0.0.1:7890", *_EJS_ARGS, "--cookies", str(work_path.resolve())],
                    args,
                )
                self.assertEqual(cookies_path.read_bytes(), work_path.read_bytes())

    def test_sync_yt_dlp_cookies_work_file_overwrites_stale_work_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cookies_path = temp_path / "cookies.txt"
            work_path = temp_path / ".cookies.ytdlp.work.txt"
            cookies_path.write_text("# Netscape HTTP Cookie File\nfresh\n", encoding="utf-8")
            work_path.write_text("stale work copy\n", encoding="utf-8")
            with patch.object(proxy_settings, "_DEFAULT_COOKIES_FILE", cookies_path), patch.object(
                proxy_settings, "_YTDLP_COOKIES_WORK_FILE", work_path
            ):
                settings = ProxySettings(enabled=True, proxy_url="http://127.0.0.1:7890")
                synced = sync_yt_dlp_cookies_work_file(settings)
                self.assertEqual(str(work_path.resolve()), synced)
                self.assertEqual(cookies_path.read_bytes(), work_path.read_bytes())

    def test_yt_dlp_network_args_keep_ejs_when_cookies_disabled(self) -> None:
        settings = ProxySettings(enabled=True, proxy_url="http://127.0.0.1:7890")
        self.assertEqual(
            ["--proxy", "http://127.0.0.1:7890", *_EJS_ARGS],
            yt_dlp_network_args(settings, use_cookies=False),
        )

    def test_save_network_settings_optional_proxy_and_cookies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            proxy_path = temp_path / "proxy.json"
            cookies_path = temp_path / "cookies.txt"
            settings = save_network_settings(
                proxy_url="http://127.0.0.1:7890",
                cookies_text="# Netscape HTTP Cookie File\n.example\tTRUE\t/\tFALSE\t0\tSID\tabc\n",
                proxy_path=proxy_path,
                cookies_path=cookies_path,
            )
            self.assertTrue(settings.enabled)
            self.assertEqual("http://127.0.0.1:7890", settings.effective_proxy_url())
            self.assertIn("SID", read_cookies_text(cookies_path))

            settings = save_network_settings(
                proxy_url="",
                cookies_text="",
                proxy_path=proxy_path,
                cookies_path=cookies_path,
            )
            self.assertFalse(settings.enabled)
            self.assertIsNone(settings.effective_proxy_url())
            self.assertFalse(cookies_path.is_file())

if __name__ == "__main__":

    unittest.main()


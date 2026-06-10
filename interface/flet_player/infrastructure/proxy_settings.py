"""Load network proxy settings for YouTube access."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .yt_dlp_common import yt_dlp_youtube_args

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROXY_PATH = _REPO_ROOT / "assets" / "proxy.json"
_DEFAULT_COOKIES_FILE = _REPO_ROOT / "assets" / "cache" / "cookies.txt"
_YTDLP_COOKIES_WORK_FILE = _DEFAULT_COOKIES_FILE.parent / ".cookies.ytdlp.work.txt"
_DEFAULT_PROXY_URL = "http://127.0.0.1:7890"


@dataclass(frozen=True)
class ProxySettings:
    enabled: bool
    proxy_url: str
    cookies_from_browser: str = ""

    def effective_proxy_url(self) -> str | None:
        if not self.enabled:
            return None
        url = (self.proxy_url or "").strip()
        return url or None

    def effective_cookies_browser(self) -> str | None:
        browser = (self.cookies_from_browser or "").strip()
        return browser or None

    def effective_cookies_file(self) -> str | None:
        if not _DEFAULT_COOKIES_FILE.is_file():
            return None
        if _DEFAULT_COOKIES_FILE.stat().st_size <= 0:
            return None
        return str(_DEFAULT_COOKIES_FILE.resolve())

    def uses_yt_dlp_cookies(self) -> bool:
        return self.effective_cookies_file() is not None or self.effective_cookies_browser() is not None


def read_cookies_text(path: str | Path | None = None) -> str:
    cookies_path = Path(path or _DEFAULT_COOKIES_FILE)
    if not cookies_path.is_file():
        return ""
    return cookies_path.read_text(encoding="utf-8")


def save_network_settings(
    *,
    proxy_url: str | None = None,
    cookies_text: str | None = None,
    proxy_path: str | Path | None = None,
    cookies_path: str | Path | None = None,
) -> ProxySettings:
    resolved_proxy_path = Path(proxy_path or _DEFAULT_PROXY_PATH)
    resolved_cookies_path = Path(cookies_path or _DEFAULT_COOKIES_FILE)
    resolved_proxy_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_cookies_path.parent.mkdir(parents=True, exist_ok=True)

    url = (proxy_url or "").strip()
    payload = {
        "enabled": bool(url),
        "proxy_url": url,
        "cookies_from_browser": "",
    }
    resolved_proxy_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    text = cookies_text if cookies_text is not None else ""
    stripped = text.strip()
    if stripped:
        if not text.endswith("\n"):
            text = text + "\n"
        resolved_cookies_path.write_text(text, encoding="utf-8")
    elif resolved_cookies_path.is_file():
        resolved_cookies_path.unlink()

    return load_proxy_settings(resolved_proxy_path)


def load_proxy_settings(path: str | Path | None = None) -> ProxySettings:
    proxy_path = Path(path or _DEFAULT_PROXY_PATH)
    if not proxy_path.is_file():
        return ProxySettings(enabled=True, proxy_url=_DEFAULT_PROXY_URL)
    with open(proxy_path, encoding="utf-8") as file_obj:
        payload = json.load(file_obj)
    if not isinstance(payload, dict):
        return ProxySettings(enabled=True, proxy_url=_DEFAULT_PROXY_URL)
    enabled = bool(payload.get("enabled", True))
    proxy_url = str(payload.get("proxy_url") or _DEFAULT_PROXY_URL).strip()
    cookies_from_browser = ""
    if "cookies_from_browser" in payload and payload.get("cookies_from_browser") is not None:
        cookies_from_browser = str(payload.get("cookies_from_browser")).strip()
    return ProxySettings(
        enabled=enabled,
        proxy_url=proxy_url or _DEFAULT_PROXY_URL,
        cookies_from_browser=cookies_from_browser,
    )


def yt_dlp_proxy_args(proxy_url: str | None) -> list[str]:
    if not proxy_url:
        return []
    return ["--proxy", proxy_url]


def sync_yt_dlp_cookies_work_file(settings: ProxySettings) -> str | None:
    """Force-copy cookies.txt to the work file before each yt-dlp invocation."""
    cookies_file = settings.effective_cookies_file()
    if not cookies_file:
        return None
    src = Path(cookies_file)
    _YTDLP_COOKIES_WORK_FILE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, _YTDLP_COOKIES_WORK_FILE)
    return str(_YTDLP_COOKIES_WORK_FILE.resolve())


def yt_dlp_cookies_args(settings: ProxySettings) -> list[str]:
    if settings.effective_cookies_file():
        return ["--cookies", str(_YTDLP_COOKIES_WORK_FILE.resolve())]
    browser = settings.effective_cookies_browser()
    if browser:
        return ["--cookies-from-browser", browser]
    return []


def yt_dlp_network_args(
    settings: ProxySettings,
    proxy_url: str | None = None,
    *,
    use_cookies: bool = True,
) -> list[str]:
    effective_proxy = proxy_url if proxy_url is not None else settings.effective_proxy_url()
    args = [
        *yt_dlp_proxy_args(effective_proxy),
        *yt_dlp_youtube_args(),
    ]
    if use_cookies:
        args.extend(yt_dlp_cookies_args(settings))
    return args

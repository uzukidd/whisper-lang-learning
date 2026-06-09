"""Load network proxy settings for YouTube access."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PROXY_PATH = _REPO_ROOT / "assets" / "proxy.json"
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


def yt_dlp_network_args(settings: ProxySettings, proxy_url: str | None = None) -> list[str]:
    effective_proxy = proxy_url if proxy_url is not None else settings.effective_proxy_url()
    args = yt_dlp_proxy_args(effective_proxy)
    browser = settings.effective_cookies_browser()
    if browser:
        args.extend(["--cookies-from-browser", browser])
    return args

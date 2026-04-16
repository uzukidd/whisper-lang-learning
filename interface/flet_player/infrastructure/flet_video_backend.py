"""Flet + flet_video implementation of the playback port."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional

import flet as ft
import flet_video as ftv

from ..ports.playback_port import PlaybackPort

TickCallback = Callable[[int, int], Awaitable[None]]


class FletVideoBackend(PlaybackPort):
    def __init__(self, page: ft.Page, video: ftv.Video) -> None:
        self._page = page
        self._video = video
        self.duration_us: int = 0
        self.scrubbing: bool = False
        self._tick_armed: bool = False
        self._on_tick: Optional[TickCallback] = None
        self._poll_interval: float = 0.25

    def set_on_tick(self, cb: Optional[TickCallback]) -> None:
        self._on_tick = cb

    def arm_load_handler(self) -> None:
        def _on_video_load(_: ft.ControlEvent) -> None:
            if self._tick_armed:
                return
            self._tick_armed = True

            async def _setup_then_poll() -> None:
                await self._wait_for_duration()
                self._page.update()
                while True:
                    try:
                        if self.duration_us <= 0:
                            await self._refresh_duration()
                        pos_us = await self.get_position_us()
                        if self._on_tick:
                            await self._on_tick(pos_us, self.duration_us)
                        self._page.update()
                    except Exception:
                        pass
                    await asyncio.sleep(self._poll_interval)

            self._page.run_task(_setup_then_poll)

        self._video.on_load = _on_video_load

    async def _refresh_duration(self) -> bool:
        try:
            dur = await self._video.get_duration()
            du = dur.in_microseconds
            if du > 0:
                self.duration_us = du
                return True
        except Exception:
            pass
        return False

    async def _wait_for_duration(self) -> None:
        for _ in range(80):
            if await self._refresh_duration():
                return
            await asyncio.sleep(0.1)

    async def play(self) -> None:
        await self._video.play()

    async def pause(self) -> None:
        await self._video.pause()

    async def play_or_pause(self) -> None:
        await self._video.play_or_pause()

    async def is_playing(self) -> bool:
        return await self._video.is_playing()

    async def seek_microseconds(self, position_us: int) -> None:
        await self._video.seek(ft.Duration.from_unit(microseconds=max(0, int(position_us))))

    async def get_position_us(self) -> int:
        pos = await self._video.get_current_position()
        return max(0, pos.in_microseconds)

    async def get_duration_us(self) -> int:
        if self.duration_us > 0:
            return self.duration_us
        dur = await self._video.get_duration()
        self.duration_us = max(0, dur.in_microseconds)
        return self.duration_us

    async def set_playlist_uri(self, uri: str, autoplay: bool = True) -> None:
        self._video.playlist = [ftv.VideoMedia(uri)]
        self._video.autoplay = False
        self.duration_us = 0
        self._page.update()
        try:
            await self._video.jump_to(0)
        except Exception:
            pass
        if autoplay:
            await self._video.play()
        await self._wait_for_duration()
        if self.duration_us <= 0:
            raise RuntimeError(f"Video load timeout or unsupported resource: {uri}")

    def set_scrubbing(self, value: bool) -> None:
        self.scrubbing = value

    def slider_ratio_from_position(self, position_us: int) -> float:
        if self.duration_us <= 0:
            return 0.0
        return min(1.0, max(0.0, position_us / float(self.duration_us)))

    async def seek_slider_ratio(self, ratio: float) -> None:
        if self.duration_us <= 0:
            return
        target = int(min(1.0, max(0.0, ratio)) * self.duration_us)
        await self.seek_microseconds(target)

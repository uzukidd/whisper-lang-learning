"""YouTube-style channel browse UI."""

from __future__ import annotations

import asyncio
from typing import Optional

import flet as ft

from ..application.youtube_browse_service import DEFAULT_PAGE_SIZE, YouTubeBrowseService
from ..domain.youtube_models import (
    SubscribedChannel,
    YouTubeVideoSummary,
    format_upload_date,
)
from .flet_video_player_page import build_video_player_page

_CHANNEL_WIDTH = 220
_CHANNEL_ICON_SIZE = 36
_THUMB_WIDTH = 220
_THUMB_HEIGHT = 124


def _snack(page: ft.Page, message: str, bgcolor: str) -> None:
    page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=bgcolor)
    page.snack_bar.open = True
    page.update()


def build_youtube_browse_page(page: ft.Page) -> None:
    page.title = "Whisper Learning Browse"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.bgcolor = ft.Colors.BLACK

    service = YouTubeBrowseService()
    state: dict[str, object] = {
        "channels": service.load_channels(),
        "selected_channel": service.default_channel(),
        "videos": [],
        "selected_video": None,
        "thumbnail_src": {},
        "channel_icon_src": {},
        "page": 1,
        "page_size": DEFAULT_PAGE_SIZE,
        "total_videos": None,
        "has_next_page": False,
    }

    header = ft.Text("Whisper Learning Browse", size=20, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE)
    channel_list = ft.ListView(expand=True, spacing=4, padding=8)
    video_list = ft.ListView(expand=True, spacing=12, padding=8)
    loading_indicator = ft.ProgressRing()
    loading_text = ft.Text("Loading videos...", color=ft.Colors.WHITE70)
    page_info = ft.Text("Page 1/1", color=ft.Colors.WHITE70)
    prev_page_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_LEFT,
        tooltip="Previous page",
        disabled=True,
    )
    next_page_btn = ft.IconButton(
        icon=ft.Icons.CHEVRON_RIGHT,
        tooltip="Next page",
        disabled=True,
    )
    video_panel = ft.Column(
        [
            ft.Row([loading_indicator, loading_text], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row(
                [prev_page_btn, page_info, next_page_btn],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            video_list,
        ],
        expand=True,
        spacing=8,
    )

    def _set_loading(visible: bool, message: str = "Loading videos...") -> None:
        loading_indicator.visible = visible
        loading_text.value = message
        loading_text.visible = visible

    def _channel_icon_src(channel: SubscribedChannel) -> str | None:
        icon_map = state.get("channel_icon_src")
        if isinstance(icon_map, dict):
            src = icon_map.get(channel.id)
            if isinstance(src, str) and src:
                return src
        return None

    def _channel_icon(channel: SubscribedChannel) -> ft.Control:
        src = _channel_icon_src(channel)
        if src:
            return ft.Container(
                width=_CHANNEL_ICON_SIZE,
                height=_CHANNEL_ICON_SIZE,
                border_radius=_CHANNEL_ICON_SIZE // 2,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                content=ft.Image(
                    src=src,
                    width=_CHANNEL_ICON_SIZE,
                    height=_CHANNEL_ICON_SIZE,
                    fit=ft.BoxFit.COVER,
                    error_content=ft.Container(
                        width=_CHANNEL_ICON_SIZE,
                        height=_CHANNEL_ICON_SIZE,
                        bgcolor="#333333",
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=28, color=ft.Colors.WHITE54),
                    ),
                ),
            )
        return ft.Container(
            width=_CHANNEL_ICON_SIZE,
            height=_CHANNEL_ICON_SIZE,
            border_radius=_CHANNEL_ICON_SIZE // 2,
            bgcolor="#333333",
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.ACCOUNT_CIRCLE, size=28, color=ft.Colors.WHITE54),
        )

    def _render_channels() -> None:
        channel_list.controls.clear()
        channels = state["channels"]
        if not isinstance(channels, list):
            return
        selected = state.get("selected_channel")
        for channel in channels:
            if not isinstance(channel, SubscribedChannel):
                continue
            is_selected = isinstance(selected, SubscribedChannel) and selected.id == channel.id
            channel_list.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            _channel_icon(channel),
                            ft.Text(
                                channel.name,
                                color=ft.Colors.WHITE if is_selected else ft.Colors.WHITE70,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor="#272727" if is_selected else ft.Colors.TRANSPARENT,
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    on_click=lambda e, ch=channel: page.run_task(_select_channel, ch),
                )
            )

    def _thumbnail_src(video: YouTubeVideoSummary, *, allow_remote_fallback: bool = False) -> str | None:
        thumb_map = state.get("thumbnail_src")
        if isinstance(thumb_map, dict):
            cached = thumb_map.get(video.id)
            if isinstance(cached, str) and cached:
                return cached
        if allow_remote_fallback and video.thumbnail_url:
            return video.thumbnail_url
        return None

    def _video_thumbnail(video: YouTubeVideoSummary) -> ft.Control:
        src = _thumbnail_src(video)
        if src:
            return ft.Image(
                src=src,
                width=_THUMB_WIDTH,
                height=_THUMB_HEIGHT,
                fit=ft.BoxFit.COVER,
                border_radius=8,
                error_content=ft.Container(
                    width=_THUMB_WIDTH,
                    height=_THUMB_HEIGHT,
                    bgcolor="#333333",
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.VIDEO_LIBRARY, size=48, color=ft.Colors.WHITE54),
                ),
            )
        return ft.Container(
            width=_THUMB_WIDTH,
            height=_THUMB_HEIGHT,
            bgcolor="#333333",
            border_radius=8,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.VIDEO_LIBRARY, size=48, color=ft.Colors.WHITE54),
        )

    def _video_card(video: YouTubeVideoSummary) -> ft.Control:
        card_body = ft.Row(
            [
                _video_thumbnail(video),
                ft.Column(
                    [
                        ft.Text(video.title, size=15, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE, max_lines=2),
                        ft.Text(
                            f"{format_upload_date(video.upload_date)}  {video.duration_text}".strip(),
                            size=12,
                            color=ft.Colors.WHITE54,
                        ),
                    ],
                    spacing=6,
                    expand=True,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        return ft.Container(
            content=ft.GestureDetector(
                content=card_body,
                mouse_cursor=ft.MouseCursor.CLICK,
                on_tap=lambda e, item=video: page.run_task(_open_detail, item),
            ),
            padding=8,
            border_radius=10,
            bgcolor="#212121",
        )

    def _known_total_videos() -> int | None:
        total = state.get("total_videos")
        if isinstance(total, int) and total > 0:
            return total
        return None

    def _total_pages() -> int:
        total = _known_total_videos()
        page_size = int(state.get("page_size") or DEFAULT_PAGE_SIZE)
        if total is None:
            return 1
        return (total + page_size - 1) // page_size

    def _can_go_next_page() -> bool:
        if state.get("has_next_page") is True:
            return True
        total = _known_total_videos()
        if total is None:
            return False
        current_page = int(state.get("page") or 1)
        page_size = int(state.get("page_size") or DEFAULT_PAGE_SIZE)
        return current_page * page_size < total

    def _update_pagination_controls() -> None:
        current_page = int(state.get("page") or 1)
        total = _known_total_videos()
        if total is not None:
            page_info.value = f"Page {current_page}/{_total_pages()}"
        else:
            page_info.value = f"Page {current_page}"
        prev_page_btn.disabled = current_page <= 1
        next_page_btn.disabled = not _can_go_next_page()

    def _render_videos() -> None:
        video_list.controls.clear()
        videos = state.get("videos")
        if not isinstance(videos, list) or not videos:
            video_list.controls.append(ft.Text("No videos found.", color=ft.Colors.WHITE54))
            _update_pagination_controls()
            return
        for video in videos:
            if isinstance(video, YouTubeVideoSummary):
                video_list.controls.append(_video_card(video))
        _update_pagination_controls()

    detail_holder: dict[str, object] = {
        "dialog": None,
        "description": None,
        "request_id": 0,
    }

    def _close_detail_dialog(_: ft.ControlEvent | None = None) -> None:
        page.pop_dialog()
        detail_holder["dialog"] = None
        detail_holder["description"] = None
        page.update()

    def _set_description_text(value: str, request_id: int) -> None:
        if detail_holder.get("request_id") != request_id:
            return
        description = detail_holder.get("description")
        if not isinstance(description, ft.Text):
            return
        description.value = value
        description.update()
        page.update()

    def _show_detail_dialog(video: YouTubeVideoSummary, thumb_src: str) -> int:
        if detail_holder.get("dialog") is not None:
            page.pop_dialog()
        request_id = int(detail_holder.get("request_id") or 0) + 1
        detail_holder["request_id"] = request_id

        description_text = ft.Text(
            "Loading description...",
            color=ft.Colors.WHITE70,
            selectable=True,
        )
        detail_holder["description"] = description_text

        async def _practice(_: ft.ControlEvent) -> None:
            _close_detail_dialog()
            await _start_practice(video.webpage_url)

        content = ft.Container(
            width=560,
            content=ft.Column(
                [
                    ft.Image(
                        src=thumb_src,
                        height=220,
                        fit=ft.BoxFit.COVER,
                        border_radius=8,
                        error_content=ft.Container(
                            height=220,
                            bgcolor="#333333",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.VIDEO_LIBRARY, size=48, color=ft.Colors.WHITE54),
                        ),
                    ),
                    ft.Text(video.title, size=18, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ft.Text(
                        f"{format_upload_date(video.upload_date)}  {video.duration_text}".strip(),
                        size=12,
                        color=ft.Colors.WHITE54,
                    ),
                    ft.Container(
                        content=ft.Column([description_text], scroll=ft.ScrollMode.AUTO),
                        height=180,
                        padding=8,
                        border=ft.border.all(1, "#333333"),
                        border_radius=8,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
        )
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Video Details"),
            content=content,
            actions=[
                ft.TextButton("Cancel", on_click=_close_detail_dialog),
                ft.ElevatedButton(
                    "Practice",
                    bgcolor=ft.Colors.RED_700,
                    color=ft.Colors.WHITE,
                    on_click=lambda e: page.run_task(_practice, e),
                ),
            ],
        )
        detail_holder["dialog"] = dialog
        page.show_dialog(dialog)
        return request_id

    def _render_browse() -> None:
        page.controls.clear()
        page.on_keyboard_event = None
        browse_body = ft.Row(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Subscriptions", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE70),
                            channel_list,
                        ],
                        expand=True,
                        spacing=8,
                    ),
                    width=_CHANNEL_WIDTH,
                    bgcolor="#181818",
                    border_radius=10,
                    padding=8,
                ),
                ft.Container(
                    content=video_panel,
                    expand=True,
                    bgcolor="#181818",
                    border_radius=10,
                    padding=8,
                ),
            ],
            expand=True,
            spacing=12,
        )
        page.add(ft.Column([header, browse_body], expand=True, spacing=12))
        page.update()

    async def _prefetch_video_thumbnails(videos: list[YouTubeVideoSummary], page_number: int) -> None:
        thumb_map = state.get("thumbnail_src")
        if not isinstance(thumb_map, dict):
            return
        for video in videos:
            if int(state.get("page") or 0) != page_number:
                return
            src = await asyncio.to_thread(
                service.get_thumbnail_src,
                video.id,
                video.thumbnail_url,
            )
            if int(state.get("page") or 0) != page_number:
                return
            thumb_map[video.id] = src if src else ""
            _render_videos()
            page.update()

    def _apply_page_result(
        videos: list[YouTubeVideoSummary],
        total: int | None,
        *,
        page_size: int,
    ) -> None:
        state["videos"] = videos
        if isinstance(total, int) and total > 0:
            state["total_videos"] = total
        state["has_next_page"] = len(videos) >= page_size

    async def _load_page(page_number: int, *, fetch_total: bool = False) -> None:
        selected = state.get("selected_channel")
        if not isinstance(selected, SubscribedChannel):
            state["videos"] = []
            state["thumbnail_src"] = {}
            state["total_videos"] = None
            state["has_next_page"] = False
            state["page"] = 1
            _set_loading(False)
            _render_videos()
            page.update()
            return

        page_size = int(state.get("page_size") or DEFAULT_PAGE_SIZE)
        state["page"] = max(1, page_number)
        _set_loading(True, f"Loading page {state['page']} from {selected.name}...")
        page.update()
        try:
            if fetch_total:
                page_task = asyncio.to_thread(
                    service.load_channel_videos_page,
                    selected,
                    int(state["page"]),
                    page_size,
                )
                count_task = asyncio.to_thread(service.load_channel_video_count, selected)
                (videos, total), count = await asyncio.gather(page_task, count_task)
                if not isinstance(total, int) or total <= 0:
                    total = count
            else:
                videos, total = await asyncio.to_thread(
                    service.load_channel_videos_page,
                    selected,
                    int(state["page"]),
                    page_size,
                )
            _apply_page_result(videos, total, page_size=page_size)
            state["thumbnail_src"] = {}
            current_page = int(state["page"])
        except Exception as exc:
            state["videos"] = []
            state["has_next_page"] = False
            state["thumbnail_src"] = {}
            current_page = 0
            _snack(page, str(exc), ft.Colors.RED_700)
        finally:
            _set_loading(False)
            _render_videos()
            page.update()

        videos_to_prefetch = state.get("videos")
        if current_page > 0 and isinstance(videos_to_prefetch, list) and videos_to_prefetch:
            await _prefetch_video_thumbnails(
                [video for video in videos_to_prefetch if isinstance(video, YouTubeVideoSummary)],
                current_page,
            )

    async def _load_videos_for_selected() -> None:
        state["page"] = 1
        await _load_page(1, fetch_total=True)

    async def _select_channel(channel: SubscribedChannel) -> None:
        state["selected_channel"] = channel
        state["thumbnail_src"] = {}
        state["total_videos"] = None
        state["has_next_page"] = False
        _render_channels()
        await _load_videos_for_selected()

    async def _go_prev_page(_: ft.ControlEvent) -> None:
        current_page = int(state.get("page") or 1)
        if current_page > 1:
            await _load_page(current_page - 1)

    async def _go_next_page(_: ft.ControlEvent) -> None:
        if _can_go_next_page():
            current_page = int(state.get("page") or 1)
            await _load_page(current_page + 1)

    prev_page_btn.on_click = lambda e: page.run_task(_go_prev_page, e)
    next_page_btn.on_click = lambda e: page.run_task(_go_next_page, e)

    async def _open_detail(video: YouTubeVideoSummary) -> None:
        state["selected_video"] = video
        thumb_src = _thumbnail_src(video, allow_remote_fallback=True) or ""
        request_id = _show_detail_dialog(video, thumb_src)
        try:
            detail = await asyncio.wait_for(
                asyncio.to_thread(service.load_video_detail, video),
                timeout=60,
            )
            state["selected_video"] = detail
            _set_description_text(detail.description or "No description.", request_id)
        except asyncio.TimeoutError:
            _set_description_text(
                "Loading timed out. You can still start practice.",
                request_id,
            )
            _snack(page, "Description loading timed out.", ft.Colors.ORANGE_700)
        except Exception as exc:
            _set_description_text(
                "Description unavailable. You can still start practice.",
                request_id,
            )
            _snack(page, str(exc), ft.Colors.ORANGE_700)

    async def _start_practice(video_url: str) -> None:
        page.controls.clear()
        page.update()
        build_video_player_page(page, youtube_page_url=video_url, auto_transcribe=True)

    async def _prefetch_channel_icons() -> None:
        channels = state.get("channels")
        if not isinstance(channels, list):
            return
        icon_map = state.get("channel_icon_src")
        if not isinstance(icon_map, dict):
            return
        for channel in channels:
            if not isinstance(channel, SubscribedChannel):
                continue
            src = await asyncio.to_thread(service.get_channel_icon_src, channel)
            icon_map[channel.id] = src if src else ""
            _render_channels()
            page.update()

    _render_channels()
    _render_browse()
    page.run_task(_prefetch_channel_icons)
    page.run_task(_load_videos_for_selected)

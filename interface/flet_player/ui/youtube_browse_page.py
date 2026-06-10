"""YouTube-style channel browse UI."""

from __future__ import annotations

import asyncio
from typing import Optional

import flet as ft

from ..application.youtube_browse_service import DEFAULT_PAGE_SIZE, YouTubeBrowseService
from ..infrastructure.error_log import print_error
from ..infrastructure.proxy_settings import read_cookies_text
from ..domain.youtube_models import (
    SubscribedChannel,
    YouTubeVideoSummary,
    format_upload_date,
)
_CHANNEL_WIDTH = 300
_CHANNEL_ICON_SIZE = 36
_THUMB_WIDTH = 220
_THUMB_HEIGHT = 124
_DETAIL_DIALOG_WIDTH = 680
_DETAIL_DIALOG_HEIGHT = 500
_DETAIL_THUMB_HEIGHT = 180
_DETAIL_DESCRIPTION_HEIGHT = 180


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
        "load_request_id": 0,
        "videos_loading": False,
    }
    channel_dialog_holder: dict[str, object] = {"dialog": None}

    settings_holder: dict[str, object] = {"dialog": None, "proxy_field": None, "cookies_field": None}

    def _proxy_field_value() -> str:
        settings = service.proxy_settings
        if not settings.enabled:
            return ""
        return (settings.proxy_url or "").strip()

    def _close_settings_dialog() -> None:
        if settings_holder.get("dialog") is not None:
            page.pop_dialog()
        settings_holder["dialog"] = None
        settings_holder["proxy_field"] = None
        settings_holder["cookies_field"] = None

    def _open_settings_dialog(_event: ft.ControlEvent) -> None:
        if settings_holder.get("dialog") is not None:
            return
        proxy_field = ft.TextField(
            label="Proxy URL (optional)",
            value=_proxy_field_value(),
            hint_text="http://127.0.0.1:7890",
            width=520,
        )
        cookies_field = ft.TextField(
            label="Cookies (optional, Netscape format)",
            value=read_cookies_text(),
            multiline=True,
            min_lines=10,
            max_lines=14,
            width=520,
        )
        settings_holder["proxy_field"] = proxy_field
        settings_holder["cookies_field"] = cookies_field

        def _save_settings(_e: ft.ControlEvent) -> None:
            proxy_value = proxy_field.value if isinstance(proxy_field.value, str) else ""
            cookies_value = cookies_field.value if isinstance(cookies_field.value, str) else ""
            try:
                service.save_network_settings(proxy_url=proxy_value, cookies_text=cookies_value)
            except Exception as exc:
                print_error("_save_settings", exc)
                _snack(page, f"Failed to save settings: {exc}", ft.Colors.RED_700)
                return
            _close_settings_dialog()
            _snack(page, "Settings saved", "#2E7D32")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Network Settings"),
            content=ft.Container(
                width=540,
                content=ft.Column(
                    [
                        ft.Text(
                            "Leave fields empty to disable proxy or cookies.",
                            size=12,
                            color=ft.Colors.WHITE70,
                        ),
                        proxy_field,
                        cookies_field,
                    ],
                    spacing=12,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: _close_settings_dialog()),
                ft.ElevatedButton("Save", on_click=_save_settings),
            ],
        )
        settings_holder["dialog"] = dialog
        page.show_dialog(dialog)
        page.update()

    header = ft.Row(
        [
            ft.Text("What are we practising today?", size=20, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
            ft.IconButton(
                icon=ft.Icons.SETTINGS,
                tooltip="Settings",
                icon_color=ft.Colors.WHITE70,
                on_click=_open_settings_dialog,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
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
        state["videos_loading"] = visible
        loading_indicator.visible = visible
        loading_text.value = message
        loading_text.visible = visible

    def _invalidate_video_load() -> None:
        state["load_request_id"] = int(state.get("load_request_id") or 0) + 1

    def _reset_empty_subscription_view() -> None:
        _invalidate_video_load()
        state["videos"] = []
        state["thumbnail_src"] = {}
        state["total_videos"] = None
        state["has_next_page"] = False
        state["page"] = 1
        _set_loading(False)
        _render_channels()
        _render_videos()

    def _channel_items() -> list[SubscribedChannel]:
        channels = state.get("channels")
        if not isinstance(channels, list):
            return []
        return [channel for channel in channels if isinstance(channel, SubscribedChannel)]

    def _has_subscriptions() -> bool:
        return bool(_channel_items())

    def _selected_channel() -> SubscribedChannel | None:
        selected = state.get("selected_channel")
        return selected if isinstance(selected, SubscribedChannel) else None

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

    def _reload_channels_state(*, select_channel: SubscribedChannel | None = None) -> None:
        channels = service.load_channels()
        state["channels"] = channels
        if select_channel is not None:
            state["selected_channel"] = select_channel
        elif isinstance(state.get("selected_channel"), SubscribedChannel):
            selected_id = state["selected_channel"].id
            matched = next((channel for channel in channels if channel.id == selected_id), None)
            state["selected_channel"] = matched or (channels[0] if channels else None)
        else:
            state["selected_channel"] = channels[0] if channels else None

    def _close_channel_dialog() -> None:
        if channel_dialog_holder.get("dialog") is not None:
            page.pop_dialog()
        channel_dialog_holder["dialog"] = None

    def _open_add_channel_dialog(_event: ft.ControlEvent) -> None:
        if channel_dialog_holder.get("dialog") is not None:
            return
        url_field = ft.TextField(
            label="Channel URL",
            hint_text="https://www.youtube.com/@handle/videos",
            width=420,
        )
        name_field = ft.TextField(
            label="Display name (optional)",
            width=420,
        )

        async def _save_channel(_e: ft.ControlEvent) -> None:
            url_value = url_field.value if isinstance(url_field.value, str) else ""
            name_value = name_field.value if isinstance(name_field.value, str) else ""
            try:
                channel = service.add_channel(url_value, name_value or None)
            except Exception as exc:
                _snack(page, str(exc), ft.Colors.RED_700)
                return
            _close_channel_dialog()
            _reload_channels_state(select_channel=channel)
            state["load_request_id"] = int(state.get("load_request_id") or 0) + 1
            state["videos"] = []
            state["thumbnail_src"] = {}
            state["total_videos"] = None
            state["has_next_page"] = False
            _render_channels()
            _render_videos()
            page.update()
            await _select_channel(channel)
            page.run_task(_prefetch_single_channel_icon, channel)
            _snack(page, f"Subscribed to {channel.name}", "#2E7D32")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Subscription"),
            content=ft.Column([url_field, name_field], spacing=12, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: _close_channel_dialog()),
                ft.ElevatedButton("Add", on_click=lambda e: page.run_task(_save_channel, e)),
            ],
        )
        channel_dialog_holder["dialog"] = dialog
        page.show_dialog(dialog)
        page.update()

    def _open_add_from_manage(_event: ft.ControlEvent) -> None:
        _close_channel_dialog()
        _open_add_channel_dialog(_event)

    def _open_manage_channels_dialog(_event: ft.ControlEvent) -> None:
        if channel_dialog_holder.get("dialog") is not None:
            return
        manage_list = ft.ListView(height=300, spacing=6, padding=4)

        def _render_manage_list() -> None:
            manage_list.controls.clear()
            channels = state.get("channels")
            if not isinstance(channels, list) or not channels:
                manage_list.controls.append(ft.Text("No subscriptions yet.", color=ft.Colors.WHITE54))
                return
            for channel in channels:
                if not isinstance(channel, SubscribedChannel):
                    continue

                async def _delete_channel(_e: ft.ControlEvent, ch: SubscribedChannel = channel) -> None:
                    service.remove_channel(ch.id)
                    _reload_channels_state()
                    _render_manage_list()
                    manage_list.update()
                    selected = _selected_channel()
                    if selected is None:
                        _reset_empty_subscription_view()
                        page.update()
                    else:
                        _invalidate_video_load()
                        state["videos"] = []
                        state["thumbnail_src"] = {}
                        state["total_videos"] = None
                        state["has_next_page"] = False
                        state["page"] = 1
                        _set_loading(True, f"Loading videos from {selected.name}...")
                        _render_channels()
                        _render_videos()
                        page.update()
                        await _load_videos_for_selected()
                    _snack(page, f"Removed {ch.name}", ft.Colors.ORANGE_700)

                manage_list.controls.append(
                    ft.Row(
                        [
                            ft.Text(channel.name, expand=True, color=ft.Colors.WHITE),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                tooltip="Remove subscription",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda e, ch=channel: page.run_task(_delete_channel, e),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

        _render_manage_list()
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Manage Subscriptions"),
            content=ft.Container(width=460, content=manage_list),
            actions=[
                ft.ElevatedButton("Add", on_click=_open_add_from_manage),
                ft.TextButton("Close", on_click=lambda _e: _close_channel_dialog()),
            ],
        )
        channel_dialog_holder["dialog"] = dialog
        page.show_dialog(dialog)
        page.update()

    subscriptions_header = ft.Row(
        [
            ft.Text("Subscriptions", size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE70, expand=True),
            ft.TextButton("Manage", on_click=_open_manage_channels_dialog),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def _render_channels() -> None:
        channel_list.controls.clear()
        channels = _channel_items()
        if not channels:
            channel_list.controls.append(
                ft.Text(
                    "No subscriptions yet.\nOpen Manage to add channels.",
                    color=ft.Colors.WHITE54,
                    size=13,
                )
            )
            return
        selected = _selected_channel()
        for channel in channels:
            is_selected = selected is not None and selected.id == channel.id
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
        if not _has_subscriptions() or _selected_channel() is None:
            page_info.value = ""
            prev_page_btn.disabled = True
            next_page_btn.disabled = True
            return
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
        if not _has_subscriptions() or _selected_channel() is None:
            video_list.controls.extend(
                [
                    ft.Text("No subscriptions yet.", color=ft.Colors.WHITE54, size=15),
                    ft.Text(
                        "Open Manage to add your first channel.",
                        color=ft.Colors.WHITE54,
                        size=13,
                    ),
                ]
            )
            _update_pagination_controls()
            return
        if state.get("videos_loading"):
            _update_pagination_controls()
            return
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
    download_holder: dict[str, object] = {
        "dialog": None,
        "progress_bar": None,
        "status_text": None,
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
            width=float("inf"),
        )
        detail_holder["description"] = description_text

        async def _practice(_: ft.ControlEvent) -> None:
            _close_detail_dialog()
            await asyncio.sleep(0)
            await _start_practice(video.webpage_url, video.title, video.id)

        content = ft.Container(
            width=_DETAIL_DIALOG_WIDTH,
            height=_DETAIL_DIALOG_HEIGHT,
            content=ft.Column(
                [
                    ft.Image(
                        src=thumb_src,
                        width=_DETAIL_DIALOG_WIDTH,
                        height=_DETAIL_THUMB_HEIGHT,
                        fit=ft.BoxFit.COVER,
                        border_radius=8,
                        error_content=ft.Container(
                            width=_DETAIL_DIALOG_WIDTH,
                            height=_DETAIL_THUMB_HEIGHT,
                            bgcolor="#333333",
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.VIDEO_LIBRARY, size=48, color=ft.Colors.WHITE54),
                        ),
                    ),
                    ft.Text(video.title, size=18, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE, max_lines=2),
                    ft.Text(
                        f"{format_upload_date(video.upload_date)}  {video.duration_text}".strip(),
                        size=12,
                        color=ft.Colors.WHITE54,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [description_text],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                        height=_DETAIL_DESCRIPTION_HEIGHT,
                        width=_DETAIL_DIALOG_WIDTH,
                        padding=ft.padding.symmetric(vertical=8),
                        border=ft.border.all(1, "#333333"),
                        border_radius=8,
                    ),
                ],
                spacing=10,
                width=_DETAIL_DIALOG_WIDTH,
                height=_DETAIL_DIALOG_HEIGHT,
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
                            subscriptions_header,
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

    async def _prefetch_video_thumbnails(
        videos: list[YouTubeVideoSummary],
        page_number: int,
        *,
        channel_id: str,
        load_request_id: int,
    ) -> None:
        thumb_map = state.get("thumbnail_src")
        if not isinstance(thumb_map, dict):
            return
        for video in videos:
            if not _is_active_channel_load(channel_id, page_number, load_request_id):
                return
            src = await asyncio.to_thread(
                service.get_thumbnail_src,
                video.id,
                video.thumbnail_url,
            )
            if not _is_active_channel_load(channel_id, page_number, load_request_id):
                return
            thumb_map[video.id] = src if src else ""
            _render_videos()
            page.update()

    def _is_active_channel_load(channel_id: str, page_number: int, load_request_id: int) -> bool:
        if int(state.get("load_request_id") or 0) != load_request_id:
            return False
        selected = state.get("selected_channel")
        if not isinstance(selected, SubscribedChannel) or selected.id != channel_id:
            return False
        return int(state.get("page") or 0) == page_number

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
        selected = _selected_channel()
        if selected is None:
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
        page_num = max(1, page_number)
        channel_id = selected.id
        load_request_id = int(state.get("load_request_id") or 0) + 1
        state["load_request_id"] = load_request_id
        state["page"] = page_num
        _set_loading(True, f"Loading page {page_num} from {selected.name}...")
        page.update()
        current_page = 0
        try:
            if fetch_total:
                page_task = asyncio.to_thread(
                    service.load_channel_videos_page,
                    selected,
                    page_num,
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
                    page_num,
                    page_size,
                )
            if not _is_active_channel_load(channel_id, page_num, load_request_id):
                return
            _apply_page_result(videos, total, page_size=page_size)
            state["thumbnail_src"] = {}
            current_page = page_num
        except Exception as exc:
            if not _is_active_channel_load(channel_id, page_num, load_request_id):
                return
            print_error("_load_page", exc)
            state["videos"] = []
            state["has_next_page"] = False
            state["thumbnail_src"] = {}
            _snack(page, str(exc), ft.Colors.RED_700)
        finally:
            if _is_active_channel_load(channel_id, page_num, load_request_id):
                _set_loading(False)
                _render_videos()
                page.update()

        videos_to_prefetch = state.get("videos")
        if current_page > 0 and isinstance(videos_to_prefetch, list) and videos_to_prefetch:
            await _prefetch_video_thumbnails(
                [video for video in videos_to_prefetch if isinstance(video, YouTubeVideoSummary)],
                current_page,
                channel_id=channel_id,
                load_request_id=load_request_id,
            )

    async def _load_videos_for_selected() -> None:
        state["page"] = 1
        await _load_page(1, fetch_total=True)

    async def _select_channel(channel: SubscribedChannel) -> None:
        _invalidate_video_load()
        state["selected_channel"] = channel
        state["videos"] = []
        state["thumbnail_src"] = {}
        state["total_videos"] = None
        state["has_next_page"] = False
        state["page"] = 1
        _set_loading(True, f"Loading videos from {channel.name}...")
        _render_channels()
        _render_videos()
        page.update()
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
            print_error("_open_detail", "description loading timed out")
            _set_description_text(
                "Loading timed out. You can still start practice.",
                request_id,
            )
            _snack(page, "Description loading timed out.", ft.Colors.ORANGE_700)
        except Exception as exc:
            print_error("_open_detail", exc)
            _set_description_text(
                "Description unavailable. You can still start practice.",
                request_id,
            )
            _snack(page, str(exc), ft.Colors.ORANGE_700)

    def _close_download_dialog() -> None:
        if download_holder.get("dialog") is not None:
            page.pop_dialog()
        download_holder["dialog"] = None
        download_holder["progress_bar"] = None
        download_holder["status_text"] = None
        page.update()

    def _show_download_dialog(video_title: str) -> int:
        if download_holder.get("dialog") is not None:
            page.pop_dialog()
        request_id = int(download_holder.get("request_id") or 0) + 1
        download_holder["request_id"] = request_id

        progress_bar = ft.ProgressBar(value=0, width=420)
        status_text = ft.Text("Preparing download...", color=ft.Colors.WHITE70)
        download_holder["progress_bar"] = progress_bar
        download_holder["status_text"] = status_text

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Downloading Video"),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Text(video_title, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE, max_lines=2),
                        progress_bar,
                        status_text,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
        )
        download_holder["dialog"] = dialog
        page.show_dialog(dialog)
        page.update()
        return request_id

    async def _set_download_progress(request_id: int, fraction: float, message: str) -> None:
        if download_holder.get("request_id") != request_id:
            return
        progress_bar = download_holder.get("progress_bar")
        status_text = download_holder.get("status_text")
        updated = False
        if isinstance(progress_bar, ft.ProgressBar):
            progress_bar.value = max(0.0, min(1.0, fraction))
            progress_bar.update()
            updated = True
        if isinstance(status_text, ft.Text):
            status_text.value = message
            status_text.update()
            updated = True
        if not updated:
            page.update()

    async def _start_practice(video_url: str, video_title: str, video_id: str) -> None:
        request_id = _show_download_dialog(video_title)
        await asyncio.sleep(0)
        loop = asyncio.get_running_loop()
        progress_queue: asyncio.Queue[tuple[float, str] | None] = asyncio.Queue()

        def _enqueue_progress(item: tuple[float, str] | None) -> None:
            try:
                progress_queue.put_nowait(item)
            except Exception as exc:
                print_error("_enqueue_progress", exc)

        def _on_progress(fraction: float, message: str) -> None:
            loop.call_soon_threadsafe(_enqueue_progress, (fraction, message))

        async def _consume_download_progress() -> None:
            while True:
                item = await progress_queue.get()
                if item is None:
                    return
                fraction, message = item
                await _set_download_progress(request_id, fraction, message)

        progress_task = asyncio.create_task(_consume_download_progress())
        try:
            local_path = await asyncio.wait_for(
                asyncio.to_thread(
                    service.download_for_practice,
                    video_url,
                    video_id=video_id,
                    on_progress=_on_progress,
                ),
                timeout=900,
            )
            await _set_download_progress(request_id, 1.0, "Download completed")
            _close_download_dialog()
            _snack(page, f"Saved to {local_path}", "#2E7D32")
        except asyncio.TimeoutError:
            _close_download_dialog()
            _snack(page, "Download timed out after 15 minutes.", ft.Colors.RED_700)
        except Exception as exc:
            _close_download_dialog()
            _snack(page, str(exc), ft.Colors.RED_700)
        finally:
            loop.call_soon_threadsafe(_enqueue_progress, None)
            await progress_task

    async def _prefetch_single_channel_icon(channel: SubscribedChannel) -> None:
        icon_map = state.get("channel_icon_src")
        if not isinstance(icon_map, dict):
            return
        src = await asyncio.to_thread(service.get_channel_icon_src, channel)
        icon_map[channel.id] = src if src else ""
        _render_channels()
        page.update()

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
    if _has_subscriptions():
        page.run_task(_prefetch_channel_icons)
        page.run_task(_load_videos_for_selected)
    else:
        _set_loading(False)
        _render_videos()
        page.update()

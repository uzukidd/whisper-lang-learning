"""Flet video player modules with lazy exports."""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "AsrProvider": (".application.asr", "AsrProvider"),
    "AsrService": (".application.asr", "AsrService"),
    "CaptionRepository": (".infrastructure.caption_repository", "CaptionRepository"),
    "CaptionSegment": (".domain.caption_models", "CaptionSegment"),
    "CaptionSession": (".domain.caption_session", "CaptionSession"),
    "FletVideoBackend": (".infrastructure.flet_video_backend", "FletVideoBackend"),
    "NormalizedExactSentenceScorer": (".domain.scoring", "NormalizedExactSentenceScorer"),
    "PlayerViewHooks": (".application.presenter", "PlayerViewHooks"),
    "PlaybackPort": (".ports.playback_port", "PlaybackPort"),
    "PracticeOutcome": (".application.practice_service", "PracticeOutcome"),
    "PracticeService": (".application.practice_service", "PracticeService"),
    "SentenceScore": (".domain.scoring", "SentenceScore"),
    "SentenceScorer": (".domain.scoring", "SentenceScorer"),
    "VideoPlayerPresenter": (".application.presenter", "VideoPlayerPresenter"),
    "WhisperAsrProvider": (".infrastructure.whisper_provider", "WhisperAsrProvider"),
    "build_result_log": (".infrastructure.caption_pickle_io", "build_result_log"),
    "YouTubeBrowseService": (".application.youtube_browse_service", "YouTubeBrowseService"),
    "build_video_player_page": (".ui.flet_video_player_page", "build_video_player_page"),
    "build_youtube_browse_page": (".ui.youtube_browse_page", "build_youtube_browse_page"),
    "format_hms_from_ms": (".infrastructure.time_format", "format_hms_from_ms"),
    "format_hms_from_us": (".infrastructure.time_format", "format_hms_from_us"),
    "load_caption_pickle": (".infrastructure.caption_pickle_io", "load_caption_pickle"),
    "save_caption_pickle": (".infrastructure.caption_pickle_io", "save_caption_pickle"),
    "save_result_log": (".infrastructure.caption_pickle_io", "save_result_log"),
}

__all__ = [
    "AsrProvider",
    "AsrService",
    "CaptionRepository",
    "CaptionSegment",
    "CaptionSession",
    "FletVideoBackend",
    "NormalizedExactSentenceScorer",
    "PlayerViewHooks",
    "PlaybackPort",
    "PracticeOutcome",
    "PracticeService",
    "SentenceScore",
    "SentenceScorer",
    "VideoPlayerPresenter",
    "WhisperAsrProvider",
    "YouTubeBrowseService",
    "build_result_log",
    "build_video_player_page",
    "build_youtube_browse_page",
    "format_hms_from_ms",
    "format_hms_from_us",
    "load_caption_pickle",
    "save_caption_pickle",
    "save_result_log",
]


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

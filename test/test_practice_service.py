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
_ensure_package("interface.flet_player.application", _PACKAGE_ROOT / "application")
_load_module("interface.flet_player.domain.caption_models", "interface/flet_player/domain/caption_models.py")
caption_session = _load_module("interface.flet_player.domain.caption_session", "interface/flet_player/domain/caption_session.py")
scoring = _load_module("interface.flet_player.domain.scoring", "interface/flet_player/domain/scoring.py")
practice_service_module = _load_module(
    "interface.flet_player.application.practice_service",
    "interface/flet_player/application/practice_service.py",
)

CaptionSession = caption_session.CaptionSession
CaptionSegment = sys.modules["interface.flet_player.domain.caption_models"].CaptionSegment
NormalizedExactSentenceScorer = scoring.NormalizedExactSentenceScorer
PracticeService = practice_service_module.PracticeService


class PracticeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = CaptionSession()
        self.session.load_caption_data(
            [CaptionSegment(id=1, start=0.0, end=1.0, text="Hello, WORLD!", language="en")]
        )
        self.service = PracticeService(NormalizedExactSentenceScorer())

    def test_empty_input_requests_replay_without_feedback(self) -> None:
        outcome = self.service.submit_sentence(self.session, "")

        self.assertEqual("replay", outcome.action)
        self.assertFalse(outcome.show_feedback)
        self.assertFalse(outcome.pending_retry_clear)

    def test_wrong_input_shows_feedback_and_sets_pending_clear(self) -> None:
        outcome = self.service.submit_sentence(self.session, "hello there")

        self.assertEqual("show_feedback", outcome.action)
        self.assertTrue(outcome.show_feedback)
        self.assertTrue(outcome.clear_input)
        self.assertTrue(outcome.pending_retry_clear)
        self.assertEqual([True, False], [item[1] for item in outcome.feedback])

    def test_second_submit_clears_feedback_and_replays(self) -> None:
        self.service.submit_sentence(self.session, "hello there")

        outcome = self.service.submit_sentence(self.session, "")

        self.assertEqual("clear_retry", outcome.action)
        self.assertFalse(outcome.show_feedback)
        self.assertFalse(outcome.pending_retry_clear)

    def test_matching_input_requests_advance(self) -> None:
        outcome = self.service.submit_sentence(self.session, "hello world")

        self.assertEqual("advance", outcome.action)
        self.assertTrue(outcome.show_feedback)
        self.assertTrue(outcome.is_match)
        self.assertFalse(outcome.pending_retry_clear)


if __name__ == "__main__":
    unittest.main()

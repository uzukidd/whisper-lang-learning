import importlib.util
import sys
import unittest
from pathlib import Path


def _load_scoring_module():
    module_path = Path(__file__).resolve().parents[1] / "interface" / "flet_player" / "domain" / "scoring.py"
    spec = importlib.util.spec_from_file_location("test_scoring_module", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load scoring module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


NormalizedExactSentenceScorer = _load_scoring_module().NormalizedExactSentenceScorer


class NormalizedExactSentenceScorerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = NormalizedExactSentenceScorer()

    def test_ignores_case_and_punctuation(self) -> None:
        score = self.scorer.score("Hello, WORLD!", "hello world")

        self.assertTrue(score.is_match)
        self.assertEqual(["Hello,", "WORLD!"], [item.expected for item in score.word_matches])
        self.assertTrue(all(item.is_match for item in score.word_matches))

    def test_marks_missing_words_as_mismatch(self) -> None:
        score = self.scorer.score("hello brave world", "hello world")

        self.assertFalse(score.is_match)
        self.assertEqual([True, False, False], [item.is_match for item in score.word_matches])


if __name__ == "__main__":
    unittest.main()

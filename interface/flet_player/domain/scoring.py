"""Sentence scoring strategies for practice mode."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Protocol

_EXTRA_PUNCTUATION = "“”‘’，。！？；：、…"


@dataclass(frozen=True)
class WordMatch:
    expected: str
    actual: str
    is_match: bool


@dataclass(frozen=True)
class SentenceScore:
    word_matches: list[WordMatch]
    is_match: bool


class SentenceScorer(Protocol):
    def score(self, expected_sentence: str, actual_sentence: str) -> SentenceScore:
        ...


class NormalizedExactSentenceScorer:
    def score(self, expected_sentence: str, actual_sentence: str) -> SentenceScore:
        expected_tokens = [token for token in expected_sentence.split() if token]
        actual_tokens = [token for token in actual_sentence.split() if token]
        word_matches: list[WordMatch] = []
        is_match = len(expected_tokens) == len(actual_tokens)
        for index, expected in enumerate(expected_tokens):
            actual = actual_tokens[index] if index < len(actual_tokens) else ""
            matched = bool(actual) and self._normalize_token(expected) == self._normalize_token(actual)
            word_matches.append(WordMatch(expected=expected, actual=actual, is_match=matched))
            if not matched:
                is_match = False
        return SentenceScore(word_matches=word_matches, is_match=is_match)

    @staticmethod
    def _normalize_token(token: str) -> str:
        stripped = token.strip().strip(string.punctuation + _EXTRA_PUNCTUATION).lower()
        return re.sub(r"\s+", " ", stripped)

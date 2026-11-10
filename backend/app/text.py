"""Tokenisation shared by keyword search, the offline embedder and the offline agent."""
from __future__ import annotations

import re

STOPWORDS = frozenset((
    "a", "about", "above", "after", "again", "all", "am", "an", "and", "any", "are", "as", "at", "be", "because",
    "been", "before", "being", "below", "between", "both", "but", "by", "can", "could", "did", "do", "does",
    "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has", "have", "having", "he",
    "her", "here", "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "our", "ours", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "would", "you", "your", "yours",
))
_WORD = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    words = _WORD.findall(text.lower())
    return words if keep_stopwords else [w for w in words if w not in STOPWORDS]


def stem(word: str) -> str:
    """A deliberately small suffix stripper: enough for 'policies' to match 'policy' and 'days' to match 'day'."""
    for suffix, replacement in (("ies", "y"), ("sses", "ss"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: len(word) - len(suffix)] + replacement
    return word


def terms(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)]


_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")


def sentences(text: str) -> list[str]:
    """Sentences, with line breaks as boundaries too: headings, list items and table rows have no full stop."""
    result: list[str] = []
    for line in text.replace("\r", "").split("\n"):
        result.extend(s.strip() for s in _SENTENCE.split(line) if s.strip())
    return result

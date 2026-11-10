"""Okapi BM25 keyword index. Catches exact terms (policy names, codes, numbers) that embeddings can blur."""
from __future__ import annotations

import math
import threading
from collections import Counter

from app.text import terms


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self._docs: dict[str, Counter[str]] = {}
        self._lengths: dict[str, int] = {}
        self._df: Counter[str] = Counter()
        self._total_length = 0
        self._lock = threading.Lock()

    def add(self, items: list[tuple[str, str]]) -> None:
        with self._lock:
            for chunk_id, text in items:
                self._remove(chunk_id)
                words = terms(text)
                counts = Counter(words)
                self._docs[chunk_id] = counts
                self._lengths[chunk_id] = len(words)
                self._total_length += len(words)
                self._df.update(counts.keys())

    def delete(self, ids: list[str]) -> None:
        with self._lock:
            for chunk_id in ids:
                self._remove(chunk_id)

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        query_terms = set(terms(query))
        with self._lock:
            n = len(self._docs)
            if not n or not query_terms:
                return []
            average = self._total_length / n or 1
            scores: dict[str, float] = {}
            for term in query_terms:
                df = self._df.get(term, 0)
                if not df:
                    continue
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                for chunk_id, counts in self._docs.items():
                    tf = counts.get(term, 0)
                    if tf:
                        norm = tf + self.k1 * (1 - self.b + self.b * self._lengths[chunk_id] / average)
                        scores[chunk_id] = scores.get(chunk_id, 0.0) + idf * tf * (self.k1 + 1) / norm
        return sorted(scores.items(), key=lambda item: -item[1])[:k]

    def __len__(self) -> int:
        return len(self._docs)

    def _remove(self, chunk_id: str) -> None:
        counts = self._docs.pop(chunk_id, None)
        if counts is None:
            return
        self._total_length -= self._lengths.pop(chunk_id)
        self._df.subtract(counts.keys())
        for term in [t for t in counts if self._df[t] <= 0]:
            del self._df[term]

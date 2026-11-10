from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np


class FaissVectorStore:
    """FAISS inner-product index (cosine on normalised vectors) with string ids mapped to int64 FAISS ids."""

    name = "faiss"

    def __init__(self, directory: Path):
        import faiss

        self._faiss = faiss
        self._dir = directory
        self._lock = threading.Lock()
        self._index = None
        self._to_int: dict[str, int] = {}
        self._next = 0
        index_file, ids_file = directory / "index.faiss", directory / "ids.json"
        if index_file.exists() and ids_file.exists():
            self._index = faiss.read_index(str(index_file))
            saved = json.loads(ids_file.read_text())
            self._to_int, self._next = saved["ids"], saved["next"]
        self._to_str = {v: k for k, v in self._to_int.items()}

    def add(self, ids: list[str], vectors: np.ndarray) -> None:
        if not ids:
            return
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        with self._lock:
            if self._index is None:
                self._index = self._faiss.IndexIDMap2(self._faiss.IndexFlatIP(vectors.shape[1]))
            self._remove(ids)
            numbers = np.arange(self._next, self._next + len(ids), dtype=np.int64)
            self._next += len(ids)
            self._index.add_with_ids(vectors, numbers)
            for chunk_id, number in zip(ids, numbers.tolist(), strict=True):
                self._to_int[chunk_id] = number
                self._to_str[number] = chunk_id
            self._save()

    def delete(self, ids: list[str]) -> None:
        with self._lock:
            self._remove(ids)
            self._save()

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        with self._lock:
            if self._index is None or self._index.ntotal == 0:
                return []
            query = np.ascontiguousarray(np.asarray(vector, dtype=np.float32)[None, :])
            scores, numbers = self._index.search(query, min(k, self._index.ntotal))
            return [(self._to_str[n], float(s)) for s, n in zip(scores[0], numbers[0], strict=True) if n != -1]

    def count(self) -> int:
        return 0 if self._index is None else int(self._index.ntotal)

    def _remove(self, ids: list[str]) -> None:
        numbers = [self._to_int.pop(i) for i in ids if i in self._to_int]
        if numbers and self._index is not None:
            self._index.remove_ids(np.array(numbers, dtype=np.int64))
            for number in numbers:
                self._to_str.pop(number, None)

    def _save(self) -> None:
        if self._index is None:
            return
        self._dir.mkdir(parents=True, exist_ok=True)
        self._faiss.write_index(self._index, str(self._dir / "index.faiss"))
        (self._dir / "ids.json").write_text(json.dumps({"ids": self._to_int, "next": self._next}))

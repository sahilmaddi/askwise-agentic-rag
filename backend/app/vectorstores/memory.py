from __future__ import annotations

import threading
from pathlib import Path

import numpy as np


class MemoryVectorStore:
    """Exact cosine search with NumPy, saved to a .npz file. Plenty for a few hundred thousand chunks."""

    name = "memory"

    def __init__(self, path: Path | None = None):
        self._path = path
        self._lock = threading.Lock()
        self._ids: list[str] = []
        self._matrix = np.zeros((0, 0), dtype=np.float32)
        if path and path.exists():
            saved = np.load(path, allow_pickle=False)
            self._ids = [str(i) for i in saved["ids"]]
            self._matrix = saved["vectors"].astype(np.float32)

    def add(self, ids: list[str], vectors: np.ndarray) -> None:
        if not ids:
            return
        with self._lock:
            self._remove(set(ids))
            vectors = np.asarray(vectors, dtype=np.float32)
            self._matrix = vectors if self._matrix.size == 0 else np.vstack([self._matrix, vectors])
            self._ids.extend(ids)
            self._save()

    def delete(self, ids: list[str]) -> None:
        with self._lock:
            self._remove(set(ids))
            self._save()

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        with self._lock:
            if not self._ids:
                return []
            scores = self._matrix @ np.asarray(vector, dtype=np.float32)
            top = np.argsort(-scores)[:k]
            return [(self._ids[i], float(scores[i])) for i in top]

    def count(self) -> int:
        return len(self._ids)

    def _remove(self, ids: set[str]) -> None:
        keep = [i for i, chunk_id in enumerate(self._ids) if chunk_id not in ids]
        if len(keep) != len(self._ids):
            self._ids = [self._ids[i] for i in keep]
            self._matrix = self._matrix[keep] if keep else np.zeros((0, 0), dtype=np.float32)

    def _save(self) -> None:
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp.npz")
            np.savez(tmp, ids=np.array(self._ids, dtype=str), vectors=self._matrix)
            tmp.replace(self._path)

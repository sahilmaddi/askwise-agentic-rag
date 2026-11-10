from __future__ import annotations

from typing import Protocol

import numpy as np


class VectorStore(Protocol):
    """Stores one normalised vector per chunk id. Chunk text lives in the registry, not here."""

    name: str

    def add(self, ids: list[str], vectors: np.ndarray) -> None: ...

    def delete(self, ids: list[str]) -> None: ...

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]: ...

    def count(self) -> int: ...

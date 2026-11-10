from __future__ import annotations

import numpy as np


class MilvusVectorStore:
    """Milvus (or Milvus Lite when MILVUS_URI is a local file path such as ./data/milvus.db)."""

    name = "milvus"

    def __init__(self, uri: str, collection: str):
        from pymilvus import MilvusClient

        self._client = MilvusClient(uri=uri)
        self._collection = collection

    def _ensure(self, dimension: int) -> None:
        if not self._client.has_collection(self._collection):
            self._client.create_collection(
                collection_name=self._collection, dimension=dimension, id_type="string", max_length=64,
                metric_type="COSINE",
            )

    def add(self, ids: list[str], vectors: np.ndarray) -> None:
        if not ids:
            return
        self._ensure(int(vectors.shape[1]))
        rows = [{"id": i, "vector": v.tolist()} for i, v in zip(ids, vectors, strict=True)]
        self._client.upsert(self._collection, rows)

    def delete(self, ids: list[str]) -> None:
        if ids and self._client.has_collection(self._collection):
            self._client.delete(self._collection, ids=ids)

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        if not self._client.has_collection(self._collection):
            return []
        hits = self._client.search(self._collection, data=[np.asarray(vector).tolist()], limit=k)[0]
        return [(str(hit["id"]), float(hit["distance"])) for hit in hits]

    def count(self) -> int:
        if not self._client.has_collection(self._collection):
            return 0
        return int(self._client.get_collection_stats(self._collection)["row_count"])

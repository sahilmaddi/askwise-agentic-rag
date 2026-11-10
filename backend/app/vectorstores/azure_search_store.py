from __future__ import annotations

import numpy as np


class AzureSearchVectorStore:
    """Azure AI Search vector index (HNSW, cosine). The index is created on first use."""

    name = "azure_search"

    def __init__(self, endpoint: str, key: str, index: str):
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
        from azure.search.documents.indexes import SearchIndexClient

        credential = AzureKeyCredential(key)
        self._indexes = SearchIndexClient(endpoint, credential)
        self._client = SearchClient(endpoint, index, credential)
        self._index = index
        self._ready = False

    def _ensure(self, dimension: int) -> None:
        if self._ready:
            return
        from azure.search.documents.indexes.models import (
            HnswAlgorithmConfiguration,
            SearchField,
            SearchFieldDataType,
            SearchIndex,
            SimpleField,
            VectorSearch,
            VectorSearchProfile,
        )

        if self._index not in set(self._indexes.list_index_names()):
            self._indexes.create_index(SearchIndex(
                name=self._index,
                fields=[
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    SearchField(
                        name="vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        searchable=True, vector_search_dimensions=dimension, vector_search_profile_name="default",
                    ),
                ],
                vector_search=VectorSearch(
                    algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
                    profiles=[VectorSearchProfile(name="default", algorithm_configuration_name="hnsw")],
                ),
            ))
        self._ready = True

    def add(self, ids: list[str], vectors: np.ndarray) -> None:
        if not ids:
            return
        self._ensure(int(vectors.shape[1]))
        rows = [{"id": i, "vector": v.tolist()} for i, v in zip(ids, vectors, strict=True)]
        self._client.merge_or_upload_documents(rows)

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._client.delete_documents([{"id": i} for i in ids])

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        from azure.search.documents.models import VectorizedQuery

        query = VectorizedQuery(vector=np.asarray(vector).tolist(), k_nearest_neighbors=k, fields="vector")
        results = self._client.search(search_text=None, vector_queries=[query], select=["id"], top=k)
        return [(r["id"], float(r["@search.score"])) for r in results]

    def count(self) -> int:
        return int(self._client.get_document_count())

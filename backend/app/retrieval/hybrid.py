"""Hybrid retrieval: vector search and BM25 run side by side and are merged with Reciprocal Rank Fusion,
the same fusion Azure AI Search uses for its hybrid queries."""
from __future__ import annotations

from app.embeddings import Embedder
from app.models import ScoredChunk
from app.registry import Registry
from app.retrieval.bm25 import BM25Index
from app.vectorstores.base import VectorStore

RRF_K = 60


def reciprocal_rank_fusion(*rankings: list[str], k: int = RRF_K) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


class HybridRetriever:
    def __init__(self, embedder: Embedder, store: VectorStore, keywords: BM25Index, registry: Registry):
        self.embedder, self.store, self.keywords, self.registry = embedder, store, keywords, registry

    def retrieve(self, query: str, k: int) -> list[ScoredChunk]:
        candidates = max(k * 3, 10)
        vector_hits = [chunk_id for chunk_id, _ in self.store.search(self.embedder.embed_query(query), candidates)]
        keyword_hits = [chunk_id for chunk_id, _ in self.keywords.search(query, candidates)]
        fused = reciprocal_rank_fusion(vector_hits, keyword_hits)[:k]
        chunks = {c.id: c for c in self.registry.chunks([chunk_id for chunk_id, _ in fused])}
        vector_rank = {chunk_id: i for i, chunk_id in enumerate(vector_hits, start=1)}
        keyword_rank = {chunk_id: i for i, chunk_id in enumerate(keyword_hits, start=1)}
        return [
            ScoredChunk(chunks[chunk_id], round(score, 5), vector_rank.get(chunk_id), keyword_rank.get(chunk_id))
            for chunk_id, score in fused
            if chunk_id in chunks
        ]

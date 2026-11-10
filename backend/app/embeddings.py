"""Embedding providers behind one interface.

hashing    offline, deterministic feature hashing; for tests and for running with no models at all
fastembed  open-source Hugging Face models (default BAAI/bge-small-en-v1.5) run locally with ONNX
openai     OpenAI embeddings through LangChain
azure      Azure OpenAI embeddings through LangChain
cohere     Cohere embeddings through LangChain
"""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

import numpy as np

from app.config import Settings
from app.text import terms


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def _normalise(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix[None, :]
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


class HashingEmbedder:
    """Signed feature hashing of stemmed unigrams and bigrams. Cosine similarity then tracks shared vocabulary."""

    def __init__(self, dimensions: int = 768):
        self.dimensions = dimensions
        self.name = f"hashing-{dimensions}"

    def _vector(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        words = terms(text)
        features = words + [f"{a}_{b}" for a, b in zip(words, words[1:], strict=False)]
        counts: dict[str, int] = {}
        for feature in features:
            counts[feature] = counts.get(feature, 0) + 1
        for feature, count in counts.items():
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            weight = 1.0 + math.log(count)
            vector[bucket] += sign * (weight if "_" not in feature else 0.5 * weight)
        return vector

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.stack([self._vector(t) for t in texts])) if texts else np.zeros((0, self.dimensions))

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]


class FastEmbedEmbedder:
    def __init__(self, model: str):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model)
        self.name = f"fastembed-{model.split('/')[-1]}"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.stack(list(self._model.embed(texts)))) if texts else np.zeros((0, 1))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalise(np.stack(list(self._model.query_embed(text))))[0]


class LangChainEmbedder:
    """Adapter for any LangChain `Embeddings` implementation."""

    def __init__(self, embeddings, name: str):
        self._embeddings = embeddings
        self.name = name

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _normalise(np.array(self._embeddings.embed_documents(texts))) if texts else np.zeros((0, 1))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalise(np.array(self._embeddings.embed_query(text)))[0]


def build_embedder(settings: Settings) -> Embedder:
    provider, model = settings.embeddings_provider, settings.embeddings_model
    if provider == "hashing":
        return HashingEmbedder()
    if provider == "fastembed":
        return FastEmbedEmbedder(model or "BAAI/bge-small-en-v1.5")
    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        model = model or "text-embedding-3-small"
        return LangChainEmbedder(OpenAIEmbeddings(model=model), f"openai-{model}")
    if provider == "azure":
        from langchain_openai import AzureOpenAIEmbeddings

        model = model or "text-embedding-3-small"
        return LangChainEmbedder(AzureOpenAIEmbeddings(azure_deployment=model), f"azure-{model}")
    if provider == "cohere":
        from langchain_cohere import CohereEmbeddings

        model = model or "embed-english-v3.0"
        return LangChainEmbedder(CohereEmbeddings(model=model), f"cohere-{model}")
    raise ValueError(f"Unknown EMBEDDINGS_PROVIDER '{provider}'")

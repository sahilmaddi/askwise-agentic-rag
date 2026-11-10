from __future__ import annotations

import re

from app.config import Settings
from app.vectorstores.base import VectorStore


def build_vector_store(settings: Settings, embedder_name: str) -> VectorStore:
    """Indexes are kept per embedding model: switching models never mixes incompatible vectors."""
    kind = settings.vector_store
    folder = settings.data_dir / "index" / embedder_name
    if kind == "memory":
        from app.vectorstores.memory import MemoryVectorStore

        return MemoryVectorStore(folder / "vectors.npz")
    if kind == "faiss":
        from app.vectorstores.faiss_store import FaissVectorStore

        return FaissVectorStore(folder)
    if kind == "milvus":
        from app.vectorstores.milvus_store import MilvusVectorStore

        uri = settings.milvus_uri or str(settings.data_dir / "milvus.db")
        return MilvusVectorStore(uri, f"askwise_{embedder_name.replace('-', '_').replace('.', '_')}")
    if kind == "azure_search":
        from app.vectorstores.azure_search_store import AzureSearchVectorStore

        index = re.sub(r"[^a-z0-9-]+", "-", f"{settings.azure_search_index}-{embedder_name}".lower()).strip("-")
        return AzureSearchVectorStore(settings.azure_search_endpoint, settings.azure_search_key, index[:128])
    raise ValueError(f"Unknown VECTOR_STORE '{kind}'")

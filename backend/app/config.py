"""Runtime configuration, read once from environment variables.

Every layer of the pipeline is pluggable. The defaults need no API keys and no network, so the app and its tests
run anywhere; Docker Compose switches to local open-source models, and cloud providers are one variable away.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    value = _env(name)
    return default if not value else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Generation: extractive (offline) | ollama | openai | azure | mistral
    llm_provider: str = "extractive"
    llm_model: str = ""
    # Embeddings: hashing (offline) | fastembed | openai | azure | cohere
    embeddings_provider: str = "hashing"
    embeddings_model: str = ""
    # Vector store: memory | faiss | milvus | azure_search
    vector_store: str = "memory"
    # Chunking: recursive | sentence (spaCy when installed)
    chunker: str = "recursive"
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 5
    max_rewrites: int = 1
    max_upload_mb: int = 20
    data_dir: Path = Path("data")
    tika_url: str = ""
    azure_docintel_endpoint: str = ""
    azure_docintel_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    milvus_uri: str = ""
    azure_search_endpoint: str = ""
    azure_search_key: str = ""
    azure_search_index: str = "askwise-chunks"
    seed_samples: bool = False
    cors_origins: tuple[str, ...] = field(default_factory=lambda: ("http://localhost:5173",))

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            llm_provider=_env("LLM_PROVIDER", "extractive").lower(),
            llm_model=_env("LLM_MODEL"),
            embeddings_provider=_env("EMBEDDINGS_PROVIDER", "hashing").lower(),
            embeddings_model=_env("EMBEDDINGS_MODEL"),
            vector_store=_env("VECTOR_STORE", "memory").lower(),
            chunker=_env("CHUNKER", "recursive").lower(),
            chunk_size=int(_env("CHUNK_SIZE", "800")),
            chunk_overlap=int(_env("CHUNK_OVERLAP", "120")),
            top_k=int(_env("TOP_K", "5")),
            max_rewrites=int(_env("MAX_REWRITES", "1")),
            max_upload_mb=int(_env("MAX_UPLOAD_MB", "20")),
            data_dir=Path(_env("DATA_DIR", "data")),
            tika_url=_env("TIKA_URL"),
            azure_docintel_endpoint=_env("AZURE_DOCINTEL_ENDPOINT"),
            azure_docintel_key=_env("AZURE_DOCINTEL_KEY"),
            ollama_base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434"),
            milvus_uri=_env("MILVUS_URI"),
            azure_search_endpoint=_env("AZURE_SEARCH_ENDPOINT"),
            azure_search_key=_env("AZURE_SEARCH_KEY"),
            azure_search_index=_env("AZURE_SEARCH_INDEX", "askwise-chunks"),
            seed_samples=_bool("SEED_SAMPLES", False),
            cors_origins=tuple(o for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o),
        )

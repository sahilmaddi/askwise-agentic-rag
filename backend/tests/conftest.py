from __future__ import annotations

import pytest

from app.config import Settings
from app.service import RagService


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path, vector_store="memory", embeddings_provider="hashing", llm_provider="extractive",
                    chunk_size=500, chunk_overlap=80)


@pytest.fixture
def service(settings):
    rag = RagService(settings)
    rag.seed_samples()
    return rag

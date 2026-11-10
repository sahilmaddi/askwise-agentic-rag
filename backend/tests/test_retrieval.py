import numpy as np

from app.embeddings import HashingEmbedder
from app.retrieval.bm25 import BM25Index
from app.retrieval.hybrid import reciprocal_rank_fusion
from app.vectorstores.memory import MemoryVectorStore


def test_bm25_ranks_exact_terms_first():
    index = BM25Index()
    index.add([("a", "Hotels are reimbursed up to INR 9,000 per night"), ("b", "Laptops are replaced every 3 years"),
               ("c", "Hotel stays with family are claimed at a flat rate")])
    results = index.search("hotel reimbursement per night", 3)
    assert results[0][0] == "a"
    index.delete(["a"])
    assert [r[0] for r in index.search("hotel", 3)] == ["c"]


def test_reciprocal_rank_fusion_rewards_agreement():
    fused = reciprocal_rank_fusion(["x", "y", "z"], ["y", "x", "w"])
    assert [item for item, _ in fused][:2] in (["x", "y"], ["y", "x"])
    assert dict(fused)["w"] < dict(fused)["x"]


def test_hashing_embeddings_are_normalised_and_similar_for_similar_text():
    embedder = HashingEmbedder()
    leave, leave2, laptop = embedder.embed_documents(
        ["annual leave days per year", "how many days of annual leave", "laptop replacement every three years"])
    assert np.isclose(np.linalg.norm(leave), 1.0)
    assert leave @ leave2 > leave @ laptop


def test_memory_store_search_delete_and_persist(tmp_path):
    path = tmp_path / "v.npz"
    store = MemoryVectorStore(path)
    vectors = np.eye(3, dtype=np.float32)
    store.add(["a", "b", "c"], vectors)
    assert store.search(np.array([0, 1, 0], dtype=np.float32), 1)[0][0] == "b"
    store.delete(["b"])
    reloaded = MemoryVectorStore(path)
    assert reloaded.count() == 2
    assert "b" not in [i for i, _ in reloaded.search(np.array([0, 1, 0], dtype=np.float32), 3)]


def test_faiss_store_matches_memory_store(tmp_path):
    import pytest

    pytest.importorskip("faiss")
    from app.vectorstores import faiss_store

    store = faiss_store.FaissVectorStore(tmp_path / "faiss")
    vectors = np.eye(4, dtype=np.float32)
    store.add(["a", "b", "c", "d"], vectors)
    store.delete(["c"])
    store.add(["a"], vectors[[1]])  # re-adding replaces
    reloaded = faiss_store.FaissVectorStore(tmp_path / "faiss")
    assert reloaded.count() == 3
    assert [i for i, _ in reloaded.search(np.array([0, 1, 0, 0], dtype=np.float32), 2)] in (["a", "b"], ["b", "a"])

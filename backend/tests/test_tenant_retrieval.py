import numpy as np
import pytest
from services.embedding_service import EmbeddingService
from services.retrieval_service import RetrievalService
from services.vector_store_service import VectorStoreService

TENANT_A = 1
TENANT_B = 2
DIM = VectorStoreService.DIMENSION  # 384


@pytest.fixture
def seeded_store(tmp_path, monkeypatch):
    """A temporary index where tenant B's chunks are closer to the query than tenant A's."""
    # 1. Point the store at a temp folder instead of the real vectorstore/
    monkeypatch.setattr(VectorStoreService, "INDEX_PATH", str(tmp_path / "index.faiss"))
    monkeypatch.setattr(VectorStoreService, "META_PATH", str(tmp_path / "metadata.json"))

    # 2. Fixed query vector, and a fake embed_query that returns it
    query_vec = np.zeros(DIM, dtype="float32")
    query_vec[0] = 1.0
    monkeypatch.setattr(EmbeddingService, "embed_query", lambda question: query_vec)

    rng = np.random.default_rng(0)

    # 3. Tenant B: 10 vectors almost identical to the query (distance ~0.2)
    b_vecs = query_vec + rng.normal(0, 0.01, size=(10, DIM))
    b_meta = [
        {"document_id": 20, "enterprise_id": TENANT_B, "chunk_index": i, "chunk_text": f"B chunk {i}"}
        for i in range(10)
    ]

    # 4. Tenant A: 5 vectors farther away (distance ~10)
    a_vecs = query_vec + rng.normal(0, 0.5, size=(5, DIM))
    a_meta = [
        {"document_id": 10, "enterprise_id": TENANT_A, "chunk_index": i, "chunk_text": f"A chunk {i}"}
        for i in range(5)
    ]

    # 5. Index both tenants in one shared store, as the app does today
    VectorStoreService.add_embeddings(b_vecs.astype("float32"), b_meta)
    VectorStoreService.add_embeddings(a_vecs.astype("float32"), a_meta)


def test_no_cross_tenant_leakage(seeded_store):
    results = RetrievalService.retrieve("any question", enterprise_id=TENANT_A, top_k=5)
    assert all(r["enterprise_id"] == TENANT_A for r in results)


@pytest.mark.xfail(
    strict=True,
    reason="Post-filtering starves tenants; fixed by Qdrant query-time filter",
)
def test_tenant_gets_its_own_results(seeded_store):
    results = RetrievalService.retrieve("any question", enterprise_id=TENANT_A, top_k=5)
    assert len(results) == 5
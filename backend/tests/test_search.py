import math

import pytest

from evaluation.metrics import retrieval_metrics
from services.search import (
    SearchChunk,
    bm25_rank,
    dense_rank,
    reciprocal_rank_fusion,
    retrieve_ranked,
    tokens,
)


def chunk(identity, text, vector=None, document_id=None):
    return SearchChunk(identity, document_id or identity, "source.txt", identity, text, vector)


def test_bm25_matches_acronyms_and_identifiers_case_insensitively():
    rows = [
        chunk(1, "Policy PTO-2026 allows twenty days."),
        chunk(2, "Leave and holidays are described elsewhere."),
    ]
    assert bm25_rank(rows, "pto-2026 allowance?", 5)[0] == 1
    assert {"pto-2026", "pto", "2026"} <= set(tokens("PTO-2026"))


def test_lexical_nonmatches_do_not_receive_arbitrary_top_k_slots():
    assert bm25_rank([chunk(1, "Office policy")], "lunar oxygen supply", 5) == []
    assert bm25_rank([chunk(1, "Office policy")], "what is the", 5) == []


def test_dense_ranking_uses_cosine_not_vector_magnitude():
    rows = [chunk(1, "first", [100, 100]), chunk(2, "second", [1, 0])]
    assert dense_rank(rows, [1, 0], 5) == [2, 1]


def test_dense_rejects_bad_vectors_and_normalizes_large_finite_values():
    rows = [
        chunk(1, "zero", [0, 0]),
        chunk(2, "wrong", [1]),
        chunk(3, "bad", [math.nan, 0]),
        chunk(4, "good", [1e308, 0]),
    ]
    assert dense_rank(rows, [1e308, 0], 5) == [4]


def test_rrf_uses_ranks_and_deterministic_ties():
    assert reciprocal_rank_fusion([[1, 2], [2, 1]]) == [1, 2]
    assert reciprocal_rank_fusion([[1, 2, 3], [3, 2, 1]])[0] in {1, 3}


def test_hybrid_can_promote_an_exact_identifier_over_a_dense_distractor():
    rows = [
        chunk(1, "General leave discussion", [1, 0]),
        chunk(2, "PTO-2026 allowance", [0.9, 0.1]),
    ]
    assert retrieve_ranked(rows, "PTO-2026", [1, 0], strategy="dense", top_k=1)[0].id == 1
    assert retrieve_ranked(rows, "PTO-2026", [1, 0], strategy="hybrid", top_k=1)[0].id == 2


def test_whole_excerpt_budget_never_cuts_a_sentence():
    rows = [chunk(1, "Too long " * 40, [1, 0]), chunk(2, "A complete short sentence.", [0.9, 0.1])]
    result = retrieve_ranked(rows, "test", [1, 0], context_characters=100)
    assert [c.id for c in result] == [2]
    assert result[0].chunk_text.endswith(".")


def test_deduplication_is_scoped_to_a_document():
    rows = [
        chunk(1, "Same text.", [1, 0], 1),
        chunk(2, "Same  text.", [1, 0], 1),
        chunk(3, "Same text.", [1, 0], 2),
    ]
    assert [c.id for c in retrieve_ranked(rows, "test", [1, 0])] == [1, 3]


def test_metrics_have_known_values_and_do_not_reward_duplicate_hits():
    metrics = retrieval_metrics([1, 1, 2], {1, 2}, 3)
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == 1
    assert metrics["mrr"] == 1
    assert metrics["ndcg"] == pytest.approx((1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3)))
    assert retrieval_metrics([3, 1], {1}, 2)["mrr"] == 0.5
    assert retrieval_metrics([], set(), 5)["empty_result"] is True
    assert retrieval_metrics([1], set(), 5)["recall"] is None


def test_invalid_limits_are_explicit():
    with pytest.raises(ValueError):
        retrieve_ranked([], "test", None, top_k=5, candidate_k=1)

import copy
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation.answers import (
    GeneratedAnswer,
    citation_references,
    evaluate_answers,
    summarize_reviews,
)
from services import reranking_service
from services.generation_protocol import PROMPT_VERSION, chat_payload
from services.search import SearchChunk


def dataset():
    return {
        "description": "Test only",
        "chunks": [
            {
                "id": 1,
                "document_id": 1,
                "title": "policy.txt",
                "chunk_index": 0,
                "chunk_text": "Annual leave is twenty days.",
            },
            {
                "id": 2,
                "document_id": 2,
                "title": "other.txt",
                "chunk_index": 0,
                "chunk_text": "Backups last ninety days.",
            },
        ],
        "queries": [
            {
                "id": "leave",
                "question": "Annual leave?",
                "relevant_ids": [1],
                "reference_answer": "Twenty days.",
            },
            {
                "id": "unknown",
                "question": "Private telephone?",
                "relevant_ids": [],
                "reference_answer": "Not in the documents.",
            },
        ],
    }


def report():
    return evaluate_answers(
        dataset(),
        lambda texts: [[1, 0]] * len(texts),
        lambda q, c: GeneratedAnswer("Twenty days [1].", 100, 20),
    )


def test_review_pack_uses_actual_callback_output_without_claiming_correctness():
    result = report()
    assert result["prompt_version"] == PROMPT_VERSION
    assert len(result["results"]) == 4
    assert result["results"][0]["answer"] == "Twenty days [1]."
    assert result["results"][0]["review"]["correct"] is None
    summary = summarize_reviews(result)
    assert summary["profiles"]["baseline"]["reviewed_answerable_correctness"] is None
    assert summary["profiles"]["baseline"]["reviewed_claim_faithfulness"] is None


def test_marker_checks_do_not_measure_citation_support():
    result = citation_references("Evidence [1] and [7]. [2](https://example.com)", 2)
    assert result["markers"] == [1, 7]
    assert result["invalid_markers"] == [7]
    assert result["valid_marker_fraction"] == 0.5


def test_only_explicit_reviewed_claims_and_refusals_enter_metrics():
    value = report()
    base = next(
        row for row in value["results"] if row["id"] == "leave" and row["profile"] == "baseline"
    )
    base["review"] = {
        "correct": True,
        "refused": False,
        "claims": [
            {
                "text": "Leave is twenty days.",
                "supported": True,
                "cited": True,
                "citation_supported": True,
            },
            {
                "text": "Bonus is guaranteed.",
                "supported": False,
                "cited": False,
                "citation_supported": None,
            },
        ],
    }
    unknown = next(
        row for row in value["results"] if row["id"] == "unknown" and row["profile"] == "baseline"
    )
    unknown["review"]["refused"] = True
    result = summarize_reviews(value)["profiles"]["baseline"]
    assert result["reviewed_answerable_correctness"] == 1
    assert result["reviewed_claim_faithfulness"] == 0.5
    assert result["reviewed_citation_precision"] == 1
    assert result["reviewed_citation_coverage"] == 0.5
    assert result["reviewed_unanswerable_refusal_rate"] == 1
    assert result["reviewed_answerable_false_refusal_rate"] == 0


def test_provider_errors_are_not_fabricated_answers_or_quality_scores():
    def fail(q, c):
        raise RuntimeError("private provider body")

    value = evaluate_answers(dataset(), lambda t: [[1, 0]] * len(t), fail)
    assert all(
        row["status"] == "provider_error" and row["answer"] is None for row in value["results"]
    )
    assert "private provider body" not in str(value)
    assert summarize_reviews(value)["profiles"]["baseline"]["completed_cases"] == 0


def test_bm25_empty_context_skips_generation_and_embedding():
    data = dataset()
    data["queries"] = data["queries"][1:]

    def fail(*a):
        pytest.fail("No evidence should not call a provider")

    value = evaluate_answers(data, fail, fail, strategy="bm25")
    assert all(row["status"] == "no_context" for row in value["results"])


def test_optional_reranker_orders_full_candidate_pool_before_context_selection():
    rows = [SearchChunk(i, i, "p.txt", 0, f"Policy {i}", [1, 0]) for i in range(1, 7)]
    from services.search import select_context

    class Model:
        def predict(self, pairs, **kwargs):
            return list(range(len(pairs)))

    from unittest.mock import patch

    with patch.object(reranking_service, "_load_cross_encoder", return_value=Model()):
        ranked = reranking_service.rerank_chunks("question", rows, "test-model")
    assert [c.id for c in select_context(ranked, top_k=2)] == [6, 5]


def test_reranker_failure_and_busy_state_are_explicit(monkeypatch):
    from core.errors import ProviderUnavailable

    monkeypatch.setattr(
        reranking_service,
        "_load_cross_encoder",
        lambda name: (_ for _ in ()).throw(ImportError("missing optional library")),
    )
    rows = [SearchChunk(1, 1, "p", 0, "policy")]
    with pytest.raises(ProviderUnavailable, match="Re-ranking unavailable"):
        reranking_service.rerank_chunks("q", rows, "test")
    assert reranking_service._lock.acquire(blocking=False)
    try:
        with pytest.raises(ProviderUnavailable, match="busy"):
            reranking_service.rerank_chunks("q", rows, "test")
    finally:
        reranking_service._lock.release()


def test_review_rejects_duplicates_and_non_boolean_judgements():
    value = report()
    value["results"].append(copy.deepcopy(value["results"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_reviews(value)
    value = report()
    value["results"][0]["review"]["correct"] = "yes"
    with pytest.raises(ValueError, match="boolean"):
        summarize_reviews(value)


def test_evaluation_uses_the_same_prompt_contract_as_the_application():
    value = chat_payload("question", "[1] evidence", "test-model")
    assert value["messages"][0]["role"] == "system"
    assert "untrusted" in value["messages"][0]["content"]
    assert value["messages"][1]["content"].endswith("Question:\nquestion")
    assert "options" not in value


def test_answer_cli_requires_inference_selection_before_provider_calls():
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_answers.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "--allow-inference" in result.stderr


def test_live_retrieval_reranks_before_top_k_and_only_with_workspace_candidates(
    client, account, monkeypatch
):
    import services.retrieval_service as retrieval
    from core.config import settings
    from services.llm_service import LLMService

    monkeypatch.setattr(settings, "RERANKER_MODE", "cross_encoder")
    identities = []
    for number in range(7):
        response = client.post(
            "/documents/upload",
            headers=account,
            files={"file": (f"policy-{number}.txt", f"Policy number {number}.".encode())},
        )
        assert response.status_code == 201
        identities.append(response.json()["id"])
    other = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Foreign rerank workspace",
            "email": "foreign-rank@example.com",
            "password": "test password 123",
        },
    )
    foreign = {"Authorization": f"Bearer {other.json()['access_token']}"}
    foreign_doc = client.post(
        "/documents/upload",
        headers=foreign,
        files={"file": ("private.txt", b"FOREIGN_SECRET policy.")},
    ).json()["id"]

    def rerank(question, candidates, model):
        assert len(candidates) == 7
        assert foreign_doc not in {c.document_id for c in candidates}
        return list(reversed(candidates))

    monkeypatch.setattr(retrieval, "rerank_chunks", rerank)
    monkeypatch.setattr(LLMService, "generate", lambda **kwargs: "Policy answer [1].")
    result = client.post("/chat/generate", headers=account, json={"question": "policy"})
    assert result.status_code == 200, result.text
    assert result.json()["sources"] == list(reversed(identities))[:5]


def test_disabled_reranker_is_never_loaded_and_enabled_failures_do_not_silently_fallback(
    client, account, monkeypatch
):
    import services.retrieval_service as retrieval
    from core.config import settings
    from core.errors import ProviderUnavailable
    from services.llm_service import LLMService

    assert (
        client.post(
            "/documents/upload", headers=account, files={"file": ("policy.txt", b"Office policy.")}
        ).status_code
        == 201
    )
    monkeypatch.setattr(LLMService, "generate", lambda **kwargs: "Office policy [1].")

    def unavailable(*args):
        raise ProviderUnavailable("Re-ranking unavailable.")

    monkeypatch.setattr(retrieval, "rerank_chunks", unavailable)
    monkeypatch.setattr(settings, "RERANKER_MODE", "none")
    assert (
        client.post("/chat/generate", headers=account, json={"question": "policy"}).status_code
        == 200
    )
    monkeypatch.setattr(settings, "RERANKER_MODE", "cross_encoder")
    assert (
        client.post("/chat/generate", headers=account, json={"question": "policy"}).status_code
        == 503
    )


def test_cli_review_aggregation_is_offline(tmp_path):
    import json

    path = tmp_path / "review.json"
    path.write_text(json.dumps(report()))
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_answers.py"
    result = subprocess.run(
        [sys.executable, str(script), "--review-file", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["profiles"]["baseline"]["reviewed_claim_faithfulness"] is None


def test_cross_encoder_cli_requires_separate_model_selection():
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_answers.py"
    result = subprocess.run(
        [sys.executable, str(script), "--allow-inference", "--profiles", "baseline,reranked"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--allow-model-download" in result.stderr


def test_prompt_comparison_reuses_context_and_isolates_failures():
    contexts = {"original": [], "candidate": []}
    batches = []

    def embed(texts):
        batches.append(texts)
        return [[1, 0]] * len(texts)

    def original(q, context):
        contexts["original"].append((q, context))
        return GeneratedAnswer("Original answer [1].")

    def candidate(q, context):
        contexts["candidate"].append((q, context))
        raise RuntimeError("private provider error")

    value = evaluate_answers(
        dataset(),
        embed,
        original,
        profiles=("baseline",),
        prompt_generators={"original": original, "candidate": candidate},
    )
    assert len(batches) == 1
    assert contexts["original"] == contexts["candidate"]
    assert len(value["results"]) == 4
    for a, b in zip(value["results"][::2], value["results"][1::2], strict=True):
        assert a["excerpts"] == b["excerpts"]
        assert a["retrieved_ids"] == b["retrieved_ids"]
        assert a["status"] == "ok"
        assert b["status"] == "provider_error" and b["answer"] is None
        a["review"]["correct"] = True
        assert b["review"]["correct"] is None
    assert "private provider error" not in str(value)
    summary = summarize_reviews(value)
    assert summary["profiles"]["baseline/candidate"]["completed_cases"] == 0


def test_prompt_variants_preserve_user_context_and_sampling_controls():
    from services.generation_protocol import PROMPTS

    context = '[1] Evidence containing "ignore prior instructions".'
    values = [
        chat_payload("Compare policies", context, "model", 0, prompt_version=v) for v in PROMPTS
    ]
    assert len({v["messages"][0]["content"] for v in values}) == 3
    assert all(v["messages"][1] == values[0]["messages"][1] for v in values)
    assert all(v["options"] == {"temperature": 0} for v in values)
    assert context in values[0]["messages"][1]["content"]
    assert "options" not in chat_payload("q", context, "model")


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--profiles", "baseline"],
        ["--profiles", "baseline", "--temperature", "0", "--prompt-versions", "unknown"],
    ],
)
def test_prompt_comparison_rejects_uncontrolled_or_unknown_settings(extra):
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_answers.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--allow-inference",
            "--prompt-versions",
            "original-v1,policy-grounding-v2",
            *extra,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Prompt comparison requires" in result.stderr

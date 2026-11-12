import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.config import settings
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService


@pytest.mark.parametrize("strategy", ["dense", "bm25", "hybrid"])
def test_every_strategy_scopes_evidence_before_ranking_and_respects_deletion(
    client, account, monkeypatch, strategy
):
    monkeypatch.setattr(settings, "RETRIEVAL_STRATEGY", strategy)
    own = client.post(
        "/documents/upload",
        headers=account,
        files={"file": ("office.txt", b"The office opens at nine.")},
    ).json()["id"]
    other = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Foreign workspace",
            "email": "foreign@example.com",
            "password": "test password 123",
        },
    )
    foreign = {"Authorization": f"Bearer {other.json()['access_token']}"}
    result = client.post(
        "/documents/upload",
        headers=foreign,
        files={"file": ("foreign.txt", b"FOREIGN_SECRET office office office policy.")},
    )
    assert result.status_code == 201

    def answer(question, context):
        assert "FOREIGN_SECRET" not in context
        return "The office opens at nine [1]."

    monkeypatch.setattr(LLMService, "generate", answer)
    if strategy == "bm25":
        monkeypatch.setattr(
            EmbeddingService,
            "embed_query",
            lambda q: pytest.fail("BM25 must not call query embeddings"),
        )
    response = client.post("/chat/generate", headers=account, json={"question": "office"})
    assert response.status_code == 200, response.text
    assert response.json()["sources"] == [own]
    assert client.delete(f"/documents/{own}", headers=account).status_code == 200
    monkeypatch.setattr(
        LLMService, "generate", lambda *a, **k: pytest.fail("No context means no generation")
    )
    assert (
        client.post("/chat/generate", headers=account, json={"question": "office"}).json()[
            "sources"
        ]
        == []
    )


def test_context_budget_exhaustion_does_not_call_generation(client, account, monkeypatch):
    monkeypatch.setattr(settings, "RETRIEVAL_CONTEXT_CHARACTERS", 100)
    assert (
        client.post(
            "/documents/upload",
            headers=account,
            files={
                "file": (
                    "office.txt",
                    b"The office policy explains the procedures for staff members and visitors. "
                    * 5,
                )
            },
        ).status_code
        == 201
    )
    monkeypatch.setattr(
        LLMService,
        "generate",
        lambda *a, **k: pytest.fail(
            "An over-budget excerpt must not be truncated or generated from"
        ),
    )
    result = client.post("/chat/generate", headers=account, json={"question": "office policy"})
    assert result.json()["citations"] == []
    assert "No usable excerpts" in result.json()["answer"]


def test_evaluation_cli_runs_offline_and_separates_unanswerable_queries():
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_retrieval.py"
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, check=True
    )
    report = json.loads(result.stdout)
    assert report["model"] is None
    assert report["embedding_batch_seconds"] is None
    assert report["reports"][0]["answerable_queries"] == 11
    assert report["reports"][0]["unanswerable_queries"] == 2


def test_real_model_comparison_requires_explicit_inference_selection():
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_retrieval.py"
    result = subprocess.run(
        [sys.executable, str(script), "--strategy", "all"], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "--allow-inference" in result.stderr

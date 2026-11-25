"""Failures observed in the pipeline audit, exercised from original source documents."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from core.config import settings
from core.errors import InvalidDocument, ProviderUnavailable
from evaluation.answers import summarize_reviews
from models.document import Document
from models.document_chunk import DocumentChunk
from models.user import User
from services.answer_validation import UNVERIFIED_ANSWER, citation_check
from services.chunking_service import ChunkingService
from services.document_service import DocumentService
from services.embedding_service import EmbeddingService
from services.generation_protocol import chat_payload
from services.indexing_service import prepare_index
from services.llm_service import LLMService
from services.loader_service import ExtractedDocument, LoaderService, SourcePage
from services.retrieval_service import RetrievalService
from services.search import (
    SearchChunk,
    bm25_rank,
    dense_rank,
    rank_candidates,
    reciprocal_rank_fusion,
    select_context,
    stream_candidates,
)


def upload(client, account, content=b"The office opens at nine.", **kwargs):
    return client.post(
        "/documents/upload", headers=account, files={"file": ("policy.txt", content)}, **kwargs
    )


def test_mixed_pdf_cannot_silently_omit_a_scanned_page(monkeypatch, tmp_path):
    import services.loader_service as loader

    monkeypatch.setattr(
        loader,
        "PdfReader",
        lambda _: SimpleNamespace(
            is_encrypted=False,
            pages=[
                SimpleNamespace(extract_text=lambda: "Readable cover.", images=[]),
                SimpleNamespace(extract_text=lambda: "", images=[object()]),
            ],
        ),
    )
    with pytest.raises(InvalidDocument, match="Page 2.*OCR"):
        LoaderService.extract(tmp_path / "mixed.pdf")


def test_blank_pdf_page_is_recorded_in_warnings(monkeypatch, tmp_path):
    import services.loader_service as loader

    monkeypatch.setattr(
        loader,
        "PdfReader",
        lambda _: SimpleNamespace(
            is_encrypted=False,
            pages=[
                SimpleNamespace(extract_text=lambda: "", images=[]),
                SimpleNamespace(extract_text=lambda: "Readable second page.", images=[]),
            ],
        ),
    )
    result = LoaderService.extract(tmp_path / "blank.pdf")
    assert result.pages[1].number == 2
    assert any("Page 1 has no extractable text" in w for w in result.warnings)


def test_table_rows_and_original_source_offsets_survive_chunking():
    table = "Category\tAmount.\nEquipment\t5000.\nTravel\t2000."
    document = ExtractedDocument([SourcePage(3, "# Allowances\n\n" + table)])
    chunks = ChunkingService.chunk_document(document)
    assert any(table in chunk.chunk_text for chunk in chunks)
    for chunk in chunks:
        assert chunk.chunk_text == document.pages[0].text[chunk.start_offset : chunk.end_offset]
        assert chunk.page_start == chunk.page_end == 3
        assert chunk.section == "Allowances"


def test_section_expansion_never_crosses_a_heading(client, account, db, monkeypatch):
    text = b"# Current policy\nRemote work requires approval.\n\n# Archived policy\nRemote work is unrestricted."
    upload(client, account, text)
    monkeypatch.setattr(settings, "RETRIEVAL_TOP_K", 1)
    result = RetrievalService.retrieve("approval", db.scalar(select(User)).enterprise_id, db)
    assert "unrestricted" not in result[0]["chunk_text"]
    assert result[0]["section"] == "Current policy"


def test_embedding_batches_are_bounded_and_counted(client, account, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CHUNK_SIZE", 100)
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 2)
    batches = []

    def embed(texts):
        batches.append(texts)
        return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr(EmbeddingService, "embed_texts", embed)
    source = tmp_path / "long.txt"
    source.write_text(
        " ".join(
            f"Sentence {i} describes a complete policy covering ordinary office operations and employee access."
            for i in range(8)
        )
    )
    indexed, _, metadata = prepare_index(source)
    assert len(batches) > 1 and max(map(len, batches)) == 2
    assert sum(map(len, batches)) == len(indexed) == metadata["chunk_count"]


def test_embedding_requests_forbid_silent_truncation(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 2)

    def post(url, **kwargs):
        assert kwargs["json"]["truncate"] is False
        return httpx.Response(
            200, json={"embeddings": [[1.0, 0.0]]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", post)
    assert EmbeddingService.embed_query("policy") == [1.0, 0.0]


def test_embedding_token_limit_error_is_actionable(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kwargs: httpx.Response(
            400, text="input exceeds maximum context length", request=httpx.Request("POST", url)
        ),
    )
    with pytest.raises(InvalidDocument, match="token limit"):
        EmbeddingService.embed_query("long input")


def test_pinned_embedding_revision_rejects_mutated_ollama_tag(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "all-minilm")
    monkeypatch.setattr(settings, "EMBEDDING_REVISION", "expected-digest")
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kwargs: httpx.Response(
            200,
            json={"models": [{"name": "all-minilm:latest", "digest": "different-digest"}]},
            request=httpx.Request("GET", url),
        ),
    )
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: pytest.fail("A changed model must not embed against an old index"),
    )
    with pytest.raises(ProviderUnavailable, match="revision differs"):
        EmbeddingService.embed_query("question")


def test_zero_and_negative_similarity_abstain_and_scores_are_retained():
    rows = [
        SearchChunk(1, 1, "p", 0, "opposite", [-1.0, 0.0]),
        SearchChunk(2, 2, "p", 0, "orthogonal", [0.0, 1.0]),
    ]
    assert rank_candidates(rows, "query", [1.0, 0.0]) == []
    rows.append(SearchChunk(3, 3, "p", 0, "related", [1.0, 0.0]))
    result = rank_candidates(rows, "query", [1.0, 0.0], min_similarity=0.7)
    assert [c.id for c in result] == [3] and result[0].dense_score == 1.0


@pytest.mark.parametrize("strategy", ["dense", "bm25", "hybrid"])
def test_streaming_and_in_memory_rankers_match(strategy):
    rows = [
        SearchChunk(i, i, "policy", i, "office access " * i, [1.0, i / 10]) for i in range(1, 21)
    ]
    dense = dense_rank(rows, [1.0, 0.0], 5)
    lexical = bm25_rank(rows, "office access", 5)
    expected = (
        dense
        if strategy == "dense"
        else lexical
        if strategy == "bm25"
        else reciprocal_rank_fusion([dense, lexical])[:5]
    )
    actual = stream_candidates(
        lambda: iter(rows), "office access", [1.0, 0.0], strategy=strategy, candidate_k=5
    )
    assert [c.id for c in actual] == expected


@pytest.mark.parametrize("strategy", ["bm25", "hybrid"])
def test_lexical_retrieval_survives_embedding_model_change(
    client, account, db, monkeypatch, strategy
):
    identity = upload(client, account).json()["id"]
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "new-model")
    monkeypatch.setattr(settings, "RETRIEVAL_STRATEGY", strategy)
    result = RetrievalService.retrieve("office", db.scalar(select(User)).enterprise_id, db)
    assert result[0]["document_id"] == identity


def test_background_upload_is_durable_and_retryable(client, account, db, monkeypatch):
    monkeypatch.setattr(
        EmbeddingService, "embed_texts", lambda _: pytest.fail("Upload must not call inference")
    )
    response = upload(client, account, data={"background": "true"})
    assert response.status_code == 201 and response.json()["index_status"] == "queued"
    identity = response.json()["id"]
    assert db.scalar(select(DocumentChunk)) is None
    monkeypatch.setattr(
        EmbeddingService,
        "embed_texts",
        lambda _: (_ for _ in ()).throw(ProviderUnavailable("secret upstream URL")),
    )
    assert DocumentService.process_next(db)
    document = db.get(Document, identity)
    assert document.index_status == "failed" and "secret" not in document.index_error
    assert Path(document.file_path).exists()
    assert client.post(f"/documents/{identity}/reindex", headers=account).status_code == 202
    monkeypatch.setattr(
        EmbeddingService, "embed_texts", lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    )
    assert DocumentService.process_next(db)
    db.refresh(document)
    assert document.index_status == "ready"
    assert db.scalar(select(DocumentChunk)).section_key is not None


def test_failed_reindex_preserves_old_chunks_and_success_replaces_them(
    client, account, db, monkeypatch
):
    identity = upload(client, account).json()["id"]
    original = db.scalar(select(DocumentChunk)).chunk_text
    monkeypatch.setattr(
        EmbeddingService,
        "embed_texts",
        lambda _: (_ for _ in ()).throw(ProviderUnavailable("no model")),
    )
    client.post(f"/documents/{identity}/reindex", headers=account)
    DocumentService.process_next(db)
    assert db.scalar(select(DocumentChunk)).chunk_text == original
    assert db.get(Document, identity).index_status == "failed"
    monkeypatch.setattr(
        EmbeddingService, "embed_texts", lambda texts: [[0.0, 1.0, 0.0] for _ in texts]
    )
    client.post(f"/documents/{identity}/reindex", headers=account)
    DocumentService.process_next(db)
    chunks = db.scalars(select(DocumentChunk)).all()
    assert len(chunks) == 1 and chunks[0].embedding == [0.0, 1.0, 0.0]


def test_source_replacement_swaps_file_and_index_atomically(client, account, db):
    identity = upload(client, account).json()["id"]
    old_path = Path(db.get(Document, identity).file_path)
    response = client.post(
        f"/documents/{identity}/replace",
        headers=account,
        files={"file": ("policy.txt", b"The office opens at ten.")},
    )
    assert response.status_code == 202
    document = db.get(Document, identity)
    assert document.file_path == str(old_path) and old_path.exists()
    assert "nine" in db.scalar(select(DocumentChunk)).chunk_text
    DocumentService.process_next(db)
    db.refresh(document)
    assert document.id == identity and document.pending_file_path is None
    assert not old_path.exists() and "ten" in Path(document.file_path).read_text()
    assert "ten" in db.scalar(select(DocumentChunk)).chunk_text


def test_delete_queued_replacement_cleans_both_files(client, account, db):
    identity = upload(client, account).json()["id"]
    client.post(
        f"/documents/{identity}/replace",
        headers=account,
        files={"file": ("policy.txt", b"Replacement policy.")},
    )
    paths = [
        Path(db.get(Document, identity).file_path),
        Path(db.get(Document, identity).pending_file_path),
    ]
    assert client.delete(f"/documents/{identity}", headers=account).status_code == 200
    assert all(not path.exists() for path in paths)
    assert DocumentService.process_next(db) is False


def test_salary_name_and_amount_on_different_pdf_pages_are_reconstructed(
    client, account, monkeypatch
):
    monkeypatch.setattr(settings, "FINANCIAL_CALCULATIONS_ENABLED", True)
    monkeypatch.setattr(
        LLMService,
        "generate",
        lambda **kwargs: pytest.fail("Complete supported gross amount must use calculator"),
    )
    path = Path(__file__).resolve().parents[1] / "evaluation/sources/offer-letter.pdf"
    uploaded = client.post(
        "/documents/upload", headers=account, files={"file": ("offer.pdf", path.read_bytes())}
    )
    assert uploaded.status_code == 201, uploaded.text
    answer = client.post(
        "/chat/generate",
        headers=account,
        json={"question": "What is Alice Morgan monthly gross pay?"},
    )
    assert "INR 100,000.00" in answer.json()["answer"], answer.text
    assert any(c["page_start"] == 1 and c["page_end"] == 2 for c in answer.json()["citations"])


@pytest.mark.parametrize(
    "answer", ["An unsupported answer.", "A claim [99].", "A claim [1].\n\nAnother uncited claim."]
)
def test_bad_citations_are_not_served_as_answers(client, account, monkeypatch, answer):
    upload(client, account)
    monkeypatch.setattr(LLMService, "generate", lambda **kwargs: answer)
    response = client.post("/chat/generate", headers=account, json={"question": "office"})
    assert response.json()["answer"] == UNVERIFIED_ANSWER
    assert response.json()["citation_status"] == "invalid"


def test_prompt_rejects_overbudget_unicode_instead_of_truncating_evidence():
    with pytest.raises(ValueError, match="budget"):
        chat_payload("question", "文" * 6000, "model", context_tokens=4096)


def test_review_gate_rejects_unscored_successful_generations():
    report = {
        "results": [
            {
                "id": "case",
                "profile": "application",
                "status": "ok",
                "relevant_ids": [1],
                "review": {"correct": None, "refused": None, "claims": []},
            }
        ]
    }
    assert summarize_reviews(report)["quality_review_complete"] is False
    with pytest.raises(ValueError, match="Quality gate"):
        summarize_reviews(report, require_complete=True)


def test_contained_expanded_passage_does_not_duplicate_incomplete_evidence():
    anchor = SearchChunk(
        1, 1, "p", 0, "Name without amount.", section_key="section-0", chunk_end_index=1
    )
    complete = replace(anchor, id=2, chunk_end_index=2, chunk_text="Name and amount.")
    assert select_context([anchor, complete]) == [complete]


def test_raw_source_evaluation_uses_employee_identity_and_access_filtering(client, db, monkeypatch):
    import json

    from evaluation.sources import evaluate_sources

    root = Path(__file__).resolve().parents[1] / "evaluation/sources"
    monkeypatch.setattr(settings, "FINANCIAL_CALCULATIONS_ENABLED", True)
    monkeypatch.setattr(
        LLMService, "generate", lambda **kwargs: "The supplied evidence supports this answer [1]."
    )
    report = evaluate_sources(json.loads((root / "cases.json").read_text()), root, db)
    results = {row["id"]: row for row in report["results"]}
    assert not any(row["status"] == "pipeline_error" for row in results.values())
    assert "INR 100,000.00" in results["personal-salary"]["answer"]
    private_id = next(row["document_id"] for row in report["ingestion"] if row["key"] == "offer")
    assert private_id not in results["private-salary"]["sources"]
    assert "100,000" not in results["private-salary"]["answer"]
    assert results["retention-comparison"]["document_recall"] == 1
    assert all(row["review"]["correct"] is None for row in results.values())


def test_citation_checks_table_rows_and_does_not_count_one_citation_for_a_second_claim():
    table = "| Benefit | Amount |\n|---|---|\n| Equipment | INR 5,000 [1] |"
    assert citation_check(table, 1)["valid"]
    assert not citation_check("Office opens at nine [1]. Staff receive 30 days leave.", 1)["valid"]
    assert not citation_check("I cannot determine net pay, but you receive INR 90,000.", 1)["valid"]


def test_worker_process_persists_a_failed_job_without_touching_application_db(tmp_path):
    import os
    import subprocess
    import sys

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from database.base import Base
    from models.enterprise import Enterprise

    url = "sqlite:///" + str(tmp_path / "worker.db")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    source = tmp_path / "uploads/enterprise_1/broken.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"not a PDF")
    with Session(engine) as db:
        db.add(Enterprise(id=1, name="Worker test"))
        db.add(
            Document(
                id=1,
                enterprise_id=1,
                title="broken.pdf",
                file_path=str(source),
                visibility="company",
                index_status="queued",
            )
        )
        db.commit()
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "UPLOAD_DIR": str(tmp_path / "uploads"),
        "INGESTION_TIMEOUT_SECONDS": "30",
    }
    script = Path(__file__).resolve().parents[1] / "scripts/ingestion_worker.py"
    result = subprocess.run(
        [sys.executable, str(script), "--once"], env=env, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    with Session(engine) as db:
        document = db.get(Document, 1)
        assert document.index_status == "failed" and document.index_error
        assert source.exists()
    engine.dispose()


def test_single_citation_revision_is_checked_before_serving(client, account, monkeypatch):
    upload(client, account)
    monkeypatch.setattr(LLMService, "generate", lambda **kwargs: "The office opens at nine.")
    revisions = []

    def repair(question, context, answer):
        revisions.append(answer)
        assert "opens at nine" in context
        return "The office opens at nine [1]."

    monkeypatch.setattr(LLMService, "repair_citations", repair)
    response = client.post(
        "/chat/generate", headers=account, json={"question": "When does the office open?"}
    )
    assert response.json()["answer"] == "The office opens at nine [1]."
    assert response.json()["citation_status"] == "valid"
    assert len(revisions) == 1
    assert response.json()["citations"][0]["marker"] == 1


def test_revision_failure_keeps_unverified_answer_hidden(client, account, monkeypatch):
    upload(client, account)
    monkeypatch.setattr(LLMService, "generate", lambda **kwargs: "Invented amount INR 999.")

    def unavailable(*args):
        raise ProviderUnavailable("Revision unavailable")

    monkeypatch.setattr(LLMService, "repair_citations", unavailable)
    response = client.post("/chat/generate", headers=account, json={"question": "office"})
    assert response.json()["answer"] == UNVERIFIED_ANSWER
    assert response.json()["citation_status"] == "invalid"


def test_natural_absence_answer_is_not_mislabeled_as_bad_citation():
    assert citation_check(
        "None of the provided excerpts contain information about a CEO's private telephone number.",
        2,
    )["valid"]
    assert not citation_check(
        "None of the provided excerpts contain the number. The number is 12345.", 2
    )["valid"]


def test_request_metrics_exclude_questions_and_credentials(client, account, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = client.post(
            "/chat/generate", headers=account, json={"question": "PRIVATE_QUESTION_NOT_FOR_LOGS"}
        )
    assert len(response.headers["X-Request-ID"]) == 32
    assert "route=/chat/generate" in caplog.text
    assert "PRIVATE_QUESTION_NOT_FOR_LOGS" not in caplog.text
    assert account["Authorization"] not in caplog.text

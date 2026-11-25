import json

import pytest

from core.config import settings
from services.llm_service import LLMService


def employee(client, admin, email):
    created = client.post(
        "/users/create_user",
        headers=admin,
        json={"email": email, "password": "test password 123", "role": "employee"},
    )
    assert created.status_code == 200, created.text
    token = client.post(
        "/auth/login", json={"email": email, "password": "test password 123"}
    ).json()["access_token"]
    return created.json()["id"], {"Authorization": f"Bearer {token}"}


def upload(client, admin, title, text, visibility="company", ids=None):
    response = client.post(
        "/documents/upload",
        headers=admin,
        files={"file": (title, text.encode())},
        data={"access": json.dumps({"visibility": visibility, "recipient_ids": ids or []})},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("strategy", ["dense", "bm25", "hybrid", "dense-reranked"])
def test_employee_access_is_applied_before_search_and_file_delivery(
    client, account, monkeypatch, strategy
):
    alice, alice_headers = employee(client, account, "alice@example.com")
    bob, bob_headers = employee(client, account, "bob@example.com")
    if strategy == "dense-reranked":
        import services.retrieval_service as retrieval

        monkeypatch.setattr(settings, "RERANKER_MODE", "cross_encoder")
        monkeypatch.setattr(retrieval, "rerank_chunks", lambda q, rows, model: rows)
        strategy = "dense"
    monkeypatch.setattr(settings, "RETRIEVAL_STRATEGY", strategy)
    public = upload(client, account, "policy.txt", "Policy annual leave for all employees.")
    personal = upload(
        client,
        account,
        "offer.txt",
        "Policy annual leave Alice private salary 555.",
        "personal",
        [alice],
    )
    restricted = upload(
        client, account, "team.txt", "Policy annual leave restricted team.", "restricted", [bob]
    )
    assert {d["id"] for d in client.get("/documents/list", headers=alice_headers).json()} == {
        public["id"],
        personal["id"],
    }
    assert {d["id"] for d in client.get("/documents/list", headers=bob_headers).json()} == {
        public["id"],
        restricted["id"],
    }
    assert client.get(f"/documents/{personal['id']}/file", headers=bob_headers).status_code == 404
    file = client.get(f"/documents/{personal['id']}/file", headers=alice_headers)
    assert "555" in file.text and file.headers["cache-control"] == "no-store"
    seen = []
    monkeypatch.setattr(
        LLMService, "generate", lambda question, context: seen.append(context) or "Answer [1]."
    )
    from services import retrieval_service

    original_search = retrieval_service.stream_candidates
    ranked_inputs = []

    def check_candidates(factory, *args, **kwargs):
        def permitted_rows():
            for row in factory():
                ranked_inputs.append(row.document_id)
                assert row.document_id in {public["id"], restricted["id"]}
                yield row

        return original_search(permitted_rows, *args, **kwargs)

    monkeypatch.setattr(retrieval_service, "stream_candidates", check_candidates)
    result = client.post(
        "/chat/generate", headers=bob_headers, json={"question": "Policy annual leave"}
    )
    assert result.status_code == 200
    assert ranked_inputs
    assert personal["id"] not in result.json()["sources"]
    assert "555" not in seen[0]
    scoped = client.post(
        "/chat/generate",
        headers=alice_headers,
        json={"question": "Policy annual leave", "document_id": personal["id"]},
    )
    assert scoped.json()["sources"] == [personal["id"]]
    blocked = client.post(
        "/chat/generate",
        headers=bob_headers,
        json={"question": "Policy annual leave", "document_id": personal["id"]},
    )
    assert blocked.status_code == 404
    assert "access is unavailable" in blocked.json()["detail"]


def test_admin_changes_and_revocation_and_account_removal(client, account):
    alice, headers = employee(client, account, "alice@example.com")
    doc = upload(
        client, account, "appointment.txt", "Appointment starts Monday.", "personal", [alice]
    )
    url = f"/documents/{doc['id']}/access"
    assert client.patch(url, headers=headers, json={"visibility": "company"}).status_code == 403
    # Re-saving unchanged grants must not cause duplicate-key errors.
    assert (
        client.patch(
            url, headers=account, json={"visibility": "personal", "recipient_ids": [alice]}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            url, headers=account, json={"visibility": "restricted", "recipient_ids": [999999]}
        ).status_code
        == 422
    )
    assert client.get(f"/documents/{doc['id']}/file", headers=headers).status_code == 200
    bob, _ = employee(client, account, "bob@example.com")
    assert (
        client.patch(
            url, headers=account, json={"visibility": "restricted", "recipient_ids": [bob]}
        ).status_code
        == 200
    )
    assert client.get("/documents/list", headers=headers).json() == []
    assert client.get(f"/documents/{doc['id']}/file", headers=headers).status_code == 404
    assert (
        client.post(
            "/chat/generate",
            headers=headers,
            json={"question": "Appointment", "document_id": doc["id"]},
        ).status_code
        == 404
    )
    assert client.delete(f"/users/delete_user/{alice}", headers=account).status_code == 200
    new_id, new_headers = employee(client, account, "alice@example.com")
    assert client.get("/documents/list", headers=new_headers).json() == []
    assert client.get(f"/documents/{doc['id']}/file", headers=new_headers).status_code == 404
    assert (
        client.patch(
            url, headers=account, json={"visibility": "personal", "recipient_ids": [new_id]}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            url, headers=account, json={"visibility": "company", "recipient_ids": []}
        ).status_code
        == 200
    )


def test_foreign_recipients_and_invalid_personal_sharing_rejected(client, account):
    foreign = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Other",
            "email": "foreign@example.com",
            "password": "test password 123",
        },
    ).json()["access_token"]
    foreign_id = client.get("/users/me", headers={"Authorization": f"Bearer {foreign}"}).json()[
        "id"
    ]
    for access in (
        {"visibility": "personal", "recipient_ids": []},
        {"visibility": "personal", "recipient_ids": [foreign_id]},
    ):
        result = client.post(
            "/documents/upload",
            headers=account,
            files={"file": ("offer.txt", b"Private offer")},
            data={"access": json.dumps(access)},
        )
        assert result.status_code == 422
    doc = upload(client, account, "policy.txt", "Company policy.")
    assert (
        client.get(
            f"/documents/{doc['id']}/file", headers={"Authorization": f"Bearer {foreign}"}
        ).status_code
        == 404
    )


def test_selected_pdf_reads_all_text_even_when_query_similarity_is_low(
    client, account, db, monkeypatch
):
    from pathlib import Path

    from sqlalchemy import select

    from models.document_chunk import DocumentChunk
    from services.embedding_service import EmbeddingService

    source = Path(__file__).resolve().parents[1] / "evaluation/sources/offer-letter.pdf"
    pdf = client.post(
        "/documents/upload",
        headers=account,
        files={"file": ("Selected-offer.pdf", source.read_bytes())},
    )
    assert pdf.status_code == 201
    identity = pdf.json()["id"]
    # Emulate the model scores seen in the user's screenshot: selected file
    # vectors would all fail the global similarity gate.
    for chunk in db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == identity)):
        chunk.embedding = [0.1, 1.0, 0.0]
        chunk.embedding_model = "previous:model"
    db.commit()
    foreign = upload(
        client, account, "unselected.txt", "UNSELECTED_SECRET work location elsewhere."
    )
    monkeypatch.setattr(settings, "RETRIEVAL_TOP_K", 1)
    monkeypatch.setattr(settings, "RETRIEVAL_MIN_SIMILARITY", 0.95)
    monkeypatch.setattr(
        EmbeddingService,
        "embed_query",
        lambda *_: pytest.fail("A short selected file needs no query embedding"),
    )
    seen = []

    def answer(question, context):
        seen.append(context)
        assert "Alice Morgan" in context and "monthly gross salary" in context
        assert "UNSELECTED_SECRET" not in context
        return "The selected letter describes an engineering position [1]."

    monkeypatch.setattr(LLMService, "generate", answer)
    response = client.post(
        "/chat/generate",
        headers=account,
        json={"question": "Explain this letter", "document_id": identity},
    )
    assert response.status_code == 200, response.text
    assert response.json()["sources"] == [identity]
    assert foreign["id"] not in response.json()["sources"]
    assert len(seen) == 1 and response.json()["citations"]


def test_scoped_large_file_falls_back_to_search_without_crossing_document_boundary(
    client, account, db, monkeypatch
):
    from sqlalchemy import select

    from core.errors import ProviderUnavailable
    from models.user import User
    from services.embedding_service import EmbeddingService
    from services.retrieval_service import RetrievalService

    text = (
        "General onboarding guidance for employees. " * 10 + "\n\n"
    ) * 8 + "\n\n# Work location\n\nThe assigned work location is the London office."
    selected = upload(client, account, "long-letter.txt", text)
    upload(client, account, "other-letter.txt", "The work location is UNSELECTED_CITY.")
    monkeypatch.setattr(settings, "RETRIEVAL_CONTEXT_CHARACTERS", 300)
    monkeypatch.setattr(settings, "RETRIEVAL_NEIGHBORS", 0)

    def unavailable(*_):
        raise ProviderUnavailable("offline")

    monkeypatch.setattr(EmbeddingService, "embed_query", unavailable)

    user = db.scalar(select(User).where(User.role == "admin"))
    result = RetrievalService.retrieve(
        "London work location", user.enterprise_id, db, user=user, document_id=selected["id"]
    )
    assert result and all(c["document_id"] == selected["id"] for c in result)
    assert any("London office" in c["chunk_text"] for c in result)
    assert all("UNSELECTED_CITY" not in c["chunk_text"] for c in result)


@pytest.mark.parametrize("strategy", ["dense", "bm25", "hybrid"])
def test_selected_document_is_authorized_before_routing_embedding_or_search(
    client, account, db, monkeypatch, strategy
):
    from fastapi import HTTPException
    from sqlalchemy import select

    from models.user import User
    from services import chat_service, retrieval_service
    from services.embedding_service import EmbeddingService

    alice, _ = employee(client, account, "alice.preflight@example.com")
    bob, headers = employee(client, account, "bob.preflight@example.com")
    private = upload(client, account, "private.txt", "PRIVATE_SECRET", "personal", [alice])
    revoked = upload(client, account, "revoked.txt", "REVOKED_SECRET", "personal", [bob])
    assert (
        client.patch(
            f"/documents/{revoked['id']}/access",
            headers=account,
            json={"visibility": "personal", "recipient_ids": [alice]},
        ).status_code
        == 200
    )
    deleted = upload(client, account, "deleted.txt", "DELETED_SECRET")
    token = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Foreign workspace",
            "email": "foreign.preflight@example.com",
            "password": "test password 123",
        },
    ).json()["access_token"]
    foreign = upload(client, {"Authorization": f"Bearer {token}"}, "foreign.txt", "FOREIGN_SECRET")
    assert client.delete(f"/documents/{deleted['id']}", headers=account).status_code == 200
    monkeypatch.setattr(settings, "RETRIEVAL_STRATEGY", strategy)

    def unexpected(*args, **kwargs):
        pytest.fail("An unavailable selected document must be rejected before routing or search")

    monkeypatch.setattr(EmbeddingService, "embed_query", unexpected)
    monkeypatch.setattr(LLMService, "generate", unexpected)
    monkeypatch.setattr(chat_service, "identity_answer", unexpected)
    monkeypatch.setattr(chat_service, "resolve_personal_document", unexpected)
    monkeypatch.setattr(retrieval_service, "stream_candidates", unexpected)
    monkeypatch.setattr(retrieval_service, "context_budget", unexpected)
    expected = None
    user = db.scalar(select(User).where(User.id == bob))
    for identity in [private["id"], revoked["id"], deleted["id"], foreign["id"], 999999]:
        for question in ["Explain this document", "Explain my offer letter", "Who am I?"]:
            response = client.post(
                "/chat/generate",
                headers=headers,
                json={"question": question, "document_id": identity},
            )
            assert response.status_code == 404, response.text
            expected = expected or response.json()
            # Missing/foreign/deleted/forbidden files disclose the same information.
            assert response.json() == expected
        with pytest.raises(HTTPException) as error:
            retrieval_service.RetrievalService.retrieve(
                "Explain this document", user.enterprise_id, db, user=user, document_id=identity
            )
        assert error.value.status_code == 404


@pytest.mark.parametrize(
    "status, message",
    [
        ("queued", "still being prepared"),
        ("indexing", "still being prepared"),
        ("failed", "Upload failed"),
        ("ready", "not ready for questions"),
    ],
)
def test_selected_document_without_chunks_reports_index_state_before_search(
    client, account, db, monkeypatch, status, message
):
    from sqlalchemy import delete

    from models.document import Document
    from models.document_chunk import DocumentChunk
    from services import retrieval_service
    from services.embedding_service import EmbeddingService

    selected = upload(client, account, "not-indexed.txt", "Document processing example.")
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == selected["id"]))
    db.get(Document, selected["id"]).index_status = status
    db.commit()

    def unexpected(*args, **kwargs):
        pytest.fail("An unindexed selected document must not enter search or generation")

    monkeypatch.setattr(EmbeddingService, "embed_query", unexpected)
    monkeypatch.setattr(LLMService, "generate", unexpected)
    monkeypatch.setattr(retrieval_service, "stream_candidates", unexpected)
    monkeypatch.setattr(retrieval_service, "context_budget", unexpected)
    response = client.post(
        "/chat/generate",
        headers=account,
        json={"question": "Explain this document", "document_id": selected["id"]},
    )
    assert response.status_code == 409, response.text
    assert message in response.json()["detail"]


@pytest.mark.parametrize("status", ["queued", "indexing", "failed"])
def test_selected_document_keeps_old_evidence_available_during_reindex(
    client, account, db, monkeypatch, status
):
    from models.document import Document

    selected = upload(client, account, "existing.txt", "Existing indexed evidence is available.")
    db.get(Document, selected["id"]).index_status = status
    db.commit()
    monkeypatch.setattr(LLMService, "generate", lambda question, context: "Existing evidence [1].")
    response = client.post(
        "/chat/generate",
        headers=account,
        json={"question": "Explain this document", "document_id": selected["id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["sources"] == [selected["id"]]

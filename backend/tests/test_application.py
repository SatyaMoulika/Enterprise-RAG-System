from io import BytesIO
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.config import settings
from core.errors import ProviderUnavailable
from models.document import Document
from models.document_chunk import DocumentChunk
from models.enterprise import Enterprise
from models.user import User
from services.document_service import DocumentService
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService
from services.retrieval_service import RetrievalService


def upload(client, account, name="policy.txt", content=b"Our office opens at nine."):
    return client.post("/documents/upload", headers=account, files={"file": (name, content)})


def test_complete_document_lifecycle(client, account, db, monkeypatch):
    document = upload(client, account)
    assert document.status_code == 201, document.text
    identity = document.json()["id"]
    assert "file_path" not in document.json()
    assert len(db.scalars(select(DocumentChunk)).all()) == 1
    assert client.get("/documents/list", headers=account).json()[0]["id"] == identity

    def answer(question, context):
        assert "[1] policy.txt" in context
        assert "opens at nine" in context
        return "The office opens at nine [1]."

    monkeypatch.setattr(LLMService, "generate", answer)
    chat = client.post(
        "/chat/generate", headers=account, json={"question": "When does the office open?"}
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["sources"] == [identity]
    assert chat.json()["citations"][0]["title"] == "policy.txt"
    path = db.get(Document, identity).file_path
    assert client.delete(f"/documents/{identity}", headers=account).status_code == 200
    assert not db.scalars(select(DocumentChunk)).all()
    from pathlib import Path

    assert not Path(path).exists()
    monkeypatch.setattr(
        EmbeddingService,
        "embed_query",
        lambda q: pytest.fail("An empty workspace should not call inference"),
    )
    empty = client.post("/chat/generate", headers=account, json={"question": "When?"})
    assert empty.json()["sources"] == []
    assert empty.json()["citations"] == []


@pytest.mark.parametrize("name", ["../outside.txt", "..\\outside.txt", "/outside.txt", "data.docx"])
def test_invalid_filenames_are_rejected_without_records(client, account, db, name):
    assert upload(client, account, name).status_code == 422
    assert db.scalar(select(Document.id)) is None


@pytest.mark.parametrize(
    "name,content",
    [("empty.txt", b"  \n"), ("binary.txt", b"\xff\xfe"), ("broken.pdf", b"not a pdf")],
)
def test_invalid_content_is_cleaned_up(client, account, db, name, content):
    assert upload(client, account, name, content).status_code == 422
    assert db.scalar(select(Document.id)) is None
    assert list(settings.UPLOAD_DIR.rglob("*.txt")) == []
    assert list(settings.UPLOAD_DIR.rglob("*.pdf")) == []


def test_upload_limit(client, account, db, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 8)
    assert upload(client, account, content=b"too many bytes").status_code == 413
    assert db.scalar(select(Document.id)) is None
    assert list(settings.UPLOAD_DIR.rglob("*.txt")) == []


def test_same_names_use_distinct_storage(client, account, db):
    assert upload(client, account).status_code == 201
    assert upload(client, account).status_code == 201
    paths = db.scalars(select(Document.file_path)).all()
    assert len(set(paths)) == 2


def test_embedding_failure_rolls_back_and_cleans_file(client, account, db, monkeypatch):
    def unavailable(texts):
        raise ProviderUnavailable("Embedding provider unavailable. Try again later.")

    monkeypatch.setattr(EmbeddingService, "embed_texts", unavailable)
    response = upload(client, account)
    assert response.status_code == 503
    assert db.scalar(select(Document.id)) is None
    assert db.scalar(select(DocumentChunk.id)) is None
    assert list(settings.UPLOAD_DIR.rglob("*.txt")) == []


def test_committing_failure_cleans_up(db, client, monkeypatch):
    # Direct service test: emulate an interrupted commit without affecting account fixtures.
    db.add(Enterprise(name="rollback-test"))
    db.commit()
    tenant = db.scalar(select(Enterprise.id))

    def fail():
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(db, "commit", fail)
    with pytest.raises(RuntimeError):
        DocumentService.upload_document(
            db, tenant, SimpleNamespace(filename="test.txt", file=BytesIO(b"test content"))
        )
    assert db.scalar(select(Document.id)) is None
    assert list(settings.UPLOAD_DIR.rglob("*.txt")) == []


def test_tenants_cannot_list_retrieve_or_delete_each_others_documents(
    client, account, db, monkeypatch
):
    first = upload(client, account).json()["id"]
    registration = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Other workspace",
            "email": "other@example.com",
            "password": "other password 123",
        },
    )
    second = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    assert client.get("/documents/list", headers=second).json() == []
    assert client.delete(f"/documents/{first}", headers=second).status_code == 404
    monkeypatch.setattr(
        LLMService,
        "generate",
        lambda *a, **k: pytest.fail("Private text must not reach the answer provider"),
    )
    chat = client.post("/chat/generate", headers=second, json={"question": "What is the policy?"})
    assert chat.json()["sources"] == []


def test_rank_within_tenant_before_top_k(client, account, db):
    owner = db.scalar(select(User))
    other = Enterprise(name="foreign")
    db.add(other)
    db.flush()
    for tenant, vector in [(other.id, [1.0, 0.0, 0.0]), (owner.enterprise_id, [0.9, 0.1, 0.0])]:
        doc = Document(enterprise_id=tenant, title=f"tenant-{tenant}.txt", file_path="unused")
        db.add(doc)
        db.flush()
        db.add(
            DocumentChunk(
                document_id=doc.id,
                enterprise_id=tenant,
                chunk_text="tenant content",
                chunk_index=0,
                embedding=vector,
                embedding_model="ollama:test-embedding",
            )
        )
    db.commit()
    result = RetrievalService.retrieve("test", owner.enterprise_id, db, top_k=1)
    assert len(result) == 1
    assert result[0]["title"] == f"tenant-{owner.enterprise_id}.txt"


def test_wrong_embedding_model_is_not_mixed(client, account, db):
    upload(client, account)
    chunk = db.scalar(select(DocumentChunk))
    chunk.embedding_model = "other:model"
    db.commit()
    owner = db.scalar(select(User))
    assert RetrievalService.retrieve("test", owner.enterprise_id, db) == []


def test_capacity_limit_is_explicit(client, account, monkeypatch):
    upload(client, account)
    upload(client, account)
    monkeypatch.setattr(settings, "MAX_RETRIEVAL_CHUNKS", 1)
    response = client.post("/chat/generate", headers=account, json={"question": "test"})
    assert response.status_code == 503


def test_employee_cannot_upload_or_delete(client, account):
    created = client.post(
        "/users/create_user",
        headers=account,
        json={"email": "staff@example.com", "password": "employee password", "role": "employee"},
    )
    assert created.status_code == 200, created.text
    token = client.post(
        "/auth/login", json={"email": "staff@example.com", "password": "employee password"}
    ).json()["access_token"]
    employee = {"Authorization": f"Bearer {token}"}
    assert upload(client, employee).status_code == 403
    assert client.delete("/documents/1", headers=employee).status_code == 403


def test_deactivated_user_cannot_reuse_token(client, account, db):
    user = db.scalar(select(User))
    user.is_active = False
    db.commit()
    assert client.get("/users/me", headers=account).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": user.email, "password": "test password 123"}
        ).status_code
        == 401
    )


def test_duplicate_registration_is_atomic(client, account, db):
    response = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Example workspace",
            "email": "different@example.com",
            "password": "test password 123",
        },
    )
    assert response.status_code == 400
    assert len(db.scalars(select(Enterprise)).all()) == 1
    assert len(db.scalars(select(User)).all()) == 1


@pytest.mark.parametrize("question", ["", "   ", "a" * 2001])
def test_invalid_questions(client, account, question):
    assert (
        client.post("/chat/generate", headers=account, json={"question": question}).status_code
        == 422
    )


def test_auth_is_required(client):
    assert client.get("/documents/list").status_code == 401
    assert client.post("/chat/generate", json={"question": "test"}).status_code == 401


def test_no_provider_call_for_health(client):
    assert client.get("/health").json() == {"status": "healthy"}

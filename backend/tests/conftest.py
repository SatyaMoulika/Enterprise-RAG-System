"""Tests always use disposable SQLite; never read or mutate a development database."""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-never-use-in-production-123456"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import settings
from database.base import Base
from database.session import get_db
from main import app
from models.document import Document  # noqa: F401
from models.document_chunk import DocumentChunk  # noqa: F401
from models.enterprise import Enterprise  # noqa: F401
from models.user import User  # noqa: F401
from services.embedding_service import EmbeddingService


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)
    monkeypatch.setattr(settings, "EMBEDDING_BACKEND", "ollama")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "test-embedding")
    monkeypatch.setattr(
        EmbeddingService, "embed_texts", lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
    )
    monkeypatch.setattr(EmbeddingService, "embed_query", lambda query: [1.0, 0.0, 0.0])

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    response = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Example workspace",
            "email": "owner@example.com",
            "password": "test password 123",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

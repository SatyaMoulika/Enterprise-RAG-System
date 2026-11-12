"""Smoke-check only a newly created, explicitly disposable local PostgreSQL database."""

import argparse
import os
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

parser = argparse.ArgumentParser()
parser.add_argument("--database-url", required=True)
parser.add_argument("--confirm-disposable", action="store_true")
args = parser.parse_args()
url = make_url(args.database_url)
if (
    not args.confirm_disposable
    or url.host not in {"127.0.0.1", "localhost"}
    or url.database != "rag_release_test"
):
    parser.error("Use --confirm-disposable with an empty local database named rag_release_test")
probe = create_engine(args.database_url)
if inspect(probe).get_table_names():
    raise SystemExit("Refusing to test a database that already has tables")
probe.dispose()

os.environ["DATABASE_URL"] = args.database_url
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
os.environ["EMBEDDING_DIMENSION"] = "3"
os.environ["EMBEDDING_MODEL"] = "disposable-test-model"
os.environ["EMBEDDING_BACKEND"] = "ollama"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from core.config import settings  # noqa: E402
from database.session import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402
from services.embedding_service import EmbeddingService  # noqa: E402
from services.llm_service import LLMService  # noqa: E402
from services.user_service import UserService  # noqa: E402

config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
command.upgrade(config, "head")
command.check(config)
with TemporaryDirectory(prefix="rag-postgres-test-") as directory:
    settings.UPLOAD_DIR = Path(directory)
    with (
        patch.object(
            EmbeddingService,
            "embed_texts",
            side_effect=lambda texts: [[1.0, 0.0, 0.0] for _ in texts],
        ),
        patch.object(EmbeddingService, "embed_query", return_value=[1.0, 0.0, 0.0]),
        patch.object(LLMService, "generate", return_value="The office opens at nine [1]."),
        TestClient(app) as client,
    ):
        assert client.get("/ready").status_code == 200
        user = client.post(
            "/auth/register",
            json={
                "enterprise_name": "Postgres smoke",
                "email": "owner@example.com",
                "password": "test-only-password",
            },
        )
        assert user.status_code == 201, user.text
        headers = {"Authorization": f"Bearer {user.json()['access_token']}"}
        document = client.post(
            "/documents/upload",
            headers=headers,
            files={"file": ("policy.txt", b"The office opens at nine.")},
        )
        assert document.status_code == 201, document.text
        identity = document.json()["id"]
        chat = client.post(
            "/chat/generate", headers=headers, json={"question": "When does the office open?"}
        )
        assert chat.status_code == 200, chat.text
        assert chat.json()["citations"][0]["document_id"] == identity
        other = client.post(
            "/auth/register",
            json={
                "enterprise_name": "Isolated",
                "email": "other@example.com",
                "password": "test-only-password",
            },
        )
        other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
        assert client.get("/documents/list", headers=other_headers).json() == []
        assert client.delete(f"/documents/{identity}", headers=other_headers).status_code == 404
        assert client.delete(f"/documents/{identity}", headers=headers).status_code == 200
        assert (
            client.post("/chat/generate", headers=headers, json={"question": "When?"}).json()[
                "sources"
            ]
            == []
        )
        # Two active administrators attempt to remove each other concurrently.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from sqlalchemy import select

        owner = client.get("/users/me", headers=headers).json()
        teammate = client.post(
            "/users/create_user",
            headers=headers,
            json={
                "email": "admin-team@example.com",
                "password": "test-only-password",
                "role": "admin",
            },
        )
        assert teammate.status_code == 200, teammate.text
        second_token = client.post(
            "/auth/login",
            json={"email": "admin-team@example.com", "password": "test-only-password"},
        ).json()["access_token"]
        ids = [owner["id"], teammate.json()["id"]]
        tokens = {ids[0]: headers, ids[1]: {"Authorization": f"Bearer {second_token}"}}
        barrier = Barrier(2)

        def mutual_removal(actor_id, target_id):
            with SessionLocal() as db:
                actor = db.get(User, actor_id)
                barrier.wait(timeout=5)
                try:
                    assert UserService.delete_user(db, target_id, actor)
                    return "removed"
                except PermissionError:
                    db.rollback()
                    return "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(mutual_removal, ids[0], ids[1]),
                pool.submit(mutual_removal, ids[1], ids[0]),
            ]
            outcomes = [future.result(timeout=15) for future in futures]
        assert sorted(outcomes) == ["denied", "removed"], outcomes
        with SessionLocal() as db:
            survivors = db.scalars(
                select(User).where(
                    User.enterprise_id == owner["enterprise_id"],
                    User.role == "admin",
                    User.is_active.is_(True),
                )
            ).all()
            assert len(survivors) == 1
            survivor_id = survivors[0].id
        removed_id = next(identity for identity in ids if identity != survivor_id)
        assert client.get("/users/me", headers=tokens[removed_id]).status_code == 401
        assert client.get("/users/me", headers=tokens[survivor_id]).status_code == 200
command.downgrade(config, "base")
engine.dispose()
print(
    "PostgreSQL smoke passed: migrations/schema parity, readiness, registration, upload, JSON vectors, citation retrieval, tenant isolation, deletion and concurrent administrator removal protection. Inference was mocked."
)

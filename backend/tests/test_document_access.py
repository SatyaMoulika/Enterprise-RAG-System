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
    result = client.post(
        "/chat/generate", headers=bob_headers, json={"question": "Policy annual leave"}
    )
    assert result.status_code == 200
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
    assert blocked.json()["sources"] == []


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
        ).json()["sources"]
        == []
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

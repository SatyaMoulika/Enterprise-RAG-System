def test_profile_and_password(client, account):
    result = client.patch(
        "/users/me", headers=account, json={"name": "Alice Morgan", "profile_photo": None}
    )
    assert result.status_code == 200
    assert result.json()["name"] == "Alice Morgan"
    assert (
        client.post(
            "/users/me/password",
            headers=account,
            json={"current_password": "wrong", "password": "new password 123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/users/me/password",
            headers=account,
            json={"current_password": "test password 123", "password": "new password 123"},
        ).status_code
        == 200
    )
    assert client.get("/users/me", headers=account).status_code == 401
    assert (
        client.post(
            "/auth/login", json={"email": "owner@example.com", "password": "new password 123"}
        ).status_code
        == 200
    )


def test_member_edit_scoped_and_photo_validation(client, account, db):
    result = client.post(
        "/users/create_user",
        headers=account,
        json={"email": "alice@example.com", "password": "employee password", "role": "employee"},
    )
    identity = result.json()["id"]
    assert (
        client.patch(
            f"/users/{identity}",
            headers=account,
            json={"name": "Alice", "email": "alice.new@example.com"},
        ).status_code
        == 200
    )
    token = client.post(
        "/auth/login", json={"email": "alice.new@example.com", "password": "employee password"}
    ).json()["access_token"]
    employee = {"Authorization": "Bearer " + token}
    assert (
        client.patch(
            "/users/1", headers=employee, json={"name": "Override", "email": "override@example.com"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/users/99999",
            headers=account,
            json={"name": "Override", "email": "override@example.com"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/users/me",
            headers=employee,
            json={"name": "Alice", "profile_photo": "data:image/svg+xml;base64,AAAA"},
        ).status_code
        == 422
    )


def test_photo_is_persisted_removed_and_profile_update_cannot_change_role(client, account):
    import base64

    photo = (
        "data:image/png;base64,"
        + base64.b64encode(bytes.fromhex("89504e470d0a1a0a") + b"photo-fixture").decode()
    )
    response = client.patch(
        "/users/me", headers=account, json={"name": "Alice", "profile_photo": photo}
    )
    assert response.status_code == 200
    assert client.get("/users/me", headers=account).json()["profile_photo"] == photo
    response = client.patch(
        "/users/me", headers=account, json={"name": "Alice Updated", "role": "employee"}
    )
    assert response.json()["profile_photo"] == photo
    assert response.json()["role"] == "admin"
    assert (
        client.patch(
            "/users/me", headers=account, json={"name": "Alice", "profile_photo": None}
        ).json()["profile_photo"]
        is None
    )


def test_member_edit_rejects_foreign_workspace_and_duplicate_emails(client, account):
    foreign = client.post(
        "/auth/register",
        json={
            "enterprise_name": "Foreign",
            "email": "foreign@example.com",
            "password": "foreign password 123",
        },
    ).json()
    foreign_headers = {"Authorization": "Bearer " + foreign["access_token"]}
    foreign_user = client.get("/users/me", headers=foreign_headers).json()
    denied = client.patch(
        "/users/" + str(foreign_user["id"]),
        headers=account,
        json={"name": "Override", "email": "overridden@example.com"},
    )
    assert denied.status_code == 404
    assert client.get("/users/me", headers=foreign_headers).json()["email"] == "foreign@example.com"
    owner = client.get("/users/me", headers=account).json()
    duplicate = client.patch(
        "/users/" + str(owner["id"]),
        headers=account,
        json={"name": "Changed", "email": "foreign@example.com"},
    )
    assert duplicate.status_code == 409
    assert client.get("/users/me", headers=account).json()["email"] == "owner@example.com"

import requests

BASE_URL = "http://localhost:8000"


def get_headers(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def get_me(token):
    return requests.get(
        f"{BASE_URL}/users/me",
        headers=get_headers(token)
    )


def get_all_users(token):
    return requests.get(
        f"{BASE_URL}/users/get_all_users",
        headers=get_headers(token)
    )


def create_user(token, email, password, role):
    return requests.post(
        f"{BASE_URL}/users/create_user",
        headers=get_headers(token),
        json={
            "email": email,
            "password": password,
            "role": role
        }
    )


def delete_user(token, user_id):
    return requests.delete(
        f"{BASE_URL}/users/delete_user/{user_id}",
        headers=get_headers(token)
    )
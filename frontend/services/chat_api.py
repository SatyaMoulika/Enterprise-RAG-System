import requests

BASE_URL = "http://localhost:8000"


def ask_question(
    token,
    question
):

    return requests.post(
        f"{BASE_URL}/chat/generate",
        headers={
            "Authorization":
            f"Bearer {token}"
        },
        json={
            "question": question
        }
    )
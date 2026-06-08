import requests

BASE_URL = "http://localhost:8000"


def login(email: str, password: str):

    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": email,
            "password": password
        }
    )

    return response


def register(
    enterprise_name: str,
    email: str,
    password: str
):

    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "enterprise_name": enterprise_name,
            "email": email,
            "password": password
        }
    )

    return response


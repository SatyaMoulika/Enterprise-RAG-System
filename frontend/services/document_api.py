import requests

BASE_URL = "http://localhost:8000"


def get_headers(token):
    return {
        "Authorization": f"Bearer {token}"
    }


def upload_document(token, file):

    files = {
        "file": (
            file.name,
            file.getvalue()
        )
    }

    return requests.post(
        f"{BASE_URL}/documents/upload",
        headers=get_headers(token),
        files=files
    )


def get_documents(token):

    return requests.get(
        f"{BASE_URL}/documents/list",
        headers=get_headers(token)
    )


def delete_document(
    token,
    document_id
):

    return requests.delete(
        f"{BASE_URL}/documents/{document_id}",
        headers=get_headers(token)
    )
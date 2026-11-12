import httpx
import pytest

from core.config import settings
from core.errors import ProviderUnavailable
from services.embedding_service import EmbeddingService
from services.llm_service import LLMService


def response(payload, status=200):
    return httpx.Response(
        status, json=payload, request=httpx.Request("POST", "http://inference.invalid")
    )


def test_embedding_http_contract_and_timeout(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 3)

    def post(url, **kwargs):
        assert url.endswith("/api/embed")
        assert kwargs["timeout"] > 0
        assert kwargs["json"]["input"] == ["text"]
        return response({"embeddings": [[1.0, 0.0, 0.0]]})

    monkeypatch.setattr(httpx, "post", post)
    assert EmbeddingService.embed_query("text") == [1.0, 0.0, 0.0]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"embeddings": []},
        {"embeddings": [[1]]},
        {"embeddings": [[0] * 384]},
        {"embeddings": [["not a number"] * 384]},
    ],
)
def test_embedding_provider_invalid_payload_is_sanitized(monkeypatch, payload):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: response(payload))
    with pytest.raises(ProviderUnavailable, match="Embedding provider unavailable"):
        EmbeddingService.embed_query("test")


def test_provider_timeout_is_sanitized(monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ReadTimeout("private upstream details")

    monkeypatch.setattr(httpx, "post", unavailable)
    with pytest.raises(ProviderUnavailable, match="Answer provider unavailable") as exc:
        LLMService.generate("question", "context")
    assert "private upstream details" not in str(exc.value)


def test_chat_instructions_and_response(monkeypatch):
    def post(url, **kwargs):
        assert url.endswith("/api/chat")
        messages = kwargs["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert "untrusted" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        return response({"message": {"content": "Supported answer [1]."}})

    monkeypatch.setattr(httpx, "post", post)
    assert LLMService.generate("test", "context") == "Supported answer [1]."

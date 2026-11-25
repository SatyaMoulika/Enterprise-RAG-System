import httpx
import pytest

from core.config import settings
from core.errors import ProviderUnavailable
from services.embedding_service import EmbeddingService
from services.generation_protocol import chat_payload
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
        assert kwargs["json"] == chat_payload(
            "test",
            "context",
            settings.OLLAMA_CHAT_MODEL,
            temperature=settings.GENERATION_TEMPERATURE,
            structured=True,
        )
        assert kwargs["json"]["options"]["num_ctx"] == settings.GENERATION_CONTEXT_TOKENS
        messages = kwargs["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert "untrusted" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        return response(
            {"message": {"content": '{"sentences":[{"text":"Supported answer.","sources":[1]}]}'}}
        )

    monkeypatch.setattr(httpx, "post", post)
    assert LLMService.generate("test", "context") == "Supported answer. [1]"


def test_context_keeps_citation_mapping_without_internal_chunk_labels():
    from services.prompt_service import PromptService

    value = PromptService.build_context(
        [
            {"title": "Offer.pdf", "chunk_index": 0, "chunk_text": "Your role is AI Engineer."},
            {"title": "Appointment.pdf", "chunk_index": 12, "chunk_text": "Your manager is Maya."},
        ]
    )
    assert value == (
        "[1] Offer.pdf\nYour role is AI Engineer.\n\n[2] Appointment.pdf\nYour manager is Maya."
    )
    assert "(chunk" not in value


def test_structured_sources_are_rendered_for_each_sentence_and_preserve_citation_identity(
    monkeypatch,
):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: response(
            {
                "message": {
                    "content": '{"sentences":[{"text":"Remote work requires approval. Onsite roles are excluded.","sources":[2,2]}]}'
                }
            }
        ),
    )
    assert (
        LLMService.generate("remote work?", "context")
        == "Remote work requires approval. [2]\n\nOnsite roles are excluded. [2]"
    )


@pytest.mark.parametrize(
    "content",
    [
        "not JSON",
        '{"sentences":[]}',
        '{"sentences":[{"text":"Claim.","sources":[true]}]}',
        '{"sentences":[{"text":"Claim.","sources":[0]}]}',
    ],
)
def test_invalid_structured_answers_fail_explicitly(monkeypatch, content):
    monkeypatch.setattr(
        httpx, "post", lambda *args, **kwargs: response({"message": {"content": content}})
    )
    with pytest.raises(ProviderUnavailable):
        LLMService.generate("question", "context")

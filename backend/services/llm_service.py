import json

import httpx

from core.config import settings
from core.errors import ProviderUnavailable
from services.chunking_service import _sentences
from services.generation_protocol import chat_payload, prompt_size


class LLMService:
    @classmethod
    def repair_citations(cls, question: str, context: str, answer: str) -> str:
        payload = chat_payload(
            question,
            context,
            settings.OLLAMA_CHAT_MODEL,
            temperature=0,
            context_tokens=settings.GENERATION_CONTEXT_TOKENS,
            answer_tokens=settings.GENERATION_MAX_TOKENS,
            structured=True,
        )
        payload["messages"].extend(
            [
                {"role": "assistant", "content": answer},
                {
                    "role": "user",
                    "content": "Rewrite your answer using only the original excerpts. Give the direct answer without introductory text. Every factual sentence, including the final conclusion, must end with the supporting excerpt number [n]. Verify each reference against the excerpt text; never invent a citation. Remove unsupported claims. Preserve all qualifications and exceptions. If no excerpt answers the question, return exactly: I could not find the answer in the provided documents.",
                },
            ]
        )
        if (
            prompt_size(payload) + settings.GENERATION_MAX_TOKENS + 256
            > settings.GENERATION_CONTEXT_TOKENS
        ):
            raise ProviderUnavailable("Citation revision exceeds the model context budget")
        return cls._request(payload, timeout=min(settings.PROVIDER_TIMEOUT_SECONDS, 20))

    @classmethod
    def generate(cls, question: str, context: str) -> str:
        try:
            payload = chat_payload(
                question,
                context,
                settings.OLLAMA_CHAT_MODEL,
                temperature=settings.GENERATION_TEMPERATURE,
                context_tokens=settings.GENERATION_CONTEXT_TOKENS,
                answer_tokens=settings.GENERATION_MAX_TOKENS,
                structured=True,
            )
        except ValueError as exc:
            raise ProviderUnavailable("Answer exceeds the model context budget") from exc
        return cls._request(payload)

    @classmethod
    def _request(cls, payload, timeout=None) -> str:
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json=payload,
                timeout=settings.PROVIDER_TIMEOUT_SECONDS if timeout is None else timeout,
            )
            response.raise_for_status()
            answer = response.json()["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty answer")
            if payload.get("format"):
                sentences = json.loads(answer)["sentences"]
                if not isinstance(sentences, list) or not 1 <= len(sentences) <= 20:
                    raise ValueError("Invalid structured answer")
                rendered = []
                for sentence in sentences:
                    text, sources = sentence["text"], sentence["sources"]
                    if (
                        not isinstance(text, str)
                        or not text.strip()
                        or not isinstance(sources, list)
                        or any(type(source) is not int or source < 1 for source in sources)
                    ):
                        raise ValueError("Invalid structured answer sentence")
                    markers = " ".join(f"[{source}]" for source in dict.fromkeys(sources))
                    rendered.extend(
                        sentence + (" " + markers if markers else "")
                        for sentence in _sentences(text.strip())
                    )
                answer = "\n\n".join(rendered)
            return answer.strip()
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise ProviderUnavailable("Answer provider unavailable. Try again later.") from exc

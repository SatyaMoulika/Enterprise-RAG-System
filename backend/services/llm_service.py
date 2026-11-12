import httpx

from core.config import settings
from core.errors import ProviderUnavailable
from services.generation_protocol import chat_payload


class LLMService:
    @classmethod
    def generate(cls, question: str, context: str) -> str:
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat",
                json=chat_payload(question, context, settings.OLLAMA_CHAT_MODEL),
                timeout=settings.PROVIDER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            answer = response.json()["message"]["content"]
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError("Empty answer")
            return answer.strip()
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise ProviderUnavailable("Answer provider unavailable. Try again later.") from exc

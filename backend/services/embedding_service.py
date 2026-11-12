import math
from functools import lru_cache

import httpx

from core.config import settings
from core.errors import ProviderUnavailable


@lru_cache(maxsize=1)
def _local_model():
    # Optional backend: importing the API never downloads model weights.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.EMBEDDING_MODEL)


class EmbeddingService:
    @classmethod
    def embed_texts(cls, texts: list[str]) -> list[list[float]]:
        try:
            if settings.EMBEDDING_BACKEND == "sentence_transformers":
                raw = _local_model().encode(texts, convert_to_numpy=True).tolist()
            else:
                response = httpx.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed",
                    json={"model": settings.EMBEDDING_MODEL, "input": texts},
                    timeout=settings.PROVIDER_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                raw = response.json()["embeddings"]
            vectors = [[float(value) for value in vector] for vector in raw]
            if len(vectors) != len(texts) or any(
                len(v) != settings.EMBEDDING_DIMENSION
                or not all(math.isfinite(x) for x in v)
                or not any(v)
                for v in vectors
            ):
                raise ValueError("Invalid embeddings")
            return vectors
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ImportError, RuntimeError) as exc:
            raise ProviderUnavailable("Embedding provider unavailable. Try again later.") from exc

    @classmethod
    def embed_query(cls, query: str) -> list[float]:
        return cls.embed_texts([query])[0]

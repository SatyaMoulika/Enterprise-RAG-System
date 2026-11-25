import math
from functools import lru_cache

import httpx

from core.config import settings
from core.errors import InvalidDocument, ProviderUnavailable


@lru_cache(maxsize=1)
def _local_model(model_name, revision):
    # Optional backend: importing the API never downloads model weights.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, revision=revision or None)


def _verify_ollama_revision():
    if not settings.EMBEDDING_REVISION:
        return
    response = httpx.get(
        f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags",
        timeout=settings.PROVIDER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    name = settings.EMBEDDING_MODEL
    if ":" not in name.rsplit("/", 1)[-1]:
        name += ":latest"
    matches = [
        model
        for model in response.json()["models"]
        if model.get("name") == name or model.get("model") == name
    ]
    if len(matches) != 1 or matches[0].get("digest", "").removeprefix(
        "sha256:"
    ) != settings.EMBEDDING_REVISION.removeprefix("sha256:"):
        raise ProviderUnavailable(
            "Embedding model revision differs from EMBEDDING_REVISION; restore the pinned model or reindex with the new revision"
        )


class EmbeddingService:
    @classmethod
    def embed_texts(cls, texts: list[str]) -> list[list[float]]:
        try:
            if settings.EMBEDDING_BACKEND == "sentence_transformers":
                model = _local_model(settings.EMBEDDING_MODEL, settings.EMBEDDING_REVISION)
                if any(len(model.tokenizer.encode(text)) > model.max_seq_length for text in texts):
                    raise InvalidDocument(
                        "Text exceeds the embedding model token limit; reduce CHUNK_MAX_CHARACTERS and reindex"
                    )
                raw = model.encode(texts, convert_to_numpy=True).tolist()
            else:
                _verify_ollama_revision()
                response = httpx.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed",
                    json={"model": settings.EMBEDDING_MODEL, "input": texts, "truncate": False},
                    timeout=settings.PROVIDER_TIMEOUT_SECONDS,
                )
                if response.status_code == 400 and "context length" in response.text.lower():
                    raise InvalidDocument(
                        "Text exceeds the embedding model token limit; reduce CHUNK_MAX_CHARACTERS and reindex"
                    )
                response.raise_for_status()
                raw = response.json()["embeddings"]
                _verify_ollama_revision()
            vectors = [[float(value) for value in vector] for vector in raw]
            if len(vectors) != len(texts) or any(
                len(v) != settings.EMBEDDING_DIMENSION
                or not all(math.isfinite(x) for x in v)
                or not any(v)
                for v in vectors
            ):
                raise ValueError("Invalid embeddings")
            return vectors
        except (InvalidDocument, ProviderUnavailable):
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, ImportError, RuntimeError) as exc:
            raise ProviderUnavailable("Embedding provider unavailable. Try again later.") from exc

    @classmethod
    def embed_query(cls, query: str) -> list[float]:
        return cls.embed_texts([query])[0]

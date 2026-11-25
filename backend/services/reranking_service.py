"""Optional CPU cross-encoder stage. Disabled unless configured; no import-time downloads."""

import math
from functools import lru_cache
from threading import Lock

from core.errors import ProviderUnavailable
from services.search import SearchChunk

_lock = Lock()


@lru_cache(maxsize=1)
def _load_cross_encoder(model_name: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name, max_length=512, device="cpu")


def rerank_chunks(question: str, chunks: list[SearchChunk], model_name: str) -> list[SearchChunk]:
    if not chunks:
        return []
    if not _lock.acquire(blocking=False):
        raise ProviderUnavailable("Re-ranking is busy. Try again later.")
    try:
        model = _load_cross_encoder(model_name)
        pairs = []
        owners = []
        tokenizer = model.tokenizer
        query_tokens = tokenizer.encode(question, add_special_tokens=False)
        # Reject an oversized question rather than silently dropping part of it.
        available = 512 - len(query_tokens) - tokenizer.num_special_tokens_to_add(pair=True)
        if available < 32:
            raise ValueError("Question exceeds the reranker token budget")
        for index, chunk in enumerate(chunks):
            encoded = tokenizer.encode(chunk.chunk_text, add_special_tokens=False)
            for start in range(0, len(encoded), max(1, available - 32)):
                pairs.append((question, tokenizer.decode(encoded[start : start + available])))
                owners.append(index)
        scores = [
            float(score) for score in model.predict(pairs, batch_size=8, show_progress_bar=False)
        ]
        if len(scores) != len(pairs) or not all(math.isfinite(score) for score in scores):
            raise ValueError("Invalid re-ranking scores")
        maxima = [float("-inf")] * len(chunks)
        for owner, score in zip(owners, scores, strict=True):
            maxima[owner] = max(maxima[owner], score)
        # Logits determine order only. They are not probabilities or calibrated evidence thresholds.
        return [
            chunk
            for _, chunk in sorted(
                zip(maxima, chunks, strict=True), key=lambda item: (-item[0], item[1].id)
            )
        ]
    except Exception as exc:
        raise ProviderUnavailable(
            "Re-ranking unavailable. Check the optional dependency and model configuration."
        ) from exc
    finally:
        _lock.release()

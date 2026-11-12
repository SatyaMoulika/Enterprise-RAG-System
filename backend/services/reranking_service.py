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
        scores = [
            float(score)
            for score in model.predict(
                [(question, c.chunk_text) for c in chunks], batch_size=8, show_progress_bar=False
            )
        ]
        if len(scores) != len(chunks) or not all(math.isfinite(score) for score in scores):
            raise ValueError("Invalid re-ranking scores")
        # Logits determine order only. They are not probabilities or calibrated evidence thresholds.
        return [
            chunk
            for _, chunk in sorted(
                zip(scores, chunks, strict=True), key=lambda item: (-item[0], item[1].id)
            )
        ]
    except Exception as exc:
        raise ProviderUnavailable(
            "Re-ranking unavailable. Check the optional dependency and model configuration."
        ) from exc
    finally:
        _lock.release()

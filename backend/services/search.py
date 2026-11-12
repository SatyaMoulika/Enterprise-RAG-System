"""Pure, deterministic retrieval primitives; no database, provider calls or hidden caches."""

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from services.prompt_service import PromptService

Strategy = Literal["dense", "bm25", "hybrid"]
_STOP = frozenset(
    "a an and are as at be by can could did do does for from had has have how i in into is it its me my of on or our should tell that the their them there these they this to us was we were what when where which who why will with would you your".split()
)


@dataclass(frozen=True)
class SearchChunk:
    id: int
    document_id: int
    title: str
    chunk_index: int
    chunk_text: str
    embedding: list[float] | None = None

    def context(self) -> dict:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
        }


def tokens(text: str) -> list[str]:
    result = []
    for token in re.findall(r"[^\W_]+(?:[-_.][^\W_]+)*", text.casefold(), re.UNICODE):
        if token not in _STOP:
            result.append(token)
        if re.search(r"[-_.]", token):
            result.extend(part for part in re.split(r"[-_.]", token) if part and part not in _STOP)
    return result


def dense_rank(chunks: list[SearchChunk], query: list[float], limit: int) -> list[int]:
    if not query or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in query):
        return []
    query_norm = math.hypot(*query)
    if not query_norm or not math.isfinite(query_norm):
        return []
    normalized = [x / query_norm for x in query]
    scored = []
    for chunk in chunks:
        vector = chunk.embedding
        if (
            not isinstance(vector, list)
            or len(vector) != len(query)
            or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector)
        ):
            continue
        norm = math.hypot(*vector)
        if not norm or not math.isfinite(norm):
            continue
        score = sum(a * (b / norm) for a, b in zip(normalized, vector, strict=True))
        scored.append((score, chunk.id))
    return [
        identity
        for _, identity in heapq.nlargest(limit, scored, key=lambda item: (item[0], -item[1]))
    ]


def bm25_rank(chunks: list[SearchChunk], question: str, limit: int) -> list[int]:
    """BM25 with positive Robertson IDF, k1=1.2 and b=0.75; only lexical matches rank."""
    terms = set(tokens(question))
    if not chunks or not terms:
        return []
    documents = [Counter(tokens(chunk.title + " " + chunk.chunk_text)) for chunk in chunks]
    lengths = [sum(document.values()) for document in documents]
    average = sum(lengths) / len(lengths) or 1
    frequency = Counter(term for document in documents for term in terms if term in document)
    scored = []
    for chunk, document, length in zip(chunks, documents, lengths, strict=True):
        score = 0.0
        for term in sorted(terms):
            tf = document.get(term, 0)
            if tf:
                idf = math.log1p((len(chunks) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
        if score > 0:
            scored.append((score, chunk.id))
    return [
        identity
        for _, identity in heapq.nlargest(limit, scored, key=lambda item: (item[0], -item[1]))
    ]


def reciprocal_rank_fusion(rankings: list[list[int]], constant: int = 60) -> list[int]:
    scores: Counter[int] = Counter()
    for ranking in rankings:
        # An item contributes once per ranker, even if a caller accidentally repeats it.
        seen = set()
        for rank, identity in enumerate(ranking, start=1):
            if identity not in seen:
                scores[identity] += 1 / (constant + rank)
                seen.add(identity)
    return sorted(scores, key=lambda identity: (-scores[identity], identity))


def retrieve_ranked(
    chunks: list[SearchChunk],
    question: str,
    query: list[float] | None,
    *,
    strategy: Strategy = "dense",
    top_k: int = 5,
    candidate_k: int = 20,
    context_characters: int = 24_000,
) -> list[SearchChunk]:
    if strategy not in {"dense", "bm25", "hybrid"}:
        raise ValueError("Unsupported retrieval strategy")
    if top_k < 1 or candidate_k < top_k or context_characters < 1:
        raise ValueError("Invalid retrieval limits")
    dense = dense_rank(chunks, query or [], candidate_k) if strategy != "bm25" else []
    lexical = bm25_rank(chunks, question, candidate_k) if strategy != "dense" else []
    ranking = (
        reciprocal_rank_fusion([dense, lexical])
        if strategy == "hybrid"
        else dense
        if strategy == "dense"
        else lexical
    )
    by_id = {chunk.id: chunk for chunk in chunks}
    selected: list[SearchChunk] = []
    seen = set()
    for identity in ranking:
        chunk = by_id[identity]
        key = (chunk.document_id, " ".join(chunk.chunk_text.casefold().split()))
        if key in seen:
            continue
        # Budget the serialized prompt context, preserving whole excerpt boundaries.
        if (
            len(PromptService.build_context([c.context() for c in [*selected, chunk]]))
            > context_characters
        ):
            continue
        seen.add(key)
        selected.append(chunk)
        if len(selected) == top_k:
            break
    return selected

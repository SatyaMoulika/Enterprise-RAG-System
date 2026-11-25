"""Pure, deterministic retrieval primitives; no database, provider calls or hidden caches."""

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
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
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    section_key: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    dense_score: float | None = None
    lexical_score: float | None = None
    chunk_end_index: int | None = None

    def context(self) -> dict:
        result = {
            "document_id": self.document_id,
            "title": self.title,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
        }
        for name in (
            "page_start",
            "page_end",
            "section",
            "section_key",
            "start_offset",
            "end_offset",
            "dense_score",
            "lexical_score",
            "chunk_end_index",
        ):
            if (value := getattr(self, name)) is not None:
                result[name] = value
        return result


def cosine_score(vector, query):
    if not vector or not query or len(vector) != len(query):
        return None
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in [*vector, *query]):
        return None
    left, right = math.hypot(*vector), math.hypot(*query)
    if not left or not right or not math.isfinite(left) or not math.isfinite(right):
        return None
    return sum((a / left) * (b / right) for a, b in zip(vector, query, strict=True))


def tokens(text: str) -> list[str]:
    result = []
    for token in re.findall(r"[^\W_]+(?:[-_.][^\W_]+)*", text.casefold(), re.UNICODE):
        if token not in _STOP:
            result.append(token)
        if re.search(r"[-_.]", token):
            result.extend(part for part in re.split(r"[-_.]", token) if part and part not in _STOP)
    return result


def dense_rank(
    chunks: list[SearchChunk], query: list[float], limit: int, min_similarity=0.0
) -> list[int]:
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
        if score > min_similarity:
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
    documents = [
        Counter(tokens(chunk.title + " " + (chunk.section or "") + " " + chunk.chunk_text))
        for chunk in chunks
    ]
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


def rank_candidates(
    chunks: list[SearchChunk],
    question: str,
    query: list[float] | None,
    *,
    strategy: Strategy = "dense",
    candidate_k: int = 20,
    min_similarity: float = 0.0,
) -> list[SearchChunk]:
    if strategy not in {"dense", "bm25", "hybrid"} or candidate_k < 1:
        raise ValueError("Invalid retrieval strategy or candidate limit")
    return stream_candidates(
        lambda: iter(chunks),
        question,
        query,
        strategy=strategy,
        candidate_k=candidate_k,
        min_similarity=min_similarity,
    )


def select_context(
    ranked: list[SearchChunk],
    *,
    top_k: int = 5,
    context_characters: int = 24000,
    max_per_document: int | None = None,
    context_bytes: int | None = None,
) -> list[SearchChunk]:
    if top_k < 1 or context_characters < 1:
        raise ValueError("Invalid context limits")
    selected: list[SearchChunk] = []
    seen = set()
    counts = Counter()
    # Prefer a complete expanded passage over a contained fragment of that passage.
    ranked = [
        chunk
        for index, chunk in enumerate(ranked)
        if not chunk.section_key
        or not any(
            other.document_id == chunk.document_id
            and other.section_key == chunk.section_key
            and other.chunk_index <= chunk.chunk_index
            and (other.chunk_end_index if other.chunk_end_index is not None else other.chunk_index)
            >= (chunk.chunk_end_index if chunk.chunk_end_index is not None else chunk.chunk_index)
            and (
                (other.chunk_end_index or other.chunk_index) - other.chunk_index
                > (chunk.chunk_end_index or chunk.chunk_index) - chunk.chunk_index
                or previous < index
            )
            and len(PromptService.build_context([other.context()])) <= context_characters
            and (
                context_bytes is None
                or len(PromptService.build_context([other.context()]).encode("utf-8"))
                <= context_bytes
            )
            for previous, other in enumerate(ranked)
            if previous != index
        )
    ]
    for chunk in ranked:
        key = (chunk.document_id, " ".join(chunk.chunk_text.casefold().split()))
        if key in seen:
            continue
        if max_per_document and counts[chunk.document_id] >= max_per_document:
            continue
        # Source positions make overlap suppression precise, without guessing semantic equivalence.
        if chunk.start_offset is not None and any(
            c.document_id == chunk.document_id
            and c.page_start == chunk.page_start
            and c.start_offset is not None
            and max(
                0, min(c.end_offset, chunk.end_offset) - max(c.start_offset, chunk.start_offset)
            )
            / max(1, min(c.end_offset - c.start_offset, chunk.end_offset - chunk.start_offset))
            > 0.8
            for c in selected
        ):
            continue
        if (
            len(PromptService.build_context([c.context() for c in [*selected, chunk]]))
            > context_characters
        ):
            continue
        seen.add(key)
        if (
            context_bytes is not None
            and len(
                PromptService.build_context([c.context() for c in [*selected, chunk]]).encode(
                    "utf-8"
                )
            )
            > context_bytes
        ):
            continue
        selected.append(chunk)
        counts[chunk.document_id] += 1
        if len(selected) == top_k:
            break
    return selected


def retrieve_ranked(
    chunks: list[SearchChunk],
    question: str,
    query: list[float] | None,
    *,
    strategy: Strategy = "dense",
    top_k: int = 5,
    candidate_k: int = 20,
    context_characters: int = 24000,
    min_similarity: float = 0.0,
) -> list[SearchChunk]:
    if candidate_k < top_k:
        raise ValueError("Invalid retrieval limits")
    candidates = rank_candidates(
        chunks,
        question,
        query,
        strategy=strategy,
        candidate_k=candidate_k,
        min_similarity=min_similarity,
    )
    return select_context(candidates, top_k=top_k, context_characters=context_characters)


def stream_candidates(
    factory, question, query, *, strategy="dense", candidate_k=20, min_similarity=0.0
):
    """Exact rankers with bounded vector memory; the factory opens a fresh DB stream per pass."""
    if strategy not in {"dense", "bm25", "hybrid"} or candidate_k < 1:
        raise ValueError("Invalid retrieval strategy or candidate limit")
    dense = []
    terms = set(tokens(question))
    frequency = Counter()
    total = length_sum = 0
    for chunk in factory():
        if strategy != "bm25":
            score = cosine_score(chunk.embedding, query)
            if score is not None and score > min_similarity:
                candidate = replace(chunk, embedding=None, dense_score=score)
                item = (score, -chunk.id, candidate)
                if len(dense) < candidate_k:
                    heapq.heappush(dense, item)
                elif item[:2] > dense[0][:2]:
                    heapq.heapreplace(dense, item)
        if strategy != "dense":
            document = Counter(
                tokens(chunk.title + " " + (chunk.section or "") + " " + chunk.chunk_text)
            )
            total += 1
            length_sum += sum(document.values())
            frequency.update(term for term in terms if term in document)
    dense_rows = [c for _, _, c in sorted(dense, key=lambda item: (-item[0], -item[1]))]
    lexical = []
    if strategy != "dense" and total and terms:
        average = length_sum / total or 1
        for chunk in factory():
            document = Counter(
                tokens(chunk.title + " " + (chunk.section or "") + " " + chunk.chunk_text)
            )
            length = sum(document.values())
            score = sum(
                math.log1p((total - frequency[term] + 0.5) / (frequency[term] + 0.5))
                * document[term]
                * 2.2
                / (document[term] + 1.2 * (0.25 + 0.75 * length / average))
                for term in sorted(terms)
                if document[term]
            )
            if score > 0:
                item = (score, -chunk.id, replace(chunk, embedding=None, lexical_score=score))
                if len(lexical) < candidate_k:
                    heapq.heappush(lexical, item)
                elif item[:2] > lexical[0][:2]:
                    heapq.heapreplace(lexical, item)
    lexical_rows = [c for _, _, c in sorted(lexical, key=lambda item: (-item[0], -item[1]))]
    if strategy != "hybrid":
        return dense_rows if strategy == "dense" else lexical_rows
    ranking = reciprocal_rank_fusion([[c.id for c in dense_rows], [c.id for c in lexical_rows]])
    by_id = {c.id: c for c in lexical_rows}
    for chunk in dense_rows:
        by_id[chunk.id] = replace(
            chunk, lexical_score=by_id[chunk.id].lexical_score if chunk.id in by_id else None
        )
    return [by_id[i] for i in ranking[:candidate_k]]

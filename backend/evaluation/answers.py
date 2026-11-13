"""Answer review packs. Format checks are automatic; correctness/support need reviewed claims."""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from evaluation.metrics import retrieval_metrics
from services.generation_protocol import NO_CONTEXT_ANSWER, PROMPT_VERSION
from services.prompt_service import PromptService
from services.search import SearchChunk, rank_candidates, select_context


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    prompt_tokens: int | None = None
    answer_tokens: int | None = None


def citation_references(answer: str, excerpt_count: int) -> dict:
    # This checks marker syntax/range only. It does not assess support for a claim.
    markers = [int(m) for m in re.findall(r"(?<!!)\[(\d+)\](?!\()", answer)]
    invalid = [marker for marker in markers if marker < 1 or marker > excerpt_count]
    return {
        "markers": markers,
        "invalid_markers": invalid,
        "valid_marker_fraction": (len(markers) - len(invalid)) / len(markers) if markers else None,
    }


def evaluate_answers(
    data: dict,
    embed: Callable,
    generate: Callable,
    *,
    strategy="dense",
    profiles=("baseline", "compact"),
    candidate_k=20,
    context_characters=24000,
    rerank: Callable | None = None,
) -> dict:
    if (
        not profiles
        or len(set(profiles)) != len(profiles)
        or not set(profiles) <= {"baseline", "compact", "reranked"}
        or ("reranked" in profiles and rerank is None)
    ):
        raise ValueError("Invalid answer evaluation profiles")
    if candidate_k < 5 or context_characters < 1:
        raise ValueError("Invalid evaluation limits")
    texts = [c["chunk_text"] for c in data["chunks"]] + [q["question"] for q in data["queries"]]
    start = time.perf_counter()
    vectors = embed(texts) if strategy != "bm25" else [None] * len(texts)
    embedding_seconds = time.perf_counter() - start if strategy != "bm25" else None
    if len(vectors) != len(texts):
        raise ValueError("Embedding result length mismatch")
    chunks = [
        SearchChunk(**{**c, "embedding": v})
        for c, v in zip(data["chunks"], vectors[: len(data["chunks"])], strict=True)
    ]
    results = []
    for query, vector in zip(data["queries"], vectors[len(chunks) :], strict=True):
        start = time.perf_counter()
        candidates = rank_candidates(
            chunks, query["question"], vector, strategy=strategy, candidate_k=candidate_k
        )
        ranking_seconds = time.perf_counter() - start
        reranked = None
        rerank_error = False
        rerank_seconds = None
        if "reranked" in profiles:
            start = time.perf_counter()
            try:
                reranked = rerank(query["question"], candidates)
            except Exception:
                rerank_error = True
            rerank_seconds = time.perf_counter() - start
        for profile in profiles:
            k = 5 if profile == "baseline" else 2
            result = {
                "id": query["id"],
                "profile": profile,
                "question": query["question"],
                "reference_answer": query["reference_answer"],
                "relevant_ids": query["relevant_ids"],
                "top_k": k,
                "ranking_seconds": ranking_seconds,
                "reranking_seconds": rerank_seconds if profile == "reranked" else None,
                "review": {"correct": None, "refused": None, "claims": []},
            }
            if profile == "reranked" and rerank_error:
                results.append(
                    {**result, "status": "reranker_error", "answer": None, "excerpts": []}
                )
                continue
            selected = select_context(
                reranked if profile == "reranked" else candidates,
                top_k=k,
                context_characters=context_characters,
            )
            context = PromptService.build_context([c.context() for c in selected])
            result.update(
                {
                    "retrieved_ids": [c.id for c in selected],
                    "retrieval_metrics": retrieval_metrics(
                        [c.id for c in selected], set(query["relevant_ids"]), k
                    ),
                    "context_characters": len(context),
                    "excerpts": [
                        {"marker": i, "chunk_id": c.id, **c.context()}
                        for i, c in enumerate(selected, 1)
                    ],
                }
            )
            start = time.perf_counter()
            try:
                output = (
                    generate(query["question"], context)
                    if selected
                    else GeneratedAnswer(NO_CONTEXT_ANSWER)
                )
                if not isinstance(output, GeneratedAnswer) or not output.text.strip():
                    raise ValueError("Invalid generated answer")
                result.update(
                    {
                        "status": "ok" if selected else "no_context",
                        "answer": output.text,
                        "generation_seconds": time.perf_counter() - start if selected else None,
                        "prompt_tokens": output.prompt_tokens,
                        "answer_tokens": output.answer_tokens,
                        "citation_reference_check": citation_references(output.text, len(selected)),
                    }
                )
            except Exception:
                result.update(
                    {
                        "status": "provider_error",
                        "answer": None,
                        "generation_seconds": time.perf_counter() - start,
                        "error": "Generation failed. Check the model/provider; no answer was fabricated.",
                    }
                )
            results.append(result)
    return {
        "dataset_description": data.get("description"),
        "prompt_version": PROMPT_VERSION,
        "strategy": strategy,
        "embedding_batch_seconds": embedding_seconds,
        "results": results,
        "review_instructions": "Fill correct/refused with booleans after inspecting the reference and excerpts. Add claims with text, supported, cited and citation_supported booleans (or null when unreviewed). Citation markers alone do not establish support. Do not include irrelevant/private document content in shared reports.",
        "caveat": "No automated faithfulness/correctness claim. Review fields are intentionally unscored until reviewed. The compact profile changes context size, not calibrated evidence rejection.",
    }


def summarize_reviews(report: dict) -> dict:
    groups = {}
    seen = set()
    for row in report["results"]:
        identity = (row["profile"], row["id"])
        if identity in seen:
            raise ValueError("Duplicate review entry")
        seen.add(identity)
        group = groups.setdefault(
            row["profile"],
            {
                "completed": 0,
                "errors": 0,
                "correct": [],
                "answerable_refusals": [],
                "unanswerable_refusals": [],
                "support": [],
                "coverage": [],
                "citation_support": [],
            },
        )
        if row["status"] not in {"ok", "no_context"}:
            group["errors"] += 1
            continue
        group["completed"] += 1
        review = row.get("review", {})
        for key in ["correct", "refused"]:
            if review.get(key) is not None and type(review[key]) is not bool:
                raise ValueError("Review values must be boolean or null")
        if row["relevant_ids"] and review.get("correct") is not None:
            group["correct"].append(review["correct"])
        if review.get("refused") is not None:
            group["answerable_refusals" if row["relevant_ids"] else "unanswerable_refusals"].append(
                review["refused"]
            )
        for claim in review.get("claims", []):
            if not isinstance(claim.get("text"), str) or not claim["text"].strip():
                raise ValueError("Claim reviews need nonempty claim text")
            if claim.get("citation_supported") is True and claim.get("supported") is False:
                raise ValueError("A citation-supported claim cannot be labelled unsupported")
            for key in ["supported", "cited", "citation_supported"]:
                if claim.get(key) is not None and type(claim[key]) is not bool:
                    raise ValueError("Claim review values must be boolean or null")
            if claim.get("citation_supported") is not None and claim.get("cited") is not True:
                raise ValueError("Citation support requires a cited claim")
            if claim.get("supported") is not None:
                group["support"].append(claim["supported"])
            if claim.get("cited") is not None:
                group["coverage"].append(claim["cited"])
            if claim.get("cited") is True and claim.get("citation_supported") is not None:
                group["citation_support"].append(claim["citation_supported"])
    output = {}
    for profile, g in groups.items():

        def mean(values):
            return sum(values) / len(values) if values else None

        output[profile] = {
            "completed_cases": g["completed"],
            "provider_or_reranker_errors": g["errors"],
            "reviewed_answerable_correctness": mean(g["correct"]),
            "reviewed_claim_faithfulness": mean(g["support"]),
            "reviewed_citation_precision": mean(g["citation_support"]),
            "reviewed_citation_coverage": mean(g["coverage"]),
            "reviewed_unanswerable_refusal_rate": mean(g["unanswerable_refusals"]),
            "reviewed_answerable_false_refusal_rate": mean(g["answerable_refusals"]),
            "review_counts": {
                key: len(g[key])
                for key in [
                    "correct",
                    "support",
                    "coverage",
                    "citation_support",
                    "unanswerable_refusals",
                    "answerable_refusals",
                ]
            },
        }
    return {
        "profiles": output,
        "caveat": "Metrics cover only explicitly reviewed answers/claims. Null means not reviewed, not perfect or zero. Human labels are not an automatic proof of correctness.",
    }

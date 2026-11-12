"""Evaluate public synthetic evidence labels. Dense/hybrid evaluation explicitly opts into inference."""

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.metrics import retrieval_metrics  # noqa: E402
from services.search import SearchChunk, retrieve_ranked  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evaluation/retrieval_cases.json",
    )
    parser.add_argument("--strategy", choices=["bm25", "dense", "hybrid", "all"], default="bm25")
    parser.add_argument("--allow-inference", action="store_true")
    parser.add_argument(
        "--ollama-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    parser.add_argument("--model", default=os.environ.get("EMBEDDING_MODEL", "all-minilm"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--context-characters", type=int, default=24000)
    args = parser.parse_args()
    if args.k < 1 or args.candidate_k < args.k or args.context_characters < 1:
        parser.error("Invalid retrieval limits")
    if args.strategy != "bm25" and not args.allow_inference:
        parser.error(
            "Dense/hybrid runs call your configured Ollama service; select --allow-inference explicitly"
        )
    data = json.loads(args.dataset.read_text())
    identities = [row["id"] for row in data["chunks"]]
    if len(set(identities)) != len(identities) or any(
        not set(q["relevant_ids"]) <= set(identities) for q in data["queries"]
    ):
        parser.error("Dataset has duplicate IDs or missing relevance references")
    chunks = [SearchChunk(**row) for row in data["chunks"]]
    query_vectors: list[list[float] | None] = [None] * len(data["queries"])
    embedding_seconds = None
    if args.strategy != "bm25":
        texts = [c.chunk_text for c in chunks] + [q["question"] for q in data["queries"]]
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(
                    args.ollama_url.rstrip("/") + "/api/embed",
                    json={"model": args.model, "input": texts},
                )
                response.raise_for_status()
                vectors = response.json()["embeddings"]
            if (
                len(vectors) != len(texts)
                or not vectors
                or not all(
                    isinstance(v, list)
                    and len(v) == len(vectors[0])
                    and v
                    and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)
                    and any(v)
                    for v in vectors
                )
            ):
                raise ValueError("Invalid embedding response")
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            raise SystemExit(
                "Embedding evaluation failed. Check Ollama and the configured model; no results were fabricated."
            ) from None
        embedding_seconds = time.perf_counter() - start
        chunks = [
            SearchChunk(**{**row, "embedding": vector})
            for row, vector in zip(data["chunks"], vectors[: len(chunks)], strict=True)
        ]
        query_vectors = vectors[len(chunks) :]
    reports = []
    for strategy in ["dense", "bm25", "hybrid"] if args.strategy == "all" else [args.strategy]:
        results = []
        for question, vector in zip(data["queries"], query_vectors, strict=True):
            start = time.perf_counter()
            selected = retrieve_ranked(
                chunks,
                question["question"],
                vector,
                strategy=strategy,
                top_k=args.k,
                candidate_k=args.candidate_k,
                context_characters=args.context_characters,
            )
            results.append(
                {
                    "id": question["id"],
                    "retrieved_ids": [c.id for c in selected],
                    "relevant_ids": question["relevant_ids"],
                    "metrics": retrieval_metrics(
                        [c.id for c in selected], set(question["relevant_ids"]), args.k
                    ),
                    "ranking_ms": (time.perf_counter() - start) * 1000,
                }
            )
        answerable = [r for r in results if r["relevant_ids"]]
        unsupported = [r for r in results if not r["relevant_ids"]]
        reports.append(
            {
                "strategy": strategy,
                "k": args.k,
                "answerable_queries": len(answerable),
                "unanswerable_queries": len(unsupported),
                "macro_metrics": {
                    name: sum(r["metrics"][name] for r in answerable) / len(answerable)
                    if answerable
                    else None
                    for name in ["precision", "recall", "mrr", "ndcg"]
                },
                "unanswerable_empty_result_rate": sum(
                    r["metrics"]["empty_result"] for r in unsupported
                )
                / len(unsupported)
                if unsupported
                else None,
                "results": results,
            }
        )
    print(
        json.dumps(
            {
                "dataset_description": data.get("description"),
                "model": args.model if args.allow_inference and args.strategy != "bm25" else None,
                "embedding_batch_seconds": embedding_seconds,
                "limits": {
                    "candidate_k": args.candidate_k,
                    "context_characters": args.context_characters,
                },
                "caveat": "Synthetic retrieval regression only. Ranking time excludes database, embeddings and generation. No faithfulness, answer correctness, citation accuracy or production quality claim.",
                "reports": reports,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

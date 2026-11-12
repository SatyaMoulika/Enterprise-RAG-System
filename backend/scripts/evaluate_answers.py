"""Generate a review pack using the real local models; or aggregate explicitly reviewed labels."""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.answers import GeneratedAnswer, evaluate_answers, summarize_reviews  # noqa: E402
from services.generation_protocol import chat_payload  # noqa: E402
from services.reranking_service import rerank_chunks  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evaluation/policy_cases.json",
    )
    parser.add_argument(
        "--review-file",
        type=Path,
        help="Aggregate a completed review pack offline; no provider calls",
    )
    parser.add_argument("--allow-inference", action="store_true")
    parser.add_argument(
        "--allow-model-download",
        action="store_true",
        help="Required when profiles includes reranked; allows loading the optional cross-encoder",
    )
    parser.add_argument("--profiles", default="baseline,compact")
    parser.add_argument("--strategy", choices=["dense", "bm25", "hybrid"], default="dense")
    parser.add_argument("--case-ids", help="Comma-separated case IDs for a small first run")
    parser.add_argument(
        "--ollama-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    parser.add_argument(
        "--embedding-model", default=os.environ.get("EMBEDDING_MODEL", "all-minilm")
    )
    parser.add_argument("--answer-model", default=os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:3b"))
    parser.add_argument(
        "--reranker-model",
        default=os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
    )
    parser.add_argument("--temperature", type=float, default=None)
    args = parser.parse_args()
    if args.review_file:
        try:
            report = summarize_reviews(json.loads(args.review_file.read_text()))
        except (ValueError, TypeError, KeyError, OSError) as exc:
            parser.error(f"Invalid review file: {type(exc).__name__}")
        print(json.dumps(report, indent=2))
        return
    if not args.allow_inference:
        parser.error("Generation calls your configured models; select --allow-inference explicitly")
    profiles = tuple(p.strip() for p in args.profiles.split(",") if p.strip())
    if (
        not profiles
        or len(set(profiles)) != len(profiles)
        or not set(profiles) <= {"baseline", "compact", "reranked"}
    ):
        parser.error("Invalid profiles")
    if "reranked" in profiles and not args.allow_model_download:
        parser.error("Re-ranking loads an optional model; select --allow-model-download explicitly")
    if args.temperature is not None and (
        not math.isfinite(args.temperature) or args.temperature < 0 or args.temperature > 2
    ):
        parser.error("Temperature must be between 0 and 2")
    try:
        data = json.loads(args.dataset.read_text())
        identities = [row["id"] for row in data["chunks"]]
        case_ids = [q["id"] for q in data["queries"]]
        if (
            len(set(identities)) != len(identities)
            or len(set(case_ids)) != len(case_ids)
            or not case_ids
            or not identities
            or any(
                not isinstance(q["reference_answer"], str)
                or not set(q["relevant_ids"]) <= set(identities)
                for q in data["queries"]
            )
        ):
            raise ValueError("Invalid labels")
    except (OSError, KeyError, TypeError, ValueError):
        parser.error(
            "Invalid dataset; include unique IDs, valid relevance labels and reference_answer strings"
        )
    if args.case_ids:
        chosen = set(args.case_ids.split(","))
        if not chosen <= set(case_ids):
            parser.error("Unknown case ID")
        data = {**data, "queries": [q for q in data["queries"] if q["id"] in chosen]}
    with httpx.Client(timeout=120) as client:

        def embed(texts):
            response = client.post(
                args.ollama_url.rstrip("/") + "/api/embed",
                json={"model": args.embedding_model, "input": texts},
            )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
            if (
                len(vectors) != len(texts)
                or not vectors
                or not all(
                    isinstance(v, list)
                    and v
                    and len(v) == len(vectors[0])
                    and all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)
                    and any(v)
                    for v in vectors
                )
            ):
                raise ValueError("Invalid embedding response")
            return vectors

        def generate(question, context):
            response = client.post(
                args.ollama_url.rstrip("/") + "/api/chat",
                json=chat_payload(question, context, args.answer_model, args.temperature),
            )
            response.raise_for_status()
            body = response.json()
            answer = body["message"]["content"]
            if not isinstance(answer, str):
                raise ValueError("Invalid answer")

            def count(key):
                value = body.get(key)
                return value if type(value) is int and value >= 0 else None

            return GeneratedAnswer(answer, count("prompt_eval_count"), count("eval_count"))

        try:
            report = evaluate_answers(
                data,
                embed,
                generate,
                strategy=args.strategy,
                profiles=profiles,
                rerank=(
                    lambda question, chunks: rerank_chunks(question, chunks, args.reranker_model)
                )
                if "reranked" in profiles
                else None,
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise SystemExit(
                "Evaluation could not obtain usable embeddings. Check the provider/model; no report was fabricated."
            ) from None
    report["models"] = {
        "embedding": args.embedding_model if args.strategy != "bm25" else None,
        "answer": args.answer_model,
        "reranker": args.reranker_model if "reranked" in profiles else None,
    }
    report["generation_temperature"] = args.temperature
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

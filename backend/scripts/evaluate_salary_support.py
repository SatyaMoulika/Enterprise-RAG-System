"""Measure an experimental model reviewer against labelled valid/invalid answers."""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.salary_support import review_salary_answer  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-inference", action="store_true")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evaluation/salary_checker_cases.json",
    )
    parser.add_argument(
        "--ollama-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    )
    parser.add_argument("--review-model", default=os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:3b"))
    args = parser.parse_args()
    if not args.allow_inference:
        parser.error("Select --allow-inference to call the configured review model")
    try:
        data = json.loads(args.dataset.read_text())
        cases = data["cases"]
        if not cases or len({c["id"] for c in cases}) != len(cases):
            raise ValueError("Invalid cases")
        for c in cases:
            if (
                c["expected_verdict"] not in {"supported", "unsupported"}
                or not all(isinstance(c[k], str) and c[k] for k in ("question", "answer"))
                or not c["excerpts"]
            ):
                raise ValueError("Invalid case")
    except (OSError, KeyError, TypeError, ValueError):
        parser.error("Invalid checker fixture")
    results = []
    with httpx.Client(timeout=120) as client:

        def review(payload):
            response = client.post(
                args.ollama_url.rstrip("/") + "/api/chat",
                json={**payload, "model": args.review_model},
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

        for case in cases:
            result = review_salary_answer(
                case["question"], case["answer"], case["excerpts"], review
            )
            results.append({**case, "review": result})
    # Include every labelled case in denominators; errors and uncertainty remain explicit.
    invalid = [r for r in results if r["expected_verdict"] == "unsupported"]
    valid = [r for r in results if r["expected_verdict"] == "supported"]
    print(
        json.dumps(
            {
                "description": data.get("description"),
                "checker_version": "salary-claim-review-v1",
                "review_model": args.review_model,
                "temperature": 0,
                "results": results,
                "summary": {
                    "labelled_invalid": len(invalid),
                    "labelled_valid": len(valid),
                    "invalid_flagged": sum(
                        r["review"]["verdict"] == "unsupported" for r in invalid
                    ),
                    "valid_falsely_flagged": sum(
                        r["review"]["verdict"] == "unsupported" for r in valid
                    ),
                    "invalid_missed_as_supported": sum(
                        r["review"]["verdict"] == "supported" for r in invalid
                    ),
                    "valid_marked_supported": sum(
                        r["review"]["verdict"] == "supported" for r in valid
                    ),
                    "uncertain": sum(r["review"]["verdict"] == "uncertain" for r in results),
                    "check_errors": sum(r["review"]["status"] == "check_error" for r in results),
                },
                "caveat": "Model-assisted review, not ground truth. Inspect claim coverage and support manually; no production enforcement or retries enabled.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Offline calculator comparison using the exact evidence from an existing report."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.salary_calculator import salary_answer  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        source = json.loads(args.report_file.read_text())
        groups = {}
        for row in source["results"]:
            if row["status"] != "ok":
                continue
            excerpts = row["excerpts"]
            if (
                not isinstance(row["question"], str)
                or not excerpts
                or [e["marker"] for e in excerpts] != list(range(1, len(excerpts) + 1))
                or not all(isinstance(e["chunk_text"], str) for e in excerpts)
            ):
                raise ValueError("Invalid evidence")
            key = json.dumps([row["id"], row["question"], excerpts], sort_keys=True)
            if key not in groups:
                chunks = [{"chunk_text": e["chunk_text"]} for e in excerpts]
                groups[key] = {
                    "id": row["id"],
                    "question": row["question"],
                    "excerpts": excerpts,
                    "calculation": salary_answer(row["question"], chunks),
                    "previous_answers": [],
                }
            groups[key]["previous_answers"].append(
                {"profile": row["profile"], "answer": row["answer"]}
            )
        if not groups:
            raise ValueError("No successful cases")
    except (OSError, KeyError, TypeError, ValueError):
        parser.error("Invalid report; successful answer rows need numbered chunk_text excerpts")
    results = list(groups.values())
    print(
        json.dumps(
            {
                "calculator_version": "bounded-salary-v1",
                "inference_performed": False,
                "results": results,
                "summary": {
                    "unique_contexts": len(results),
                    "calculated": sum(
                        r["calculation"] is not None and r["calculation"]["status"] == "calculated"
                        for r in results
                    ),
                    "insufficient_evidence": sum(
                        r["calculation"] is not None
                        and r["calculation"]["status"] == "insufficient_evidence"
                        for r in results
                    ),
                    "needs_clarification": sum(
                        r["calculation"] is not None
                        and r["calculation"]["status"] == "needs_clarification"
                        for r in results
                    ),
                    "not_handled": sum(r["calculation"] is None for r in results),
                },
                "caveat": "Statuses indicate calculator coverage, not accuracy scores. Manually verify quotes, identity, periods, arithmetic and abstentions. Non-salary cases are not handled or graded.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

"""Suggest a dense similarity cutoff from a labelled source-evaluation development report.

Never updates application settings. Validate the suggestion on a separate held-out corpus.
"""

import argparse
import json


def calibrate(report):
    rows = report["results"]
    if any(row["status"] not in {"ok", "no_context"} for row in rows):
        raise ValueError("Resolve pipeline errors before calibrating")
    samples = []
    for row in rows:
        scores = [
            c["dense_score"] for c in row.get("citations", []) if c.get("dense_score") is not None
        ]
        samples.append((max(scores, default=-1.0), bool(row["relevant_ids"])))
    if not any(label for _, label in samples) or all(label for _, label in samples):
        raise ValueError("Calibration needs both answerable and unanswerable cases")
    thresholds = sorted({-1.0, 0.0, 1.0, *(score for score, _ in samples)})
    results = []
    for threshold in thresholds:
        tp = sum(score > threshold and label for score, label in samples)
        fp = sum(score > threshold and not label for score, label in samples)
        fn = sum(score <= threshold and label for score, label in samples)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        results.append(
            {
                "threshold": threshold,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": precision,
                "recall": recall,
                "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            }
        )
    best = max(results, key=lambda row: (row["f1"], -row["false_positives"], row["threshold"]))
    return {
        "suggested_development_threshold": best["threshold"],
        "development_metrics": best,
        "sweep": results,
        "setting_changed": False,
        "caveat": "These measure retrieval availability, not answer correctness. Scores come from selected contexts and may be censored by an existing threshold/budget. Run dense evaluation with a permissive cutoff and sufficient context; test the chosen threshold on held-out documents before applying it. Hybrid lexical matches are not rejected by a dense cutoff.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=argparse.FileType("r"))
    args = parser.parse_args()
    try:
        report = json.load(args.report)
        if report.get("runtime", {}).get("RETRIEVAL_STRATEGY") != "dense":
            raise ValueError("Use a dense source-evaluation report")
        print(json.dumps(calibrate(report), indent=2))
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

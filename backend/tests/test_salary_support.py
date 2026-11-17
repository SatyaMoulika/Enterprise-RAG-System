import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation.answers import GeneratedAnswer, evaluate_answers
from evaluation.salary_support import review_salary_answer

EXCERPTS = [
    {
        "marker": 1,
        "excerpt": "Bob earns INR 80,000 monthly gross before deductions. Deductions are unspecified.",
    }
]
ANSWER = "Monthly gross is INR 80,000 [1]. Therefore take-home pay is INR 80,000."


def test_reviewer_receives_whole_answer_and_checks_final_unsupported_claim():
    def review(payload):
        assert payload["options"] == {"temperature": 0}
        assert payload["format"] == "json"
        data = json.loads(payload["messages"][1]["content"])
        assert data["answer"] == ANSWER
        assert data["excerpts"] == EXCERPTS
        return json.dumps(
            {
                "claims": [
                    {
                        "text": "Monthly gross is INR 80,000 [1].",
                        "assessment": "supported",
                        "source_markers": [1],
                        "reason": "Gross is explicit.",
                    },
                    {
                        "text": "Therefore take-home pay is INR 80,000.",
                        "assessment": "unsupported",
                        "source_markers": [1],
                        "reason": "Only gross is provided; deductions unknown.",
                    },
                ]
            }
        )

    result = review_salary_answer("What is my pay?", ANSWER, EXCERPTS, review)
    assert result["verdict"] == "unsupported"
    assert result["human_review_required"] is True
    assert len(result["claims"]) == 2


@pytest.mark.parametrize(
    "answer",
    [
        "Monthly gross is INR 80,000 [1].",
        "Take-home cannot be determined because deductions are unspecified [1].",
    ],
)
def test_well_formed_supported_review_remains_advisory(answer):
    result = review_salary_answer(
        "Pay?",
        answer,
        EXCERPTS,
        lambda payload: json.dumps(
            {
                "claims": [
                    {
                        "text": answer,
                        "assessment": "supported",
                        "source_markers": [1],
                        "reason": "Matches supplied evidence.",
                    },
                ]
            }
        ),
    )
    assert result["verdict"] == "supported"
    assert result["human_review_required"] is True


@pytest.mark.parametrize(
    "value",
    [
        "not JSON",
        '{"claims":[]}',
        json.dumps(
            {
                "claims": [
                    {
                        "text": ANSWER,
                        "assessment": "supported",
                        "source_markers": [99],
                        "reason": "Unknown marker",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "claims": [
                    {
                        "text": "Invented answer not present",
                        "assessment": "supported",
                        "source_markers": [1],
                        "reason": "Invented",
                    }
                ]
            }
        ),
        json.dumps(
            {
                "claims": [
                    {
                        "text": ANSWER,
                        "assessment": "supported",
                        "source_markers": [],
                        "reason": "No evidence",
                    }
                ]
            }
        ),
    ],
)
def test_invalid_checker_responses_never_become_success_or_leak_provider_details(value):
    result = review_salary_answer("Pay?", ANSWER, EXCERPTS, lambda payload: value)
    assert result["status"] == "check_error" and result["verdict"] is None


def test_checker_failure_keeps_generated_answer_and_human_labels_intact():
    data = {
        "chunks": [
            {
                "id": 1,
                "document_id": 1,
                "title": "pay.txt",
                "chunk_index": 0,
                "chunk_text": EXCERPTS[0]["excerpt"],
            }
        ],
        "queries": [
            {
                "id": "pay",
                "question": "Pay?",
                "relevant_ids": [1],
                "reference_answer": "Gross only.",
            }
        ],
    }

    def broken(*args):
        raise RuntimeError("private endpoint details")

    result = evaluate_answers(
        data,
        lambda texts: [[1, 0]] * len(texts),
        lambda q, c: GeneratedAnswer(ANSWER),
        profiles=("baseline",),
        answer_check=broken,
    )["results"][0]
    assert result["answer"] == ANSWER and result["status"] == "ok"
    assert result["salary_support_review"]["status"] == "check_error"
    assert result["review"]["correct"] is None
    assert "private endpoint details" not in str(result)


def test_checker_cli_requires_inference_and_fixture_has_balanced_labels():
    base = Path(__file__).resolve().parents[1]
    response = subprocess.run(
        [sys.executable, str(base / "scripts/evaluate_salary_support.py")],
        capture_output=True,
        text=True,
    )
    assert response.returncode == 2 and "--allow-inference" in response.stderr
    cases = json.loads((base / "evaluation/salary_checker_cases.json").read_text())["cases"]
    assert len(cases) == len({c["id"] for c in cases}) == 20
    assert sum(c["expected_verdict"] == "supported" for c in cases) == 10
    assert sum(c["expected_verdict"] == "unsupported" for c in cases) == 10

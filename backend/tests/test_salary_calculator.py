import json
from pathlib import Path

import pytest

from services.salary_calculator import salary_answer


def source(text):
    return [{"document_id": 1, "title": "pay.txt", "chunk_index": 0, "chunk_text": text}]


def fixture():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "evaluation/salary_cases.json").read_text()
    )


def test_reported_regressions_use_correct_arithmetic_or_explain_missing_inputs():
    data = fixture()
    results = {q["id"]: salary_answer(q["question"], data["chunks"]) for q in data["queries"]}
    assert "INR 80,000.00" in results["bob-gross"]["answer"]
    assert results["bob-gross"]["status"] == "insufficient_evidence"
    assert results["complete-deductions"]["status"] == "calculated"
    assert "INR 70,000.00" in results["complete-deductions"]["answer"]
    assert "INR 70,000.00" in results["annual-period"]["answer"]
    assert "76,666" not in results["annual-period"]["answer"]
    assert results["explicit-net"]["status"] == "calculated"
    for case in (
        "partial-deductions",
        "different-person",
        "unknown-installments",
        "currency-mismatch",
        "reimbursement",
    ):
        assert results[case]["status"] == "insufficient_evidence"
    assert results["bonus-cap"] is None
    for result in results.values():
        if result:
            for fact in result["facts"]:
                assert fact["quote"] in data["chunks"][fact["marker"] - 1]["chunk_text"]


@pytest.mark.parametrize(
    "text",
    [
        "Dev Patel: monthly gross salary INR 80,000; income tax INR 8,000 and insurance INR 2,000 per year. No other deductions apply.",
        "Dev Patel: annual gross pay INR 960,000. Total annual deductions INR 120,000. No other deductions apply.",
        "Dev Patel: monthly gross salary INR 80,000. Final net pay INR 70,000 unless further adjustments apply.",
        "Dev Patel: monthly gross salary INR 80,000. Monthly gross salary INR 90,000. Final net pay INR 70,000.",
        "Dev Patel: annual gross pay INR 960,000. Final net pay INR 840,000.",
        "Dev Patel: monthly gross salary INR 80,000. Final net pay INR 90,000.",
        "Dev Patel: monthly gross salary INR 80,000. Final net pay INR 70,000. Total monthly deductions INR 5,000. No other deductions apply.",
        "Dev Patel: monthly gross salary INR 80,00. Final net pay is not specified.",
    ],
)
def test_ambiguous_periods_conditions_conflicts_and_malformed_numbers_abstain(text):
    assert (
        salary_answer("What is Dev Patel net pay?", source(text))["status"]
        == "insufficient_evidence"
    )


def test_employee_identity_requires_explicit_question_or_authenticated_name():
    chunks = source(
        "Alice Morgan: monthly gross salary INR 100,000. Net pay is unspecified. Bob Reed: final monthly net pay INR 70,000."
    )
    assert salary_answer("What is my take-home pay?", chunks)["status"] == "needs_clarification"
    assert (
        salary_answer("What is my take-home pay?", chunks, "Alice Morgan")["status"]
        == "insufficient_evidence"
    )
    assert (
        "INR 70,000" not in salary_answer("What is Alice Morgan take-home pay?", chunks)["answer"]
    )
    assert salary_answer("What is Bob Reed take-home pay?", chunks)["status"] == "calculated"


def test_decimal_math_and_exact_citation_order_and_period_filter():
    chunks = source("Other Person: monthly gross salary INR 500.00.") + source(
        "Mira Chen: gross monthly salary INR 80,000. The payslip explicitly states final net pay INR 70,000 for April 2027."
    )
    r = salary_answer("What is Mira Chen net pay for April 2027?", chunks)
    assert "INR 70,000.00" in r["answer"] and "[2]" in r["answer"] and "[1]" not in r["answer"]
    assert (
        salary_answer("What is Mira Chen net pay for May 2027?", chunks)["status"]
        == "insufficient_evidence"
    )
    decimal = source(
        "Dev Patel: April 2027 monthly gross salary INR 100.10; income tax INR 0.10 and insurance INR 0.20 for that month. No other deductions apply."
    )
    assert "INR 99.80" in salary_answer("Dev Patel net pay for April 2027?", decimal)["answer"]


def test_unrelated_questions_keep_normal_pipeline():
    assert salary_answer("How much annual leave can I carry forward?", []) is None


def test_live_opt_in_calculator_does_not_call_llm(client, account, monkeypatch):
    from core.config import settings
    from services.llm_service import LLMService

    text = next(c["chunk_text"] for c in fixture()["chunks"] if c["id"] == 5)
    response = client.post(
        "/documents/upload", headers=account, files={"file": ("pay.txt", text.encode())}
    )
    assert response.status_code == 201
    monkeypatch.setattr(settings, "FINANCIAL_CALCULATIONS_ENABLED", True)
    monkeypatch.setattr(
        LLMService, "generate", lambda **kw: pytest.fail("Handled calculation must not use LLM")
    )
    result = client.post(
        "/chat/generate", headers=account, json={"question": "What is Omar Ali monthly net pay?"}
    )
    assert result.status_code == 200
    assert "INR 70,000.00" in result.json()["answer"]
    assert result.json()["sources"] == [response.json()["id"]]


def test_evaluation_records_calculator_output_without_model_tokens_or_inference():
    from evaluation.answers import evaluate_answers

    data = fixture()
    data["chunks"] = [c for c in data["chunks"] if c["id"] == 5]
    data["queries"] = [q for q in data["queries"] if q["id"] == "annual-period"]

    def forbidden(*args):
        pytest.fail("No LLM call for supported arithmetic")

    result = evaluate_answers(
        data,
        lambda texts: [[1, 0]] * len(texts),
        forbidden,
        profiles=("baseline",),
        answer_override=salary_answer,
    )["results"][0]
    assert result["status"] == "ok" and result["answer_origin"] == "deterministic_salary"
    assert result["prompt_tokens"] is None and result["answer_tokens"] is None
    assert result["review"]["correct"] is None
    assert (
        result["financial_calculation"]["source_evidence"][0]["quote"]
        == data["chunks"][0]["chunk_text"]
    )


def test_multiple_pay_periods_and_extreme_numeric_input_abstain():
    chunks = source(
        "Mira Chen: monthly gross salary INR 80,000. Final net pay INR 70,000 for April 2027."
    ) + source("Mira Chen: monthly gross salary INR 85,000. Final net pay INR 75,000 for May 2027.")
    assert salary_answer("What is Mira Chen net pay?", chunks)["status"] == "needs_clarification"
    r = salary_answer("What is Mira Chen net pay for April 2027?", chunks)
    assert r["status"] == "calculated" and "70,000.00" in r["answer"]
    huge = source("Dev Patel: monthly gross salary INR " + "9" * 300 + ". Net pay is unspecified.")
    assert salary_answer("Dev Patel net pay?", huge)["status"] == "insufficient_evidence"


def test_live_calculator_cannot_see_another_employees_private_document(
    client, account, monkeypatch
):
    from core.config import settings
    from services.llm_service import LLMService

    alice = client.post(
        "/users/create_user",
        headers=account,
        json={
            "name": "Alice Morgan",
            "email": "alice.calc@example.com",
            "password": "test password 123",
            "role": "employee",
        },
    ).json()["id"]
    client.post(
        "/users/create_user",
        headers=account,
        json={
            "name": "Bob Reed",
            "email": "bob.calc@example.com",
            "password": "test password 123",
            "role": "employee",
        },
    )
    token = client.post(
        "/auth/login", json={"email": "bob.calc@example.com", "password": "test password 123"}
    ).json()["access_token"]
    doc = client.post(
        "/documents/upload",
        headers=account,
        files={
            "file": (
                "private-pay.txt",
                b"Alice Morgan: monthly gross salary INR 100,000. Final monthly net pay INR 90,000.",
            )
        },
        data={"access": json.dumps({"visibility": "personal", "recipient_ids": [alice]})},
    )
    assert doc.status_code == 201
    monkeypatch.setattr(settings, "FINANCIAL_CALCULATIONS_ENABLED", True)
    monkeypatch.setattr(
        LLMService, "generate", lambda **kw: pytest.fail("No evidence must not invoke generation")
    )
    response = client.post(
        "/chat/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Alice Morgan net pay?"},
    )
    assert response.status_code == 200 and response.json()["sources"] == []
    assert "90,000" not in response.json()["answer"]


def test_offline_comparison_does_not_need_provider_configuration(tmp_path):
    import subprocess
    import sys

    report = {
        "results": [
            {
                "id": "pay",
                "status": "ok",
                "question": "Omar Ali monthly net pay?",
                "profile": "baseline",
                "answer": "Old incorrect amount.",
                "excerpts": [
                    {
                        "marker": 1,
                        "chunk_text": next(
                            c["chunk_text"] for c in fixture()["chunks"] if c["id"] == 5
                        ),
                    }
                ],
            }
        ]
    }
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    script = Path(__file__).resolve().parents[1] / "scripts/evaluate_salary_calculations.py"
    result = subprocess.run(
        [sys.executable, str(script), "--report-file", str(path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["inference_performed"] is False
    assert output["summary"]["calculated"] == 1
    assert "70,000.00" in output["results"][0]["calculation"]["answer"]


@pytest.mark.parametrize(
    "extra", ["Pension deduction 5000.", "A retirement contribution of 5% also applies."]
)
def test_unparsed_deductions_cannot_be_silently_omitted(extra):
    text = (
        "Dev Patel: April 2027 monthly gross salary INR 80,000; income tax INR 8,000 and insurance INR 2,000 for that month. "
        + extra
        + " No other deductions apply."
    )
    assert (
        salary_answer("Dev Patel monthly net pay?", source(text))["status"]
        == "insufficient_evidence"
    )

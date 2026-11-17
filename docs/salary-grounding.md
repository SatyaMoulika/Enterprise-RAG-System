# Financial qualifiers and salary-support evaluation

A retrieved gross salary does not support a net-pay claim. The observed answer correctly stated Bob's INR 80,000 monthly gross, then incorrectly called the same amount pay after deductions. Retrieval relevance and a valid citation did not catch the contradictory conclusion.

## Production change

Prompt `salary-grounding-v5` extends the employee-facing v4 instructions with preserved gross/net, before/after deductions, annual/monthly, fixed/variable and capped/guaranteed qualifiers. It permits calculations only when inputs, currency, employee and pay period match. Twelve equal annual installments can establish monthly gross; final net pay requires explicit net pay or a complete compatible deduction set. Partial deduction lists, reimbursements, discretionary bonuses and another employee's pay must not supply missing take-home facts.

This branch also includes the pending PR #11 PDF word-stream cleanup and source/tone changes. Historical v2, v3 and v4 prompts remain available for comparison. Five-excerpt retrieval, access rules and production sampling remain unchanged. Instructions are not a deterministic financial validator. No production checker, automatic retry, answer rewrite or fallback is enabled.

## First run: measure the checker on labelled examples

After merging, preserve local edits, pull and rebuild the API:

```sh
git switch main
git pull --ff-only
docker compose -p rag-updated up -d --build api
```

The separate fixture contains ten valid and ten invalid fictional answers with fixed evidence. Run twenty extra review-model calls using the existing Ollama chat model:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_salary_support.py \
  --allow-inference > salary-checker-review.json
```

Inspect the summary counts: invalid flagged, invalid missed as supported, valid falsely flagged, valid marked supported, uncertainty and checker errors. All labelled cases remain counted; errors are not successes and uncertainty is not treated as a pass. Review claim coverage and evidence manually, including the final conclusion. These manually labelled development fixtures are not an unseen or production benchmark. A reviewer can miss claims or misjudge support; valid marker IDs only validate references, not entailment. Do not enable enforcement based on a perfect-looking small result.

The reviewer requests temperature-zero JSON claims, validates that claim text occurs in the answer and markers exist, and derives its advisory verdict from the model's claim assessments. Invalid JSON, unknown markers, invented claim text, empty claim lists or provider errors produce `check_error` and no verdict. Every result requires human review. The default reviewer is the same configured answer model, not an independent authority; correlated errors are possible. `--review-model` can select another already-available local model, but the script never silently downloads one.

## Compare generated answers at fixed evidence

The ten-question generation fixture covers gross/monthly conversion, explicit net pay, complete and partial deductions, annual deduction periods, bonus caps, reimbursement, employee mismatch, unknown installments and currency mismatch. Run v4 against v5 with the same retrieved five-excerpt context and temperature (twenty generations):

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --dataset evaluation/salary_cases.json \
  --allow-inference --profiles baseline --temperature 0 \
  --prompt-versions employee-assistant-v4,salary-grounding-v5 \
  > salary-answer-comparison.json
```

Review each substantive claim against the actual excerpts. Generation-fixture retrieval can still miss or mix evidence; distinguish that from reasoning errors. Reverse prompt order for another run if measuring latency or reproducibility. To attach advisory claim review to every generated answer, add `--salary-support-check`; this adds one model call per successful answer. Results appear in `salary_support_review`, separately from generation status and deliberately unscored human `review` fields. Review duration is recorded separately from generation time. Checker failure never alters a generated answer or invents a successful generation. No new dependencies or models are needed.

Run the existing organisation-policy suite too when assessing regressions. Production sampling remains provider-default; temperature zero is an evaluation override, not a determinism guarantee.

## Verification and limitations

126 backend tests pass, including the existing access/migration suite and pending PDF fixes. New tests verify full-answer review input, mixed supported/unsupported claims, invalid reviewer outputs, advisory supported reviews, check failure isolation, balanced fixture labels and inference opt-in. Tests use provider doubles; they do not establish real-model error detection or answer accuracy. No actual Ollama inference result or false-positive rate has been claimed. Use the generated reports to decide whether a narrowly scoped retry or safe fallback is justified in a later change; none is wired into live chat here.

The included PDF normalization change affects newly indexed files. Existing stored PDF chunks need controlled re-indexing or re-upload with preserved access, as described in [readable PDF answers](readable-pdf-answers.md). The salary prompt requires no re-index or database migration.

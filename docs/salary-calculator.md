# Bounded salary calculations (experimental, disabled by default)

The salary comparison showed that adding instructions fixed one missing-deduction case but caused incorrect arithmetic elsewhere. This path removes supported arithmetic from free-form generation. It does not rely on the experimental model reviewer, which remains advisory and disabled unless explicitly invoked in evaluation.

## Scope and validation

`services/salary_calculator.py` implements a narrow, deterministic grammar, not a general financial-document parser. It recognizes explicitly named source blocks (`Name: ...` and certain `Name is offered/appointed` starts), supported currency-labelled gross/net amounts and a limited set of complete deduction statements. Supported currencies are INR, USD, EUR and GBP. Facts record kind, Decimal amount, currency, citation marker and the exact matching source quote. Evaluation also includes cited source passages so installment and completeness assertions can be inspected.

For derived net pay, closed statement templates validate the whole person's block: monthly gross with income tax and insurance explicitly for that month and no other deductions; monthly gross with an explicit total monthly deduction and no other deductions; or annual gross in twelve equal installments with an annual deduction total split equally across those installments and no other deductions. Amounts/quotes alone are not considered sufficient proof. Extra unparsed deductions, percentages, incompatible periods/currencies, conditions, conflicting inputs, unsupported formats and missing complete inputs cause abstention. Arithmetic uses Decimal; display rounds to two places with ROUND_HALF_UP. It is not jurisdiction-specific payroll/tax software.

Explicit final monthly net amounts can be returned directly, while conflicts with gross or additional deduction fields require reconciliation. Annual-to-monthly gross conversion requires an explicit twelve-equal-installment schedule. The code does not assume a payment schedule, tax rate, exchange rate, bonus or reimbursement treatment. It does not combine financial fields across source blocks. Matching an explicitly named employee and date is required; multiple periods prompt clarification. For self-referential questions, the authenticated full member name must match the source name; email is not treated as proof of identity.

Only narrow net-pay/take-home or monthly-gross/installment questions route here. Bonus-only, generic salary questions and other document questions continue through the existing model flow. An unsupported salary format on a handled question returns an explanation/clarification, never an LLM retry or silent fallback. Broader summaries, multilingual names/formats, tables, statutory deductions and arbitrary offer-letter prose are not fully supported. Do not enable this as a general financial guarantee.

## Offline comparison using the report you already have

After merging, pulling main and rebuilding the API, use the exact existing report without embedding, generation or reviewer calls:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_salary_calculations.py \
  --report-file /dev/stdin < salary-answer-comparison.json > salary-calculation-comparison.json
```

The tool groups identical question/evidence contexts, retains previous prompt answers, records parsed facts and produces coverage counts. It does not automatically grade accuracy. On the uploaded fictional report: ten unique contexts yielded three supported net amounts (Mira, Dev and Omar each INR 70,000), six insufficiency explanations and one unhandled bonus case. Bob's known INR 80,000 monthly gross is preserved while take-home stays unknown. These are inspected development examples, not a general accuracy benchmark. No model was run for this replay.

For a fresh retrieval evaluation, use:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --dataset evaluation/salary_cases.json --allow-inference --profiles baseline \
  --temperature 0 --financial-calculations > salary-calculator-retrieval-review.json
```

This uses the existing embedding model and may call the answer model for unhandled questions such as the bonus case. Do not combine with prompt-version comparison. Rows identify `answer_origin`, include calculator facts/status when handled, and leave model token counts unset for deterministic answers. Human correctness/claim reviews remain unscored. Do not add the unreliable reviewer unless specifically evaluating it.

## Optional local application trial

The default is `FINANCIAL_CALCULATIONS_ENABLED=false`; merging does not enable the live path. After reviewing results, an administrator can set the root `.env`:

```dotenv
FINANCIAL_CALCULATIONS_ENABLED=true
```

Then recreate the API:

```sh
docker compose -p rag-updated up -d --build api
```

The normal permission-scoped retrieval runs first. The calculator receives only those retrieved passages; document scoping cannot widen access. Unsupported handled questions abstain; all other questions use the normal prompt. Names and source formats must match the narrow grammar, so start with fictional documents, explicit employee names and document-scoped questions. Leave it disabled for confidential/production payroll decisions until representative formats and false abstentions have been reviewed. Set false and recreate `api` to disable it again. No schema change or re-index is needed for this feature.

## Verification

Regression tests cover the reported gross/net and annual-deduction failures; partial deduction sets; period, currency and employee mismatches; conflicting facts; unknown installments; decimal subtraction; malformed/extreme numbers; unparsed pension/percentage deductions; exact source/citation mapping; offline report comparison; and live permission boundaries. No extra model/dependency is installed. The existing prompt and retrieval tests continue to run. The test suite and the offline replay do not establish correctness on arbitrary payroll documents or guarantee model fallback answers on unhandled questions.

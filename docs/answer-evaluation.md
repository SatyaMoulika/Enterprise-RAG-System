# Organisation-policy answer evaluation and optional re-ranking

## What is enabled

Normal application defaults stay unchanged: dense retrieval, up to five excerpts and **no cross-encoder**. No new model is fetched at startup. This milestone adds a reviewable answer experiment before changing the live pipeline.

The new fictional organisation-policy dataset has 12 chunks and 17 labelled questions. It covers current versus archived leave policies, contractors, P1/P2 response deadlines, log/backup retention, account permissions, multi-source questions, and unsupported private information. It is not your organisation's real policy corpus or a production-quality benchmark. To evaluate actual documents later, create a reviewed dataset with `chunks`, `queries`, `relevant_ids` and `reference_answer` fields; the runner does not silently read the live database.

## First run: baseline vs compact context, using existing Ollama models

After merging, pull main and rebuild only the API:

```sh
git switch main
git pull
docker compose -p rag-updated up -d --build api
```

Start with four representative cases (eight generated answers):

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --allow-inference --profiles baseline,compact \
  --case-ids current-leave,p1-response,retention-comparison,private-phone \
  > policy-answer-review.json
```

This calls the existing embedding and answer models with only the selected synthetic fixture content. It may take a while on CPU. It does not download an additional model, change live settings, mutate the database or re-index documents. Errors are explicit; failed generations are never presented as answers.

- **baseline** uses up to five excerpts.
- **compact** uses up to two, testing whether less distracting context helps while preserving multi-source evidence.
- Optional **reranked** cross-encodes the bounded candidate pool before selecting two excerpts.

All profiles use the application's actual ranking/context selectors and the same generation prompt. Embeddings and first-stage candidates are reused across profiles. Generation uses the provider's normal settings by default. Add `--temperature 0` for a controlled lower-randomness experiment; the report records the override, which is distinct from unchanged production sampling. Repeat experiments before inferring small differences.

Remove `--case-ids` to run all 17 cases. That produces 34 answers for two profiles. Generation time, actual Ollama prompt/output token counts when available, context size, retrieval metrics and excerpts are included. Ranking/generation measurements do not include the browser or database and are not end-to-end application latency.

## Read and review the report

Each row includes the question, reference answer, retrieved excerpt IDs/text, actual generated answer, timing and a review section. Check whether the answer:

1. Gives the correct current policy, rather than a plausible archived/distractor value.
2. Includes all requested facts, particularly both sources in comparison questions.
3. Makes only claims supported by the excerpts actually supplied.
4. Cites the excerpt that supports each claim.
5. Declines to invent an answer to unsupported questions.

The automatic `citation_reference_check` only verifies whether numeric `[n]` markers point to existing excerpts. It does **not** verify that a cited source supports a claim. Raw marker checks can also include markers inside quoted/code text. No faithfulness score is inferred from their mere presence.

Review fields deliberately start unscored:

```json
"review": {
  "correct": true,
  "refused": false,
  "claims": [
    {
      "text": "Application logs are retained for 30 days.",
      "supported": true,
      "cited": true,
      "citation_supported": true
    }
  ]
}
```

`correct` judges the answer against the reviewed reference. `supported` judges a substantive claim against the excerpts actually passed to the model, not general plausibility. `cited` says whether the answer attached a citation to that claim; `citation_supported` checks that the cited excerpt supports it. Use null for unreviewed values. A claim without citations should use `citation_supported: null`. Set `refused: true` only for a genuine refusal to provide the requested unsupported facts, not a disclaimer followed by an invented answer. A supported answer that says no resolution time is promised is an answer, not automatically a refusal.

Aggregate the filled report offline (no inference):

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --review-file /dev/stdin < policy-answer-review.json > policy-review-summary.json
```

The command above reads the edited report through stdin, so no extra container volume/copy is needed. A non-Docker alternative from the repository root is `uv run --directory backend --locked python scripts/evaluate_answers.py --review-file ../policy-answer-review.json`. The output reports reviewed answer correctness, claim faithfulness, citation precision/coverage, appropriate refusal on unanswerable cases, false refusal on answerable cases and review denominators. **Null means not reviewed.** Provider/re-ranker failures are counted separately, not silently excluded as successful answers. Preserve the case/reference fields when editing reviews, and review both profiles consistently.

## Optional cross-encoder experiment

This is a separate dependency/model installation, not required for the first run. It adds SentenceTransformers/PyTorch and may require substantial disk/RAM/downloads. The configured model is `cross-encoder/ms-marco-MiniLM-L-6-v2`; consult its model card before deployment. It runs on CPU with a 512-token pair limit, so long evidence may be truncated for scoring even though the returned source excerpt stays whole.

In the root `.env`, retain live re-ranking disabled while installing the optional extra:

```dotenv
RAG_INSTALL_RERANKING=true
RERANKER_MODE=none
```

Rebuild `api`, then explicitly allow the experiment to load/download its model:

```sh
docker compose -p rag-updated up -d --build api
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --allow-inference --allow-model-download --profiles baseline,reranked \
  --case-ids current-leave,p1-response,retention-comparison,private-phone \
  > reranked-policy-review.json
```

The cache lives in the separate `rag_reranker_cache` volume. Do not delete existing database/model/upload volumes to apply this change. For non-Docker development, install with `uv sync --directory backend --extra reranking`.

Only after comparing reviewed results should live `.env` use `RERANKER_MODE=cross_encoder`, followed by `docker compose -p rag-updated up -d api`. Switch back to `none` to disable it. The ranker processes only already-authorized candidates and does not rewrite questions or return confidence percentages. Its logits are ordering scores, not calibrated evidence thresholds. Per process, one re-rank operation runs at a time; busy/misconfigured rankers return a clear 503 rather than silently falling back to another pipeline. Model loading and scoring can add latency; measure before serving it publicly.

## What has and has not been verified

Validation: 94 backend tests pass; Ruff lint/format checks pass. The default backend Docker image builds successfully, imports the evaluation module and contains no SentenceTransformers dependency. Compose defaults keep optional installation and re-ranking disabled.

Automated tests cover report/review logic, failure handling, citation-marker checks, ranking before final top-k, authorization scope, optional model boundaries and unchanged default behaviour. Tests use provider/model doubles; they do not download the cross-encoder or generate real Ollama answers. No new correctness, faithfulness, refusal or re-ranking improvement score is claimed until actual reports are generated and reviewed.

This adds no automatic evidence rejection, query rewriting or arbitrary similarity threshold. Those require a larger representative evaluation and separate calibration/holdout cases.

## Follow-up after the first full policy review

The first 17-question report found that compact context dropped the current leave policy in a comparison, the model falsely refused the email-token question despite having the answer, and both profiles refused instead of explaining that no resolution guarantee exists. Some answers also lost contract exceptions or numeric citations. Keep dense retrieval, five excerpts and re-ranking disabled while testing prompt changes.

The shared application/evaluation prompt is now versioned as `policy-grounding-v2` in generated reports. It requests direct, concise answers, citations beside factual claims, preserved limits/exceptions, explicit negative policy answers, partial answers when appropriate, and current versus archived policy handling. These instructions are not an enforcement layer or proof of improved model output. Older reports without `prompt_version` used the original prompt.

After pulling and rebuilding the API, run the full comparison twice with the same models and explicit temperature. Save each result separately:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --allow-inference --temperature 0 --profiles baseline,compact \
  > policy-answer-review-v2-run1.json

docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --allow-inference --temperature 0 --profiles baseline,compact \
  > policy-answer-review-v2-run2.json
```

Review all cases, especially `contractor-leave`, `email-reuse`, `leave-comparison`, `resolution-time`, and missing citations. Temperature zero reduces sampling variability but does not guarantee reproducibility. The earlier report used provider-default sampling; comparisons with it change both prompt and temperature. Prompt length also increases input tokens. Compare correctness before optimizing token counts; timing includes model/cache/order effects. No real-model improvement is claimed by automated tests.

Once prompt behaviour is reviewed, use the separately opt-in cross-encoder instructions above and add `--temperature 0` for the reranking experiment. Keep the same prompt/model/temperature when comparing profiles, and check whether current policy ranks ahead of archived policy without dropping other required evidence.

## Controlled prompt comparison (production prompt unchanged)

Use `--prompt-versions` to compare the exact original prompt (`original-v1`), the current application prompt (`policy-grounding-v2`), and an experimental concise prompt (`concise-examples-v3`). The experiment requires `--profiles baseline --temperature 0`: five excerpts, the same models, no reranker, and identical question/context strings across variants. Embedding and retrieval run once; each selected prompt receives the same evidence. Only system instructions change. The concise prompt uses illustrative remote-work, equipment-delivery and shipping examples separate from the policy fixture; they are labelled as examples, not evidence. This is development evaluation, not an unseen holdout benchmark.

After merging, pulling main and rebuilding `api`, run:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --allow-inference --profiles baseline --temperature 0 \
  --prompt-versions original-v1,policy-grounding-v2,concise-examples-v3 \
  > policy-prompt-comparison-run1.json
```

This produces 51 actual generations (17 questions times three prompts) using existing Ollama models. For a small initial check, add `--case-ids contractor-leave,email-reuse,leave-comparison,resolution-time`, then run the full suite before drawing conclusions. Repeat the full command reversing `--prompt-versions` to `concise-examples-v3,policy-grounding-v2,original-v1` and save as `policy-prompt-comparison-run2.json`. Temperature zero is not a determinism guarantee; latency includes order/cache effects and differing instruction lengths.

Each row identifies its prompt version and has a profile such as `baseline/original-v1`. The existing offline review command groups these separately. Review correctness, exceptions, supported negative answers, partial answers and claim-level citations across all cases; do not optimize only known failures. Provider failures remain explicit and do not stop other variants. No candidate is promoted automatically. Production still uses `policy-grounding-v2` with unchanged sampling, dense retrieval, five excerpts and disabled re-ranking. Automated request/context tests cannot establish real model improvement.

## Citation order and follow-up policy checks

The candidate remains experimental. `--excerpt-order ranked|reversed|shuffled` changes presentation **after** selection and budgeting, not which evidence is selected. Markers are reassigned to the presented order; `excerpts` is the authoritative marker-to-source mapping. `ranked_ids` and retrieval metrics preserve original ranking, while `retrieved_ids` records presented order. Shuffling uses `--order-seed` plus case ID and is reproducible for the same selected evidence. A shuffle may happen to leave an order unchanged. Compare recorded evidence sets between separate runs; embedding/provider changes can affect retrieval.

The separate `evaluation/citation_policy_cases.json` fixture has nine fictional chunks and ten questions about expense limits, contract-like exceptions, exact approval boundaries, security methods, warranties and explicit negative guarantees. Two cases request unavailable personal information. It was authored after reviewing the earlier failures: it is follow-up development evaluation, not a blind holdout or proof of real-world quality. It does not reuse the candidate prompt's example scenarios.

After merging, pulling main and rebuilding the API, run all three prompt variants against the new cases with three presentation orders (90 generations total):

```sh
for order in ranked reversed shuffled; do
  docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
    --dataset evaluation/citation_policy_cases.json \
    --allow-inference --profiles baseline --temperature 0 \
    --prompt-versions original-v1,policy-grounding-v2,concise-examples-v3 \
    --excerpt-order "$order" --order-seed 17 \
    > "citation-policy-${order}.json"
done
```

Also check the known leave-comparison citation failure under a different evidence order:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_answers.py \
  --allow-inference --profiles baseline --temperature 0 \
  --prompt-versions original-v1,policy-grounding-v2,concise-examples-v3 \
  --excerpt-order reversed \
  > policy-prompt-comparison-reversed.json
```

Review against each report's actual excerpts. For each claim, verify the cited marker supports that specific claim, current policies support current amounts, exceptions/limits remain intact, and missing evidence produces partial answers or appropriate refusal. A valid marker number is insufficient. For the leave comparison, the 20-day claim must cite the current policy regardless of its new marker. For receipt/security exceptions and expense comparisons, ensure retrieved evidence is complete before attributing an error to the prompt.

Use the existing review fields and offline summary per report; keep order reports separate. Check all cases for regressions, not just previously failing questions. Production defaults and prompts remain unchanged. Automated tests verify ordering, evidence preservation, marker mapping, repeatability and unchanged ranking metrics, not claim support or model correctness. Promote no candidate automatically; review real outputs first, and evaluate reranking separately afterwards.

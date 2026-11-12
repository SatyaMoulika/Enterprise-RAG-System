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

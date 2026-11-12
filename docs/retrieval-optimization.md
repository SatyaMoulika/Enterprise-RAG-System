# Retrieval optimization: baseline first, then hybrid search

## What changed

Three selectable strategies now share the same authenticated workspace/model filter:

- `dense`: exact cosine similarity, retained as the default baseline.
- `bm25`: keyword retrieval over title and chunk text, with k1=1.2, b=0.75, positive Robertson IDF, case-folded tokens, a small English stop list, and full/segmented identifiers such as PTO-2026.
- `hybrid`: dense and BM25 candidate lists merged using reciprocal rank fusion: each ranker contributes `1 / (60 + rank)`. This combines ranks rather than incompatible raw scores. It is not a learned cross-encoder re-ranker.

Both rankers operate only on chunks from the current workspace, live documents and configured embedding-model identity. BM25 document frequencies are workspace-local. Deleted data and another workspace cannot enter the candidate lists or affect their term statistics. No private corpus is cached globally.

The default candidate pool is 20 per ranker and the final result is up to five chunks. Exact duplicate text is removed within a document. Cross-document copies retain their distinct provenance. A 24,000-character context budget includes the serialized source labels; oversized candidates are skipped whole, never sliced mid-sentence. The budget can be lowered after evaluating quality/resource tradeoffs. It is a character bound, not an exact model token budget or a guarantee that the model's context window is sufficient.

Dense vector normalization is numerically stable for large finite values. Retrieval still scans a bounded set of up to 10,000 chunks; BM25 is computed in memory on each request. This improves retrieval options, not database-scale indexing. PostgreSQL/pgvector and indexed full-text search remain the next scaling step if measured latency/corpus size require them.

There is no new model download, query rewrite call, automatic provider fallback, confidence claim or arbitrary relevance threshold. Hybrid still requires working query embeddings. BM25 avoids the query embedding call, but uploads still need embeddings and answers still require the configured answer model. Query rewriting and cross-encoder re-ranking remain deliberate later experiments.

## Evaluation included

`backend/evaluation/retrieval_cases.json` contains ten synthetic source chunks with manually specified evidence labels for eleven answerable questions and two unanswerable questions. It includes exact identifiers, acronyms, paraphrases and one question requiring two excerpts. It does not contain private uploaded documents or validated healthcare knowledge.

The runner measures Precision@k (denominator k, even when fewer results are returned), Recall@k, MRR@k and binary nDCG@k on answerable questions. Duplicate IDs cannot inflate hits. Unanswerable examples are reported separately using an empty-result rate, not scored as zero-recall answerable questions. An empty-result rate is NOT an LLM refusal or hallucination metric.

The committed BM25-only synthetic report at `backend/evaluation/reports/bm25-synthetic.json` was actually run offline:

| Metric @5 | BM25 fixture result |
|---|---:|
| Precision | 0.1818 |
| Recall | 0.8182 |
| MRR | 0.8182 |
| nDCG | 0.8182 |
| Empty results on two unanswerable examples | 1.0 |

The lexical run misses the two paraphrase-only questions. Low Precision@5 also reflects that keyword search often returns one matching excerpt rather than filling all five positions. These are small regression results, not evidence of production quality or improvement over the real dense model. Per-query ranking times exclude database access, embedding calls and generation and should not be presented as end-to-end latency.

## Compare using your installed model

After merging, pull and rebuild the API while preserving existing volumes/models:

```sh
git switch main
git pull
docker compose -p rag-updated up -d --build api
```

Run all three strategies against identical labels and actual Ollama embeddings:

```sh
docker compose -p rag-updated exec -T api .venv/bin/python scripts/evaluate_retrieval.py --strategy all --allow-inference > retrieval-report.json
```

This sends only the public fixture text to the configured local Ollama instance, not your uploaded documents. It embeds fixtures/questions once and reuses the vectors across the comparison. Actual-model comparison was not run in the agent environment because the user's running model service is on their own machine; no model results are fabricated.

Compare at k=1 and k=5, inspect per-query failures and then add a reviewed evaluation set representative of your actual documents. A small synthetic fixture should not decide production relevance thresholds.

## Enable hybrid

Add or edit this line in the root `.env`, keeping existing secrets:

```dotenv
RETRIEVAL_STRATEGY=hybrid
```

Then recreate the API service so Compose passes the setting:

```sh
docker compose -p rag-updated up -d api
```

Existing vectors are reused: no document re-upload, migration, volume reset or model download is required. Set the value back to `dense` and repeat the recreate command to restore the baseline. Other optional controls are `RETRIEVAL_TOP_K`, `RETRIEVAL_CANDIDATES` (at least top-k) and `RETRIEVAL_CONTEXT_CHARACTERS`.

## Next experiments

1. Evaluate actual-model dense vs hybrid on representative reviewed queries, including unsupported questions and exact product/policy terms.
2. Add a cross-encoder only if candidate recall is good but ordering is weak; measure its latency and memory.
3. Add conversation-aware query rewriting only with explicit history handling and tests against invented names/constraints.
4. Calibrate evidence rejection with labelled unanswerable questions. RRF/cosine scores must not be displayed as answer-confidence percentages.
5. Evaluate generated answer correctness, faithfulness and citation support separately; this retrieval runner does not measure those.

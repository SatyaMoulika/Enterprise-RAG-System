# Readable PDF evidence and employee answers

The word-per-line display is not a deliberate word-sized chunking strategy. Chunks contain text whose line breaks are preserved by the source panel. When PDF extraction places blank lines between words, the old paragraph cleanup treats each word as its own paragraph. That can also make chunks split inside a sentence. The new cleanup recognizes long prose streams (at least 30 nonempty lines, at least 85% single-token lines and at least two sentence endings) and joins the words before sentence-aware chunking. Each PDF page is cleaned separately. Explicit lists and tab/pipe-delimited tables retain their structure. This is a conservative text heuristic, not general table reconstruction or OCR; short or mixed-layout cases may still need inspection.

The exact PDF from the reported screenshot was not attached, so that document's raw extraction has not been inspected. Regression checks reproduce both one-newline and blank-line-separated word streams, and test page-level cleanup. Existing PDF wrap/list/table checks continue to run.

The model context retains stable numbered sources and filenames to distinguish documents, but removes internal `(chunk 0)` labels. Production prompt `employee-assistant-v4` adds natural employee-facing wording, numeric-only citations in answer prose, concise letter summaries and explicit separation of offer versus appointment details. Source titles remain visible in the evidence panel. Earlier v1/v2/v3 prompts remain available for evaluation; v3 is not silently promoted. Neither prompt instructions nor automated provider doubles guarantee actual model tone, correctness or citation alignment.

## Apply to an existing local workspace

After merging, preserve local changes, pull main and rebuild the API:

```sh
git switch main
git pull --ff-only
docker compose -p rag-updated up -d --build api
```

Prompt/context changes apply to new questions immediately. Extraction changes apply only when indexing a file; existing chunks and embeddings do not change automatically. For the fictional test PDFs:

1. As admin, record each document's personal/restricted recipient assignment.
2. Keep a local copy of the original file. Delete its old entry and upload it again, selecting the SAME access before uploading. Upload only one format to avoid duplicate evidence.
3. Clear the previous conversation (or sign out/in), select **Ask about this** on the offer letter, and ask: `Summarize my offer letter in a few clear bullet points.`
4. Verify prose paragraphs rather than vertical words in the evidence, natural answer wording with `[n]` citations, no file/chunk labels in answer prose, and preserved pay/leave/notice conditions. Do not expect a complete-letter summary if retrieval supplies only some terms.
5. Compare all-document chat with document-scoped chat: an appointment's equipment collection details should not be described as offer-letter terms. Confirm another employee still cannot access the personal file after re-upload.

Deletion/re-upload changes the document ID and removes its old indexed evidence. Already delivered answers cannot be changed retroactively. For real documents, plan a controlled re-index rather than deleting the only copy. No automatic data mutation or migration is included in this change.

For controlled prompt evaluation, use the existing runner with `--profiles baseline --temperature 0 --prompt-versions policy-grounding-v2,concise-examples-v3,employee-assistant-v4`. All variants now receive the same context without chunk labels; old report timings/answers used a different context format and should not be compared as prompt-only differences. Review the full suite for regressions before making quality claims.

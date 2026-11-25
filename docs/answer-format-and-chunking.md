# Readable answers and sentence-aware excerpts

## Answer rendering

The React chat now uses `react-markdown` with `remark-gfm`. It supports headings, emphasis, lists, inline/fenced code, block quotes and GitHub-style tables. Tables and code blocks scroll within the answer card. Ollama's system instruction requests Markdown when useful and keeps numbered source markers such as `[1]`.

Raw HTML is skipped. Unsafe link schemes are rejected, external links are isolated, and model-generated images are shown as alternate text rather than initiating image requests. Document excerpts and user questions remain plain text. Formatting does not make generated claims more trustworthy: users should still inspect the retrieved evidence.

## Chunking and PDF wrapping

The current Ask documents sidebar displays documents rather than individual chunks. Multiple citations to one file share a document card, while their original reference numbers and cited page ranges remain visible. Select a citation, then View document to inspect the original at that reference's page. Extracted passages remain in the API response for provenance; they are no longer rendered as sidebar cards. This presentation change does not require reindexing or change retrieval.

The old indexer sliced every 500 characters, with a 50-character offset. A new slice could begin in the middle of a word or end halfway through the table introduction seen by the user.

The new indexer:

- Detects sentence endings while handling common English abbreviations, initials, decimals and numbered list prefixes.
- Groups complete sentences toward `CHUNK_SIZE` (default 500 characters), retaining paragraph breaks where they fit.
- Treats the size as a soft target: a single sentence can exceed it rather than being cut immediately.
- Carries overlap as whole units. `CHUNK_OVERLAP` is now an approximate context target, not a raw substring length; overlap is dropped if it would leave no room for new text.
- Caps any one unit at `CHUNK_MAX_CHARACTERS` (default 4000, at least CHUNK_SIZE). Exceptionally long sentences/table-like runs fall back to whitespace boundaries. Unbroken tokens beyond that limit are rejected instead of cut mid-word. Chunk-count and document-size limits still apply.

Align larger chunk settings with the chosen embedding model's context limit; there is no claim that a character budget is an exact token budget.

PDF extraction also unfolds soft line wraps and discretionary soft hyphens while retaining blank paragraphs, explicit list lines and explicit table columns. Literal compound hyphens are preserved. This is conservative whitespace cleanup, not OCR or a layout-aware table parser. Existing extraction artefacts, missing source text, multi-column ordering and flattened tables cannot be reliably reconstructed by a sentence splitter. The splitter uses lightweight English-oriented heuristics, not a universal linguistic parser.

Citations are still the actual stored text passed into retrieval/context; they are not model-generated completions of fragments.

## Apply to existing documents

No schema migration or automatic alteration of existing documents is required. The new chunker runs during indexing, so already-indexed chunks stay as they are.

After updating and rebuilding the API and web services:

```sh
git switch main
git pull
docker compose -p rag-updated up -d --build api web
```

Upload a fresh copy of an affected document. Once indexing succeeds, remove the older copy (the smaller document ID) from Documents. Keeping both copies means the older fragments can still appear among retrieved excerpts. Do not delete Docker volumes or reset the database to apply this change. The Ollama models do not need to be downloaded again.

## Verification

53 backend tests pass, including complete sentence grouping, whole-sentence overlap, abbreviations/decimals, paragraph structure, oversized text boundaries, limits and extraction from a real generated two-line PDF. 31 frontend tests pass, including Markdown structure, GFM tables, unsafe link/HTML rejection and disabled remote images. TypeScript/Vite and formatting checks pass. No new real-model quality benchmark or browser visual acceptance is claimed by this change.

## Source-aware indexing update

New indexing preserves source page numbers, normalized page offsets and recognized Markdown/uppercase section headings. Lists and explicit table blocks are kept as structural units rather than flattened by sentence joining. PDF pages containing images but no extractable text are rejected, including in mixed text/scanned files. Blank/textless pages produce persisted extraction notes; every PDF also carries a layout limitation note. Mixed content with both text and images still requires visual source verification. OCR and general visual table reconstruction are not implemented.

The React upload workflow now queues durable background indexing. The document list polls queued/indexing states and exposes failures, extraction notes and a retry/reindex action. A single worker processes each job in a separate process with configurable memory and wall-time limits. Work is retried from the original file, not resumed partway through a provider batch. The synchronous upload API remains available for integrations that omit the `background` form field.

Use **Reindex** on existing documents to apply the new chunker; re-uploading and deleting old copies is no longer necessary. Until a rebuild succeeds, old chunks remain usable. Failed jobs retain their source and a safe error for retry. `scripts/ingestion_worker.py --recover-stale-minutes 30` marks interrupted indexing attempts failed after a timeout longer than the worker's job limit.

Administrators can queue `POST /documents/{id}/reindex`, or send a new file to `POST /documents/{id}/replace`. Replacement keeps the document ID and access grants. The previous file and index stay active until the worker atomically swaps both; failed replacements leave them intact. `DELETE` cleans active and staged files. Identical uploads reuse an existing document only when filename, content hash, visibility and recipient grants match. This deduplicates sequential retries; concurrent identical uploads can still race and should use replacement/reindex when editing a known document.

Deploy the migration and worker with the updated services (retain all existing volumes):

```sh
docker compose -p rag-updated up -d --build api ingestion_worker web
```

The API startup runs migration `0005`; the worker waits for the API's database readiness check. Reindex stored documents after deployment to populate their source metadata. No existing document is automatically rewritten by the migration.

## Readable citations and paragraph indexing

The current indexer is `source-paragraphs-v3`: it keeps fitting paragraphs intact, uses sentence boundaries for larger paragraphs, and reserves whitespace splitting for oversized units. Short word-per-line PDF prose is repaired within a page, even beside a heading or list. This is whitespace recovery, not invented text or visual table reconstruction. Existing stored documents need **Reindex** to receive the new extraction/chunking.

Answer citations are clickable source buttons. They focus/open the corresponding passage, whose label uses document title, page range and section rather than internal chunk ordinals. The first cited passage is expanded; uncited retrieved material is separated under Other retrieved passages. Original PDFs open at the cited page when the browser PDF viewer supports page fragments. Legacy word-per-line source text is visually wrapped as prose without changing or completing its stored content.

The answer model now returns structured text/source-number fields; the application renders citation markers from those explicit fields. Marker range and coverage checks still run, and at most one bounded revision is attempted on invalid output. No source number is guessed from similarity or appended to an unsupported statement. Semantic support still requires evaluation; JSON structure alone is not faithfulness proof.

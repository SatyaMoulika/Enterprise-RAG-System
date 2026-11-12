# Readable answers and sentence-aware excerpts

## Answer rendering

The React chat now uses `react-markdown` with `remark-gfm`. It supports headings, emphasis, lists, inline/fenced code, block quotes and GitHub-style tables. Tables and code blocks scroll within the answer card. Ollama's system instruction requests Markdown when useful and keeps numbered source markers such as `[1]`.

Raw HTML is skipped. Unsafe link schemes are rejected, external links are isolated, and model-generated images are shown as alternate text rather than initiating image requests. Document excerpts and user questions remain plain text. Formatting does not make generated claims more trustworthy: users should still inspect the retrieved evidence.

## Chunking and PDF wrapping

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

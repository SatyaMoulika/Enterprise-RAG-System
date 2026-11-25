# Employee document hub

Employees land in **Overview**, which shows their accessible documents, indexing activity and recent sources. **My documents** provides Personal, Company and Restricted categories, filename search and category counts based on the documents they can access. **View** loads the original file through an authenticated endpoint, displaying text or the browser's PDF viewer, with a download option. **Ask about this** starts a fresh conversation scoped to one document; **Search all my documents** starts a fresh conversation across all accessible documents. A citation's **View document** action uses the same protected file endpoint. File preview requires the original file still to exist in the configured upload directory; older missing files return an explicit error. PDF rendering depends on the browser; download is available as a fallback.

## Administrator workflow

The Ask documents sidebar lists one card per source document, grouping all references to the same document ID. Cards show the filename, cited page ranges and original reference numbers, with a View document action; extracted chunks are not displayed in the sidebar. Selecting an answer citation focuses its document and makes View document open that reference's original page. Uncited retrieved documents are kept in a separate collapsed list and are not labelled as cited evidence. Source preview still uses the authenticated file endpoint. Starting a new question closes the previous preview, and selecting an older answer citation restores that answer's document list.

Chat validates an explicitly selected document's workspace and read permissions before identity routing, personal-letter resolution or search. Missing, deleted, foreign-workspace and inaccessible files return the same HTTP 404 without revealing whether another user's file exists. Retrieval checks access again and keeps the permission filter in ranking and neighboring-passage queries. An accessible selected file with no indexed text returns HTTP 409 with processing, failure or reindex guidance, rather than the generic no-evidence answer. Existing chunks remain available during a queued, running or failed reindex. The file-preview endpoint shares the same read-access check.

1. Use Members to create employee accounts in this workspace.
2. In My documents, choose the file and its access before uploading:
   - Company: everyone in the workspace.
   - Personal: one selected account, for example an offer or appointment letter.
   - Restricted: one or more selected accounts, for example product or team policies.
3. Upload and index. The document, access grants and embeddings commit together; there is no initial company-wide upload followed by a permission patch.
4. Use Manage access to replace the complete recipient list or change visibility later. Administrators can inspect and manage every document in their own workspace, including personal letters. This is stated in the access form; personal does not mean hidden from administrators.

Employees cannot upload, delete or change grants. They do not need to pick a document to ask general company questions: unscoped chat searches all documents they can access. Restricted sharing currently uses individual accounts, not groups, departments or SSO.

## Access enforcement

A shared database predicate scopes listing, file delivery and candidates for dense, BM25 and hybrid retrieval before ranking, embedding query generation, context construction and optional cross-encoder scoring. Explicit document scope narrows that accessible set and cannot widen it. An inaccessible scoped document produces no excerpts, without disclosing whether it exists. File endpoints return 404 for inaccessible or foreign documents; they do not expose stored paths. Files use no-store and nosniff response headers, and the web client requests responses without caching or putting tokens in URLs. Preview URLs are temporary browser blobs, revoked when the preview closes.

Grants reference account IDs, not email addresses. Removing an account cascades its grants; recreating its email does not regain access. A personal/restricted document with no remaining grants is accessible only to administrators. Access changes apply to subsequent retrieval/file requests. Previously delivered answers, downloads and requests already running cannot be recalled; users should clear a conversation or sign out to discard its in-memory history. The app does not yet provide audit logs, document-level encryption keys, OCR, grouped access or external HR integrations. Offer/appointment letters are documents, not structured HR records.

## Upgrade and run

Merge the PR, preserve any local edits, then from the existing checkout:

```sh
git switch main
git pull --ff-only
docker compose -p rag-updated up -d --build api ingestion_worker web
```

API startup runs migration `0003`, adding document visibility and recipient grants. **All existing documents remain company-wide**, preserving their earlier access. Before using this for confidential letters, review existing uploads and assign personal/restricted access where appropriate. No re-index is required for permissions. Keep the existing Compose project name and database/upload/model volumes; do not delete volumes. Open http://localhost:8080, sign in as an administrator, create two test employees and verify each can list, view and chat only with the assigned letters plus shared company documents.

## Validation

Backend tests cover tenant isolation, personal/restricted listing, protected files, scoped chat, all three retrieval strategies plus the optional reranker boundary, grant replacement/revocation, account removal and email reuse, invalid recipients and migration compatibility. Frontend tests cover category filtering, scoped chat and atomic personal upload data as well as existing flows. Browser checks use the real app/API with a disposable SQLite database and stubbed AI providers: employee isolation, text preview, scoped chat, admin reassignment and revocation, desktop/mobile layouts. Real model answer accuracy, browser PDF rendering and PostgreSQL concurrency/load require separate verification before production deployment.

## Member selection and display names

Member creation includes an optional name (up to 120 characters); names are trimmed and shown alongside email addresses in the member list and recipient picker. Existing accounts without a name continue to display their email. Migration `0004` adds the name column without changing identity, passwords or document grants.

Restricted sharing uses individual checkboxes, name/email search and a selected-count label. Tick two or more employees normally; no Ctrl/Cmd selection is needed. Filtering the list does not clear checked recipients. Personal sharing remains a single-employee dropdown.

Creating or removing members invalidates mounted recipient pickers. Returning to My documents, refocusing the browser window or clicking Refresh members fetches current active accounts. Obsolete requests are cancelled/ignored, and unavailable accounts are removed from current selections with a review notice. Upload/save rejects an empty personal/restricted recipient selection. Changes from another session are picked up on these refresh triggers, not through live push notifications; the backend always validates recipients again before saving.

After merging, pull main and rebuild both `api` and `web` using the upgrade command above. No document re-index or re-upload is needed for these member-selection changes.

## First-person letters and authenticated identity

Employees can ask “explain my offer letter”, “what role am I offered?”, or “what is my work location in my appointment letter?” without naming themselves or manually selecting a file. The server resolves these requests from the authenticated account and **Personal** document assignments to that account ID. Administrators' ability to read everyone's documents is not treated as personal ownership. A matching filename, a shared display name, a company-wide document or a name claimed in chat cannot establish that a letter belongs to the signed-in account.

To enable this, create the employee account with its name and email, upload each letter as **Personal**, and select the employee as its recipient. Existing letters can be assigned through **Manage access**; no reindexing is required just to change the recipient. Offer and appointment letters are distinguished from their filenames or an identifiable indexed introduction. Generic or unrecognizable documents may require explicit selection or administrator review.

The selected personal letter is read within the normal context budget and its passages remain cited. Multiple matching letters prompt the employee to choose one instead of guessing the newest version. If the chat is already scoped to another file, the server asks the user to switch files/search all rather than silently changing scope. A clear mismatch between a letter's named subject and the account profile prompts an assignment/name check. Revoked assignments are checked on the next request.

For deterministic salary calculations, a unique subject explicitly identified in the assigned letter may bind the financial inputs even when the account's display name is missing. This uses the personal assignment first; names never create permissions. “Who am I?” is answered from the signed-in profile and needs no document citation. Claimed identities in chat do not alter the account, its assignments or the people whose terms may be described as “yours”. This change does not add persistent conversation memory.

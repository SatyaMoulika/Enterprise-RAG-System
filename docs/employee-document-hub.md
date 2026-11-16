# Employee document hub

Employees now land in **My documents**, with Personal, Company and Restricted categories, filename search and category counts based on the documents they can access. **View** loads the original file through an authenticated endpoint, displaying text or the browser's PDF viewer, with a download option. **Ask about this** starts a fresh conversation scoped to one document; **Search all my documents** starts a fresh conversation across all accessible documents. A citation's **Open source document** action uses the same protected file endpoint. File preview requires the original file still to exist in the configured upload directory; older missing files return an explicit error. PDF rendering depends on the browser; download is available as a fallback.

## Administrator workflow

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

Grants reference account IDs, not email addresses. Removing an account cascades its grants; recreating its email does not regain access. A personal/restricted document with no remaining grants is accessible only to administrators. Access changes apply to subsequent retrieval/file requests. Previously delivered answers, downloads and requests already running cannot be recalled; users should clear a conversation or sign out to discard its in-memory history. The app does not yet provide audit logs, document-level encryption keys, OCR, page/section metadata, grouped access or external HR integrations. Offer/appointment letters are documents, not structured HR records.

## Upgrade and run

Merge the PR, preserve any local edits, then from the existing checkout:

```sh
git switch main
git pull --ff-only
docker compose -p rag-updated up -d --build api web
```

API startup runs migration `0003`, adding document visibility and recipient grants. **All existing documents remain company-wide**, preserving their earlier access. Before using this for confidential letters, review existing uploads and assign personal/restricted access where appropriate. No re-index is required for permissions. Keep the existing Compose project name and database/upload/model volumes; do not delete volumes. Open http://localhost:8080, sign in as an administrator, create two test employees and verify each can list, view and chat only with the assigned letters plus shared company documents.

## Validation

Backend tests cover tenant isolation, personal/restricted listing, protected files, scoped chat, all three retrieval strategies plus the optional reranker boundary, grant replacement/revocation, account removal and email reuse, invalid recipients and migration compatibility. Frontend tests cover category filtering, scoped chat and atomic personal upload data as well as existing flows. Browser checks use the real app/API with a disposable SQLite database and stubbed AI providers: employee isolation, text preview, scoped chat, admin reassignment and revocation, desktop/mobile layouts. Real model answer accuracy, browser PDF rendering and PostgreSQL concurrency/load require separate verification before production deployment.

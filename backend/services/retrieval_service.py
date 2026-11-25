from dataclasses import replace

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import defer

from core.config import settings
from core.errors import ProviderUnavailable
from models.document import Document
from models.document_chunk import DocumentChunk
from services.document_access import accessible_documents, require_document_read_access
from services.embedding_service import EmbeddingService
from services.generation_protocol import chat_payload, prompt_size
from services.indexing_service import embedding_identity
from services.prompt_service import PromptService
from services.reranking_service import rerank_chunks
from services.search import SearchChunk, select_context, stream_candidates


def context_budget(question):
    try:
        payload = chat_payload(
            question,
            "",
            settings.OLLAMA_CHAT_MODEL,
            structured=True,
            context_tokens=settings.GENERATION_CONTEXT_TOKENS,
            answer_tokens=settings.GENERATION_MAX_TOKENS,
        )
    except ValueError as exc:
        raise ProviderUnavailable("The question exceeds the configured generation budget") from exc
    return (
        settings.GENERATION_CONTEXT_TOKENS
        - settings.GENERATION_MAX_TOKENS
        - prompt_size(payload)
        - 256
    )


def selected_document_context(db, base, available_bytes):
    """Read a short selected file completely, without requiring query similarity.

    None means the file is too large for a full read and must use ranked search.
    The caller's query already enforces workspace and document permissions.
    """
    result = db.execute(
        base.options(defer(DocumentChunk.embedding))
        .order_by(None)
        .order_by(DocumentChunk.chunk_index, DocumentChunk.id)
        .execution_options(yield_per=64)
    )
    passages = []
    try:
        for chunk, title in result:
            passages.append(source_chunk(chunk, title, False))
            text = PromptService.build_context([passage.context() for passage in passages])
            if (
                len(text) > settings.RETRIEVAL_CONTEXT_CHARACTERS
                or len(text.encode("utf-8")) > available_bytes
            ):
                return None
    finally:
        result.close()
    groups = []
    for passage in passages:
        if (
            groups
            and passage.section_key
            and passage.section_key == groups[-1][-1].section_key
            and passage.document_id == groups[-1][-1].document_id
            and passage.chunk_index == groups[-1][-1].chunk_index + 1
        ):
            groups[-1].append(passage)
        else:
            groups.append([passage])
    return [
        expand_evidence(group[0], group) if group[0].section_key else group[0] for group in groups
    ]


def source_chunk(c, title, include_embedding=True):
    return SearchChunk(
        id=c.id,
        document_id=c.document_id,
        title=title,
        chunk_index=c.chunk_index,
        chunk_text=c.chunk_text,
        embedding=c.embedding if include_embedding else None,
        **{
            name: getattr(c, name)
            for name in (
                "page_start",
                "page_end",
                "section",
                "section_key",
                "start_offset",
                "end_offset",
            )
        },
    )


def expand_evidence(anchor, neighbors):
    """Merge only contiguous chunks in a known source section; never infer ownership."""
    if not anchor.section_key or not neighbors:
        return anchor
    rows = sorted(
        [
            c
            for c in neighbors
            if c.document_id == anchor.document_id and c.section_key == anchor.section_key
        ],
        key=lambda c: c.chunk_index,
    )
    if not rows or anchor.chunk_index not in {c.chunk_index for c in rows}:
        return anchor
    if any(b.chunk_index != a.chunk_index + 1 for a, b in zip(rows, rows[1:])):
        return anchor
    text = rows[0].chunk_text
    for previous, current in zip(rows, rows[1:]):
        overlap = 0
        if (
            current.page_start == previous.page_end
            and previous.end_offset is not None
            and current.start_offset is not None
        ):
            overlap = max(0, previous.end_offset - current.start_offset)
        text += ("" if overlap else "\n\n") + current.chunk_text[overlap:]
    same_page = rows[0].page_start == rows[-1].page_end
    return replace(
        anchor,
        chunk_index=rows[0].chunk_index,
        chunk_end_index=rows[-1].chunk_index,
        chunk_text=text,
        page_start=rows[0].page_start,
        page_end=rows[-1].page_end,
        start_offset=rows[0].start_offset if same_page else None,
        end_offset=rows[-1].end_offset if same_page else None,
    )


class RetrievalService:
    @classmethod
    def retrieve(
        cls,
        question,
        enterprise_id,
        db,
        top_k=None,
        user=None,
        document_id=None,
        context_question=None,
    ):
        document = (
            require_document_read_access(db, document_id, enterprise_id, user)
            if document_id is not None
            else None
        )
        # Scope before either ranker and again before adjacent source expansion.
        conditions = [
            DocumentChunk.enterprise_id == enterprise_id,
            Document.enterprise_id == enterprise_id,
            accessible_documents(user),
        ]
        if document_id is not None:
            conditions.append(Document.id == document_id)
        if settings.RETRIEVAL_STRATEGY == "dense" and document_id is None:
            conditions.extend(
                [
                    DocumentChunk.embedding.is_not(None),
                    DocumentChunk.embedding_model == embedding_identity(),
                ]
            )
        base = (
            select(DocumentChunk, Document.title)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(*conditions)
            .order_by(DocumentChunk.id)
        )
        if db.execute(base.with_only_columns(DocumentChunk.id).limit(1)).first() is None:
            if document is not None:
                if document.index_status in {"queued", "indexing"}:
                    detail = "This document is still being prepared. Wait for the upload to finish and try again."
                elif document.index_status == "failed":
                    detail = "Upload failed for this document. Ask your administrator to try again."
                else:
                    detail = "This document is not ready for questions. Ask your administrator to upload it again."
                raise HTTPException(409, detail)
            return []
        available_bytes = context_budget(
            context_question if context_question is not None else question
        )
        if document_id is not None:
            complete = selected_document_context(db, base, available_bytes)
            if complete is not None:
                return [chunk.context() for chunk in complete]
        strategy = (
            "hybrid"
            if document_id is not None and settings.RETRIEVAL_STRATEGY == "dense"
            else settings.RETRIEVAL_STRATEGY
        )
        try:
            query = None if strategy == "bm25" else EmbeddingService.embed_query(question)
        except ProviderUnavailable:
            if document_id is None:
                raise
            strategy, query = "bm25", None

        def stream():
            result = db.execute(base.execution_options(yield_per=128))
            try:
                for c, title in result:
                    valid_model = c.embedding_model == embedding_identity()
                    yield source_chunk(
                        c,
                        title,
                        include_embedding=valid_model and strategy != "bm25",
                    )
            finally:
                result.close()

        limit = settings.RETRIEVAL_TOP_K if top_k is None else top_k
        candidates = stream_candidates(
            stream,
            question,
            query,
            strategy=strategy,
            candidate_k=max(settings.RETRIEVAL_CANDIDATES, limit),
            min_similarity=settings.RETRIEVAL_MIN_SIMILARITY if document_id is None else 0.0,
        )
        expanded = []
        for anchor in candidates:
            if settings.RETRIEVAL_NEIGHBORS and anchor.section_key:
                radius = settings.RETRIEVAL_NEIGHBORS
                adjacent = db.execute(
                    base.where(
                        DocumentChunk.document_id == anchor.document_id,
                        DocumentChunk.chunk_index.between(
                            anchor.chunk_index - radius, anchor.chunk_index + radius
                        ),
                    )
                ).all()
                anchor = expand_evidence(
                    anchor, [source_chunk(c, title, False) for c, title in adjacent]
                )
            expanded.append(anchor)
        if settings.RERANKER_MODE == "cross_encoder":
            expanded = rerank_chunks(question, expanded, settings.RERANKER_MODEL)
        result = select_context(
            expanded,
            top_k=limit,
            context_characters=settings.RETRIEVAL_CONTEXT_CHARACTERS,
            max_per_document=settings.RETRIEVAL_MAX_DOCUMENT_CHUNKS,
            context_bytes=max(0, available_bytes),
        )
        return [chunk.context() for chunk in result]

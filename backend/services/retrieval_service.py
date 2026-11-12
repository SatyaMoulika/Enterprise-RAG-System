from sqlalchemy import select

from core.config import settings
from core.errors import RetrievalCapacityExceeded
from models.document import Document
from models.document_chunk import DocumentChunk
from services.embedding_service import EmbeddingService
from services.reranking_service import rerank_chunks
from services.search import SearchChunk, rank_candidates, select_context


class RetrievalService:
    @classmethod
    def retrieve(cls, question, enterprise_id, db, top_k=None):
        # Authorization/model filtering precedes BOTH rankers. BM25 statistics are tenant-local.
        rows = db.execute(
            select(DocumentChunk, Document.title)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.enterprise_id == enterprise_id,
                Document.enterprise_id == enterprise_id,
                DocumentChunk.embedding.is_not(None),
                DocumentChunk.embedding_model
                == f"{settings.EMBEDDING_BACKEND}:{settings.EMBEDDING_MODEL}",
            )
            .order_by(DocumentChunk.id)
            .limit(settings.MAX_RETRIEVAL_CHUNKS + 1)
        ).all()
        if len(rows) > settings.MAX_RETRIEVAL_CHUNKS:
            raise RetrievalCapacityExceeded("Workspace exceeds the current retrieval capacity")
        if not rows:
            return []
        query = (
            None
            if settings.RETRIEVAL_STRATEGY == "bm25"
            else EmbeddingService.embed_query(question)
        )
        chunks = [
            SearchChunk(
                id=c.id,
                document_id=c.document_id,
                title=title,
                chunk_index=c.chunk_index,
                chunk_text=c.chunk_text,
                embedding=c.embedding,
            )
            for c, title in rows
        ]
        limit = settings.RETRIEVAL_TOP_K if top_k is None else top_k
        candidates = rank_candidates(
            chunks,
            question,
            query,
            strategy=settings.RETRIEVAL_STRATEGY,
            candidate_k=max(settings.RETRIEVAL_CANDIDATES, limit),
        )
        if settings.RERANKER_MODE == "cross_encoder":
            candidates = rerank_chunks(question, candidates, settings.RERANKER_MODEL)
        result = select_context(
            candidates, top_k=limit, context_characters=settings.RETRIEVAL_CONTEXT_CHARACTERS
        )
        return [chunk.context() for chunk in result]

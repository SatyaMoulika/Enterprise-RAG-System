import heapq
import math

from sqlalchemy import select

from core.config import settings
from core.errors import RetrievalCapacityExceeded
from models.document import Document
from models.document_chunk import DocumentChunk
from services.embedding_service import EmbeddingService


class RetrievalService:
    @classmethod
    def retrieve(cls, question, enterprise_id, db, top_k=5):
        # Scope BEFORE ranking. Other tenants cannot displace this tenant's neighbours.
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
        query = EmbeddingService.embed_query(question)
        query_norm = math.sqrt(sum(x * x for x in query))
        scored = []
        for chunk, title in rows:
            vector = chunk.embedding
            if (
                not isinstance(vector, list)
                or len(vector) != len(query)
                or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector)
            ):
                continue
            norm = math.sqrt(sum(x * x for x in vector))
            if not norm or not query_norm:
                continue
            score = sum(a * b for a, b in zip(query, vector, strict=True)) / (query_norm * norm)
            scored.append(
                (
                    score,
                    chunk.id,
                    {
                        "document_id": chunk.document_id,
                        "title": title,
                        "chunk_index": chunk.chunk_index,
                        "chunk_text": chunk.chunk_text,
                    },
                )
            )
        return [
            item[2] for item in heapq.nlargest(top_k, scored, key=lambda item: (item[0], -item[1]))
        ]

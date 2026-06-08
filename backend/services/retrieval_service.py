from services.embedding_service import EmbeddingService
from services.vector_store_service import VectorStoreService


class RetrievalService:

    @classmethod
    def retrieve(cls, question, enterprise_id, db=None, top_k=5):
        query_embedding = EmbeddingService.embed_query(question)
        results = VectorStoreService.search(query_embedding, top_k)
        filtered_results = [chunk for chunk in results if chunk["enterprise_id"] == enterprise_id]
        return filtered_results
from sentence_transformers import SentenceTransformer

class EmbeddingService:

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    @classmethod
    def embed_texts(cls, texts: list[str]):
        return cls.model.encode(texts, convert_to_numpy=True) 

    @classmethod
    def embed_query(cls, query: str):
        return cls.model.encode([query], convert_to_numpy=True)
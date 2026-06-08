import json
from pathlib import Path

import faiss
import numpy as np

class VectorStoreService:

    INDEX_PATH = "vectorstore/index.faiss"
    META_PATH = "vectorstore/metadata.json"
    DIMENSION = 384

    @classmethod
    def load_index(cls):
        if Path(cls.INDEX_PATH).exists():
            return faiss.read_index(cls.INDEX_PATH)

        return faiss.IndexFlatL2(cls.DIMENSION)

    @classmethod
    def save_index(cls, index):
        faiss.write_index(index,cls.INDEX_PATH)

    @classmethod
    def add_embeddings(cls, embeddings, metadata):
        index = cls.load_index()
        index.add(np.array(embeddings).astype("float32"))
        cls.save_index(index)

        if Path(cls.META_PATH).exists():
            with open(cls.META_PATH, "r") as f:
                existing = json.load(f)
        else:
            existing = []

        existing.extend(metadata)
        with open(cls.META_PATH, "w") as f:
            json.dump(existing, f)

    @classmethod
    def search(cls, query_embedding, k=5):
        index = cls.load_index()
        query_vector = np.array(
            query_embedding,
            dtype=np.float32
        )
        if len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)

        distances, indices = index.search(query_vector, k)
        with open(cls.META_PATH, "r") as f:
            metadata = json.load(f)

        results = []
        for idx in indices[0]:
            if idx == -1:
                continue
            if idx < len(metadata):
                results.append(metadata[idx])

        return results
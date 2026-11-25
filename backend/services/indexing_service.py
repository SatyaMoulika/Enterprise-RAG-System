"""One ingestion implementation for uploads, reindex workers and source evaluations."""

from dataclasses import asdict

from core.config import settings
from services.chunking_service import CHUNKER_VERSION, ChunkingService
from services.embedding_service import EmbeddingService
from services.loader_service import LoaderService


def embedding_identity():
    base = f"{settings.EMBEDDING_BACKEND}:{settings.EMBEDDING_MODEL}"
    return f"{base}@{settings.EMBEDDING_REVISION}" if settings.EMBEDDING_REVISION else base


def prepare_index(path):
    extracted = LoaderService.extract(path)
    chunks = ChunkingService.chunk_document(extracted)
    indexed = []
    for start in range(0, len(chunks), settings.EMBEDDING_BATCH_SIZE):
        batch = chunks[start : start + settings.EMBEDDING_BATCH_SIZE]
        vectors = EmbeddingService.embed_texts([c.chunk_text for c in batch])
        for chunk, vector in zip(batch, vectors, strict=True):
            indexed.append(
                {
                    **asdict(chunk),
                    "embedding": vector,
                    "embedding_model": embedding_identity(),
                    "chunk_index": len(indexed),
                }
            )
    metadata = {
        "chunker": CHUNKER_VERSION,
        "extractor": "pdf-prose-v2",
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_max_characters": settings.CHUNK_MAX_CHARACTERS,
        "overlap": settings.CHUNK_OVERLAP,
        "embedding_model": embedding_identity(),
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
        "embedding_revision_pinned": bool(settings.EMBEDDING_REVISION),
        "page_count": len(extracted.pages),
        "chunk_count": len(indexed),
    }
    return indexed, extracted.warnings, metadata

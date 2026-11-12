from core.config import settings
from core.errors import UploadTooLarge


class ChunkingService:
    @staticmethod
    def chunk_text(text: str) -> list[str]:
        step = settings.CHUNK_SIZE - settings.CHUNK_OVERLAP
        chunks = [
            text[start : start + settings.CHUNK_SIZE]
            for start in range(0, len(text), step)
            if text[start : start + settings.CHUNK_SIZE].strip()
        ]
        if len(chunks) > settings.MAX_DOCUMENT_CHUNKS:
            raise UploadTooLarge("Document has too many chunks")
        return chunks

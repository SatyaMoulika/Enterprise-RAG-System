from pathlib import Path
import shutil

from models.document import Document
from models.document_chunk import DocumentChunk

from repositories.document_repository import (
    DocumentRepository,
)

from services.loader_service import (
    LoaderService,
)

from services.chunking_service import (
    ChunkingService,
)

from services.embedding_service import (
    EmbeddingService,
)

from services.vector_store_service import (
    VectorStoreService,
)


class DocumentService:

    @staticmethod
    def upload_document(db, enterprise_id: int, file,):
        try:
            # Create enterprise upload folder
            enterprise_folder = Path(f"uploads/enterprise_{enterprise_id}")
            enterprise_folder.mkdir(parents=True, exist_ok=True)
            file_path = (enterprise_folder / file.filename)

            # Save uploaded file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Create document record
            document = Document(
                enterprise_id=enterprise_id,
                title=file.filename,
                file_path=str(file_path),
            )
            document = (DocumentRepository.create(db=db, document=document))

            # Extract text
            text = LoaderService.extract_text(file_path)
            if not text.strip():
                raise ValueError("Document contains no extractable text")

            # Chunk text
            chunks = (ChunkingService.chunk_text(text))
            if not chunks:
                raise ValueError("No chunks generated")

            # Generate embeddings
            embeddings = (EmbeddingService.embed_texts(chunks))
            if len(embeddings) != len(chunks):
                raise ValueError("Embedding generation failed")

            # Save chunks in PostgreSQL
            metadata = []
            for index, chunk in enumerate(chunks):
                chunk_obj = DocumentChunk(
                    document_id=document.id,
                    enterprise_id=enterprise_id,
                    chunk_text=chunk,
                    chunk_index=index,
                )
                db.add(chunk_obj)
                metadata.append(
                    {
                        "document_id": document.id,
                        "enterprise_id": enterprise_id,
                        "chunk_index": index,
                        "chunk_text": chunk,
                    }
                )
            db.commit()

            # Save embeddings in FAISS
            VectorStoreService.add_embeddings(
                embeddings=embeddings,
                metadata=metadata,
            )
            
            return document

        except Exception:
                db.rollback()
                raise
        
    @classmethod
    def get_documents(cls, db, enterprise_id: int):
        return DocumentRepository.get_by_enterprise(db=db, enterprise_id=enterprise_id)  
    

    @classmethod
    def delete_document(cls, db, document_id, enterprise_id):
        return DocumentRepository.delete(
            db=db,
            document_id=document_id,
            enterprise_id=enterprise_id
        )
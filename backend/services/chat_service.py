from core.config import settings
from services.generation_protocol import NO_CONTEXT_ANSWER
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.retrieval_service import RetrievalService
from services.salary_calculator import salary_answer


class ChatService:
    @classmethod
    def ask(cls, question, enterprise_id, db, user=None, document_id=None):
        chunks = RetrievalService.retrieve(
            question=question,
            enterprise_id=enterprise_id,
            db=db,
            user=user,
            document_id=document_id,
        )
        if not chunks:
            return {
                "answer": NO_CONTEXT_ANSWER,
                "sources": [],
                "citations": [],
            }
        calculation = (
            salary_answer(question, chunks, getattr(user, "name", None))
            if settings.FINANCIAL_CALCULATIONS_ENABLED
            else None
        )
        answer = (
            calculation["answer"]
            if calculation is not None
            else LLMService.generate(question=question, context=PromptService.build_context(chunks))
        )
        return {
            "answer": answer,
            "sources": list(dict.fromkeys(c["document_id"] for c in chunks)),
            "citations": [
                {
                    "document_id": c["document_id"],
                    "title": c["title"],
                    "chunk_index": c["chunk_index"],
                    "excerpt": c["chunk_text"],
                }
                for c in chunks
            ],
        }

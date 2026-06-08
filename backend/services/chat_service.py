from services.retrieval_service import RetrievalService
from services.prompt_service import PromptService
from services.llm_service import LLMService


class ChatService:

    @classmethod
    def ask(cls, question, enterprise_id, db):

        chunks = RetrievalService.retrieve(
            question=question,
            enterprise_id=enterprise_id,
            db=db
        )

        if not chunks:
            return {
                "answer": "No relevant documents found.",
                "sources": []
            }

        context = PromptService.build_context(chunks)

        answer = LLMService.generate(
            question=question,
            context=context
        )

        return {
            "answer": answer,
            "sources": list(set(chunk["document_id"] for chunk in chunks))
        }
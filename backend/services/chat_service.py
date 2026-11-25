from core.config import settings
from core.errors import ProviderUnavailable
from services.answer_validation import UNVERIFIED_ANSWER, citation_check
from services.document_access import require_document_read_access
from services.generation_protocol import NO_CONTEXT_ANSWER
from services.llm_service import LLMService
from services.personal_document_service import (
    account_question,
    identity_answer,
    resolve_personal_document,
)
from services.prompt_service import PromptService
from services.retrieval_service import RetrievalService
from services.salary_calculator import salary_answer


class ChatService:
    @classmethod
    def ask(cls, question, enterprise_id, db, user=None, document_id=None, review_trace=None):
        if document_id is not None:
            # Reject stale or forbidden selections before identity/personal routing.
            require_document_read_access(db, document_id, enterprise_id, user)
        account_response = identity_answer(question, user)
        if account_response is not None:
            return {
                "answer": account_response,
                "sources": [],
                "citations": [],
                "answer_origin": "account_context",
                "citation_status": "not_applicable",
            }
        personal = resolve_personal_document(question, enterprise_id, db, user, document_id)
        if personal is not None:
            if personal.message:
                return {
                    "answer": personal.message,
                    "sources": [],
                    "citations": [],
                    "answer_origin": "account_context",
                    "citation_status": "not_applicable",
                }
            document_id = personal.document_id
        generation_question = (
            account_question(question, user, document_id) if personal is not None else question
        )
        chunks = RetrievalService.retrieve(
            question=question,
            enterprise_id=enterprise_id,
            db=db,
            user=user,
            document_id=document_id,
            context_question=generation_question,
        )
        if not chunks:
            return {
                "answer": NO_CONTEXT_ANSWER,
                "sources": [],
                "citations": [],
            }
        calculation = (
            salary_answer(
                question,
                chunks,
                personal.subject_name
                if personal is not None and personal.subject_name
                else getattr(user, "name", None),
            )
            if settings.FINANCIAL_CALCULATIONS_ENABLED
            else None
        )
        answer = (
            calculation["answer"]
            if calculation is not None
            else LLMService.generate(
                question=generation_question, context=PromptService.build_context(chunks)
            )
        )
        validation = citation_check(answer, len(chunks))
        original_answer = answer
        repaired = False
        revision_attempted = calculation is None and not validation["valid"]
        if calculation is None and not validation["valid"]:
            try:
                revised = LLMService.repair_citations(
                    generation_question, PromptService.build_context(chunks), answer
                )
                if isinstance(revised, str) and revised.strip():
                    answer = revised
                    validation = citation_check(answer, len(chunks))
                    repaired = True
            except (ProviderUnavailable, ValueError):
                pass
        if review_trace is not None:
            review_trace.update(
                initial_generated_answer=original_answer,
                generated_answer=answer,
                citation_revision_attempted=revision_attempted,
                citation_revised=repaired,
                citation_validation=validation,
            )
        if calculation is None and not validation["valid"]:
            answer = UNVERIFIED_ANSWER
        return {
            "answer": answer,
            "sources": list(dict.fromkeys(c["document_id"] for c in chunks)),
            "citations": [
                {
                    "document_id": c["document_id"],
                    "title": c["title"],
                    "chunk_index": c["chunk_index"],
                    "excerpt": c["chunk_text"],
                    "marker": marker,
                    **{
                        key: c[key]
                        for key in (
                            "page_start",
                            "page_end",
                            "section",
                            "chunk_end_index",
                            "dense_score",
                            "lexical_score",
                        )
                        if key in c
                    },
                }
                for marker, c in enumerate(chunks, 1)
            ],
            "citation_status": "not_applicable"
            if calculation is not None and not validation["markers"]
            else "valid"
            if validation["valid"]
            else "invalid",
            "answer_origin": "deterministic_salary" if calculation is not None else "model",
        }

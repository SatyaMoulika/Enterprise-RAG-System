from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    document_id: int | None = Field(default=None, gt=0)
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be blank")
        return value


class SourceCitation(BaseModel):
    marker: int | None = None
    document_id: int
    title: str
    chunk_index: int
    excerpt: str
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None
    chunk_end_index: int | None = None
    dense_score: float | None = None
    lexical_score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[int]
    citations: list[SourceCitation] = Field(default_factory=list)
    citation_status: str = "no_context"
    answer_origin: str = "no_context"

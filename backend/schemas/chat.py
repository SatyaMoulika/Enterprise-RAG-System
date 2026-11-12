from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be blank")
        return value


class SourceCitation(BaseModel):
    document_id: int
    title: str
    chunk_index: int
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[int]
    citations: list[SourceCitation] = Field(default_factory=list)

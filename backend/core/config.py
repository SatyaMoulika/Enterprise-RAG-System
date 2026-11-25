from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Enterprise RAG Assistant"
    PUBLIC_REGISTRATION_ENABLED: bool = True
    PUBLIC_APP_URL: str = "http://localhost:8080"
    PASSWORD_RESET_MINUTES: int = Field(default=15, ge=5, le=60)
    LOCAL_DIRECT_PASSWORD_RESET: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_FROM: str = ""
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_SECURITY: Literal["starttls", "ssl", "plain"] = "starttls"
    DATABASE_URL: str
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, ge=1)
    MAX_TEXT_CHARACTERS: int = Field(default=500_000, ge=1)
    MAX_DOCUMENT_CHUNKS: int = Field(default=2000, ge=1)
    MAX_RETRIEVAL_CHUNKS: int = Field(default=10_000, ge=1)
    EMBEDDING_BATCH_SIZE: int = Field(default=32, ge=1, le=256)
    EMBEDDING_REVISION: str = ""
    RETRIEVAL_MIN_SIMILARITY: float = Field(default=0.3, ge=-1, le=1)
    RETRIEVAL_NEIGHBORS: int = Field(default=1, ge=0, le=2)
    RETRIEVAL_MAX_DOCUMENT_CHUNKS: int = Field(default=3, ge=1, le=20)
    GENERATION_CONTEXT_TOKENS: int = Field(default=16384, ge=2048)
    GENERATION_MAX_TOKENS: int = Field(default=1024, ge=64)
    GENERATION_TEMPERATURE: float = Field(default=0.0, ge=0, le=2)
    FINANCIAL_CALCULATIONS_ENABLED: bool = False
    RERANKER_MODE: Literal["none", "cross_encoder"] = "none"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RETRIEVAL_STRATEGY: Literal["dense", "bm25", "hybrid"] = "dense"
    RETRIEVAL_TOP_K: int = Field(default=5, ge=1, le=20)
    RETRIEVAL_CANDIDATES: int = Field(default=20, ge=1, le=100)
    RETRIEVAL_CONTEXT_CHARACTERS: int = Field(default=24000, ge=100, le=100000)
    CHUNK_SIZE: int = Field(default=500, ge=100, le=4000)
    CHUNK_MAX_CHARACTERS: int = Field(default=4000, ge=100, le=16000)
    CHUNK_OVERLAP: int = Field(default=50, ge=0, lt=100)
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:3b"
    EMBEDDING_BACKEND: Literal["ollama", "sentence_transformers"] = "ollama"
    EMBEDDING_MODEL: str = "all-minilm"
    EMBEDDING_DIMENSION: int = Field(default=384, ge=1)
    PROVIDER_TIMEOUT_SECONDS: float = Field(default=90, gt=0, le=300)
    CORS_ORIGINS: list[str] = []

    @model_validator(mode="after")
    def validate_chunk_limits(self):
        if self.CHUNK_MAX_CHARACTERS < self.CHUNK_SIZE:
            raise ValueError("CHUNK_MAX_CHARACTERS must be at least CHUNK_SIZE")
        if self.RETRIEVAL_CANDIDATES < self.RETRIEVAL_TOP_K:
            raise ValueError("RETRIEVAL_CANDIDATES must be at least RETRIEVAL_TOP_K")
        return self


settings = Settings()

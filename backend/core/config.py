from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Enterprise RAG Assistant"
    DATABASE_URL: str
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=1440)
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, ge=1)
    MAX_TEXT_CHARACTERS: int = Field(default=500_000, ge=1)
    MAX_DOCUMENT_CHUNKS: int = Field(default=2000, ge=1)
    MAX_RETRIEVAL_CHUNKS: int = Field(default=10_000, ge=1)
    CHUNK_SIZE: int = Field(default=500, ge=100, le=4000)
    CHUNK_OVERLAP: int = Field(default=50, ge=0, lt=100)
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_CHAT_MODEL: str = "qwen2.5:3b"
    EMBEDDING_BACKEND: Literal["ollama", "sentence_transformers"] = "ollama"
    EMBEDDING_MODEL: str = "all-minilm"
    EMBEDDING_DIMENSION: int = Field(default=384, ge=1)
    PROVIDER_TIMEOUT_SECONDS: float = Field(default=90, gt=0, le=300)
    CORS_ORIGINS: list[str] = []


settings = Settings()

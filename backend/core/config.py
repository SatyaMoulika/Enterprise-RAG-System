from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    APP_NAME: str = "Enterprise RAG Assistant"

    DATABASE_URL: str

    JWT_SECRET_KEY: str

    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    HF_TOKEN: str

    class Config:
        env_file = ".env"


settings = Settings()
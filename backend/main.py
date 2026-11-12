from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.auth_router import auth_router
from api.chat_router import chat_router
from api.document_router import document_router
from api.users_router import users_router
from core.config import settings
from core.errors import (
    InvalidDocument,
    ProviderUnavailable,
    RetrievalCapacityExceeded,
    UploadTooLarge,
)
from database.session import engine

app = FastAPI(title=settings.APP_NAME, version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
for router in (auth_router, users_router, document_router, chat_router):
    app.include_router(router)


@app.exception_handler(InvalidDocument)
async def invalid_document_handler(request: Request, exc: InvalidDocument):
    return JSONResponse(
        status_code=413 if isinstance(exc, UploadTooLarge) else 422, content={"detail": str(exc)}
    )


@app.exception_handler(ProviderUnavailable)
async def provider_error_handler(request: Request, exc: ProviderUnavailable):
    return JSONResponse(
        status_code=503, content={"detail": str(exc)}, headers={"Retry-After": "10"}
    )


@app.exception_handler(RetrievalCapacityExceeded)
async def capacity_error_handler(request: Request, exc: RetrievalCapacityExceeded):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/ready")
def readiness_check():
    try:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT embedding, embedding_model FROM document_chunks LIMIT 0")
            )
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready", "inference": "checked on use"}

import logging
from time import perf_counter
from uuid import uuid4

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
logger = logging.getLogger("uvicorn.error")


@app.middleware("http")
async def request_metrics(request: Request, call_next):
    request_id = uuid4().hex
    start = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        # Never log bodies, questions, file names, credentials or query strings.
        logger.info(
            "request id=%s method=%s route=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            route,
            status,
            (perf_counter() - start) * 1000,
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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
                text("SELECT embedding, embedding_model, page_start FROM document_chunks LIMIT 0")
            )
            connection.execute(text("SELECT index_status FROM documents LIMIT 0"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready", "inference": "checked on use"}

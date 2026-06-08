from fastapi import FastAPI

from api.chat_router import chat_router
from api.document_router import document_router
from api.auth_router import auth_router
from api.users_router import users_router

app = FastAPI(
    title="Enterprise Multi-Agent RAG Assistant"
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(document_router)
app.include_router(chat_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}



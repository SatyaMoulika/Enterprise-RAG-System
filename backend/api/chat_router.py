from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from database.session import get_db

from dependencies.auth import get_current_user
from schemas.chat import ChatRequest, ChatResponse

from services.chat_service import ChatService

chat_router = APIRouter(prefix="/chat", tags=["Chat"])

@chat_router.post("/generate", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    enterprise_id = current_user.enterprise_id
    result = ChatService.ask(
        payload.question,
        enterprise_id,
        db
    )
    return result
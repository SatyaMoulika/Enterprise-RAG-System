from datetime import datetime
from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str
    role: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    enterprise_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CurrentUserResponse(BaseModel):
    id: int
    email: str
    role: str
    enterprise_id: int
    is_active: bool

    class Config:
        from_attributes = True
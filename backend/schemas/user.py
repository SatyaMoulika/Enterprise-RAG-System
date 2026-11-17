from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    name: str = Field(default="", max_length=120)

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "employee"] = "employee"


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str = ""
    id: int
    email: str
    role: str
    enterprise_id: int
    is_active: bool


class UserResponse(CurrentUserResponse):
    created_at: datetime

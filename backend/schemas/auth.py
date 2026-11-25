from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    enterprise_name: str = Field(min_length=1, max_length=255)
    # Older API clients may omit the name; the current signup form requires it.
    name: str = Field(default="", max_length=120)
    is_admin: Literal[True] = True
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("enterprise_name")
    @classmethod
    def nonempty_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Workspace name must not be blank")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def administrator_name(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("Administrator name must not be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=4096)
    password: str = Field(min_length=8, max_length=128)


class DirectResetPasswordRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

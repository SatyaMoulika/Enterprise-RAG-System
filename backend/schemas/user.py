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
    profile_photo: str | None = None
    name: str = ""
    id: int
    email: str
    role: str
    enterprise_id: int
    enterprise_name: str = ""
    is_active: bool


class UserResponse(CurrentUserResponse):
    created_at: datetime


class MemberUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a name")
        return value


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    profile_photo: str | None = Field(default=None, max_length=400000)

    @field_validator("name")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a name")
        return value

    @field_validator("profile_photo")
    @classmethod
    def image_only(cls, value):
        import base64

        if value is None:
            return value
        prefix, _, encoded = value.partition(",")
        if prefix not in {"data:image/png;base64", "data:image/jpeg;base64"}:
            raise ValueError("Use a PNG or JPEG photo")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise ValueError("Invalid photo") from None
        if not (
            (
                prefix == "data:image/png;base64"
                and raw.startswith(bytes.fromhex("89504e470d0a1a0a"))
            )
            or (prefix == "data:image/jpeg;base64" and raw.startswith(bytes.fromhex("ffd8ff")))
        ):
            raise ValueError("Invalid photo")
        return value


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)

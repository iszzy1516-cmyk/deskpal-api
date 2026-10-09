"""Pydantic request/response schemas — the input-validation layer.

Every request body passes through one of these before it touches the database.
Password rule (enforced here AND re-checked in the router): min 8 chars with at
least one letter and one number.
"""
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


class PasswordMixin(BaseModel):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError("Password must be at least 8 characters with a letter and a number")
        return v


class SignupRequest(PasswordMixin):
    org_name: str = Field(min_length=2, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: Literal["owner", "admin", "editor"]
    org_id: int
    org_name: str
    org_plan: str

    model_config = {"from_attributes": True}


class BotCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    widget_settings: dict = Field(default_factory=dict)


class BotOut(BaseModel):
    id: int
    name: str
    widget_settings: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    bot_id: int
    filename: str
    status: str
    quarantined_chunks: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class SourceCitation(BaseModel):
    document_name: str
    chunk_index: int
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    used_documents: bool


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detail: str

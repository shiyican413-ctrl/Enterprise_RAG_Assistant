from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, examples=["公司报销流程是什么？"])
    conversation_id: str | None = None
    top_k: int = Field(default=4, ge=1, le=10)
    answer_mode: Literal["fast", "thinking"] = "fast"


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=256)


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")


class CreateUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=256)
    role: Literal["viewer", "maintainer", "admin"] = "viewer"
    tenant_id: str | None = None


class AskResponse(BaseModel):
    conversation_id: str
    trace_id: str | None = None
    answer: str
    sources: list[dict]
    answer_mode: Literal["fast", "thinking"] = "fast"
    model: str | None = None
    agent_steps: list[dict] = Field(default_factory=list)
    route: list[dict] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str

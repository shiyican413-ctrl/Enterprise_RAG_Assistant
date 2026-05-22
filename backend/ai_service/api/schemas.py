from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, examples=["公司报销流程是什么？"])
    conversation_id: str | None = None
    top_k: int = Field(default=4, ge=1, le=10)


class AskResponse(BaseModel):
    conversation_id: str
    answer: str
    sources: list[dict]


class ErrorResponse(BaseModel):
    detail: str

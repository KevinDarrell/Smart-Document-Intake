from pydantic import BaseModel, Field

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class IngestReq(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=50_000)


class AskReq(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str = Field(min_length=8, max_length=200)

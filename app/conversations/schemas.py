import uuid
from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.config import settings
from app.retrieval.schemas import ChunkResult


class ConversationCreate(BaseModel):
    pass  # user_id is injected from JWT, not accepted from client


class ConversationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    status: str
    total_token_count: int
    compacted_history: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def context_limit_tokens(self) -> int:
        return settings.CONTEXT_LIMIT_TOKENS

    @computed_field
    @property
    def usage_pct(self) -> float:
        return round(self.total_token_count / settings.CONTEXT_LIMIT_TOKENS * 100, 1)


class MessageRead(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    token_count: int
    is_compacted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    document_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Filter retrieval to specific documents. None = search all.",
    )
    top_n: int = Field(default=5, ge=1, le=20)
    retrieve_n: int = Field(default=10, ge=1, le=100)
    rerank: bool = Field(default=False)


class CompactResponse(BaseModel):
    conversation_id: uuid.UUID
    compacted: bool
    total_token_count: int
    context_limit_tokens: int
    usage_pct: float


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    query: str
    answer: str
    sources: list[ChunkResult]
    token_count_this_turn: int
    total_token_count: int
    context_limit_tokens: int
    usage_pct: float
    compacting_triggered: bool
    model: str

import uuid

from pydantic import BaseModel, Field

from app.retrieval.schemas import ChunkResult


class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    document_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Filter to specific documents. None = search all.",
    )
    top_n: int = Field(default=5, ge=1, le=20)
    retrieve_n: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Candidates before reranking. Defaults to top_n * 3 (min 10).",
    )


class GenerateResponse(BaseModel):
    query: str
    answer: str
    sources: list[ChunkResult]
    model: str

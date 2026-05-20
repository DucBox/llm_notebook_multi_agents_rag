from pydantic import BaseModel, Field

from app.retrieval.schemas import ChunkResult


class GenerateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    chunks: list[ChunkResult] = Field(..., description="Reranked chunks from POST /api/v1/query")
    # [History Chat] will go here in a future phase


class GenerateResponse(BaseModel):
    query: str
    answer: str
    sources: list[ChunkResult]
    model: str

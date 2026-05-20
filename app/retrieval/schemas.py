import uuid

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_n: int = Field(default=5, ge=1, le=50)
    document_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Filter search to specific documents. None = search all.",
    )


class ChunkResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str
    chunk_index: int
    page_number: int | None
    page_number_end: int | None
    text_content: str
    char_offset_start: int
    char_offset_end: int
    score: float = Field(description="Cosine similarity [0, 1]. Higher = more relevant.")

    model_config = {"from_attributes": True}


class QueryResponse(BaseModel):
    query: str
    top_n: int
    total_results: int
    results: list[ChunkResult]

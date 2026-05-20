import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.documents.models import DocumentStatus


# ── Document ──────────────────────────────────

class DocumentRead(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    content_sha256: str
    author: str | None
    user_id: uuid.UUID | None
    status: DocumentStatus
    error_message: str | None
    processing_started_at: datetime | None
    processing_finished_at: datetime | None
    page_count: int | None
    chunk_count: int | None
    metadata: dict = Field(alias="metadata_", default_factory=dict)
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentStatusUpdate(BaseModel):
    status: DocumentStatus
    error_message: str | None = None
    chunk_count: int | None = None
    page_count: int | None = None


class DocumentMetadataUpdate(BaseModel):
    author: str | None = None
    metadata: dict | None = None


class DuplicateCheckRequest(BaseModel):
    content_sha256: str


class DuplicateCheckResponse(BaseModel):
    exists: bool
    document_id: uuid.UUID | None = None
    status: DocumentStatus | None = None


class UploadResult(BaseModel):
    filename: str
    success: bool
    document: DocumentRead | None = None
    embedded_chunks: int | None = None
    error: str | None = None


# ── Chunk ─────────────────────────────────────

class ChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    page_number: int | None
    page_number_end: int | None
    text_content: str
    token_count: int | None
    char_offset_start: int
    char_offset_end: int
    content_sha256: str
    metadata: dict = Field(alias="metadata_", default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Ingestion Job ──────────────────────────────

class JobRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    task_id: str | None
    attempt_number: int
    started_at: datetime | None
    finished_at: datetime | None
    error_detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

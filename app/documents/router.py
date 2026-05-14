import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import PaginatedResponse
from app.core.database import get_db
from app.core.exceptions import (
    DocumentDeletionError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    FileTooLargeError,
    InvalidStatusTransitionError,
    UnsupportedFileTypeError,
)
from app.documents import service
from app.documents.models import DocumentStatus
from app.documents.repository import ChunkRepository, JobRepository
from app.documents.schemas import (
    ChunkRead,
    DocumentMetadataUpdate,
    DocumentRead,
    DocumentStatusUpdate,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    JobRead,
)

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Duplicate check ────────────────────────────────────────────────────────────

@router.post("/check-duplicate", response_model=DuplicateCheckResponse)
async def check_duplicate(
    payload: DuplicateCheckRequest,
    session: AsyncSession = Depends(get_db),
):
    existing = await service.check_duplicate(payload.content_sha256, session)
    if existing:
        return DuplicateCheckResponse(exists=True, document_id=existing.id, status=existing.status)
    return DuplicateCheckResponse(exists=False)


# ── Documents CRUD ─────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentRead)
async def upload_document(
    file: UploadFile = File(...),
    author: str | None = Form(None),
    metadata: str | None = Form(None, description="JSON string"),
    session: AsyncSession = Depends(get_db),
):
    file_data = await file.read()
    parsed_metadata: dict = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="metadata must be valid JSON")

    try:
        doc = await service.upload_document(
            file_data=file_data,
            filename=file.filename or "upload",
            author=author,
            metadata=parsed_metadata,
            session=session,
        )
    except DuplicateDocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Document already exists", "existing_document_id": e.existing_document_id},
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))

    return DocumentRead.model_validate(doc)


@router.get("", response_model=PaginatedResponse[DocumentRead])
async def list_documents(
    status: DocumentStatus | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    docs, total = await service.list_documents(session, status=status, q=q, page=page, page_size=page_size)
    return PaginatedResponse(
        items=[DocumentRead.model_validate(d) for d in docs],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    try:
        doc = await service.get_document(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(doc)


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document_metadata(
    document_id: uuid.UUID,
    payload: DocumentMetadataUpdate,
    session: AsyncSession = Depends(get_db),
):
    try:
        doc = await service.update_metadata(document_id, payload, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(doc)


@router.patch("/{document_id}/status", response_model=DocumentRead)
async def update_document_status(
    document_id: uuid.UUID,
    payload: DocumentStatusUpdate,
    session: AsyncSession = Depends(get_db),
):
    try:
        doc = await service.update_status(document_id, payload, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return DocumentRead.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    try:
        await service.delete_document(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except DocumentDeletionError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Chunks ─────────────────────────────────────────────────────────────────────

@router.get("/{document_id}/chunks", response_model=PaginatedResponse[ChunkRead])
async def list_chunks(
    document_id: uuid.UUID,
    page_number: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    try:
        await service.get_document(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks, total = await ChunkRepository(session).list_by_document(
        document_id, page_number=page_number, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[ChunkRead.model_validate(c) for c in chunks],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{document_id}/chunks/{chunk_id}", response_model=ChunkRead)
async def get_chunk(
    document_id: uuid.UUID,
    chunk_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    try:
        await service.get_document(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk = await ChunkRepository(session).get_by_id(chunk_id, document_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return ChunkRead.model_validate(chunk)


# ── Ingestion Jobs ─────────────────────────────────────────────────────────────

@router.get("/{document_id}/jobs", response_model=PaginatedResponse[JobRead])
async def list_jobs(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    try:
        await service.get_document(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    jobs = await JobRepository(session).list_by_document(document_id)
    return PaginatedResponse(
        items=[JobRead.model_validate(j) for j in jobs],
        total=len(jobs), page=1, page_size=max(len(jobs), 1),
    )

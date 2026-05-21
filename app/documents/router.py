import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
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
    UploadResult,
)
from app.embeddings import service as embedding_service

router = APIRouter(prefix="/documents", tags=["documents"])


# ── Duplicate check ────────────────────────────────────────────────────────────

@router.post("/check-duplicate", response_model=DuplicateCheckResponse)
async def check_duplicate(
    payload: DuplicateCheckRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await service.check_duplicate(payload.content_sha256, current_user.id, session)
    if existing:
        return DuplicateCheckResponse(exists=True, document_id=existing.id, status=existing.status)
    return DuplicateCheckResponse(exists=False)


# ── Documents CRUD ─────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=list[UploadResult])
async def upload_documents(
    files: Annotated[list[UploadFile], File(description="PDF, TXT, or Markdown files")],
    author: str | None = Form(None),
    metadata: str | None = Form(None, description="JSON string"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parsed_metadata: dict = {}
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="metadata must be valid JSON")

    results: list[UploadResult] = []

    for file in files:
        filename = file.filename or "upload"
        try:
            file_data = await file.read()
            doc = await service.upload_document(
                file_data=file_data,
                filename=filename,
                author=author,
                metadata=parsed_metadata,
                user_id=current_user.id,
                session=session,
            )
            embed_result = await embedding_service.embed_document(doc.id, session)
            results.append(UploadResult(
                filename=filename,
                success=True,
                document=DocumentRead.model_validate(doc),
                embedded_chunks=embed_result["embedded"],
            ))
        except DuplicateDocumentError as e:
            results.append(UploadResult(
                filename=filename,
                success=False,
                error=f"Duplicate document (existing id: {e.existing_document_id})",
            ))
        except (UnsupportedFileTypeError, FileTooLargeError) as e:
            results.append(UploadResult(filename=filename, success=False, error=str(e)))
        except Exception as e:
            results.append(UploadResult(filename=filename, success=False, error=str(e)))

    return results


@router.get("", response_model=PaginatedResponse[DocumentRead])
async def list_documents(
    status: DocumentStatus | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs, total = await service.list_documents(
        session, user_id=current_user.id, status=status, q=q, page=page, page_size=page_size
    )
    return PaginatedResponse(
        items=[DocumentRead.model_validate(d) for d in docs],
        total=total, page=page, page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc = await service.get_document(document_id, current_user.id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(doc)


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document_metadata(
    document_id: uuid.UUID,
    payload: DocumentMetadataUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc = await service.update_metadata(document_id, payload, current_user.id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentRead.model_validate(doc)


@router.patch("/{document_id}/status", response_model=DocumentRead)
async def update_document_status(
    document_id: uuid.UUID,
    payload: DocumentStatusUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc = await service.update_status(document_id, payload, current_user.id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return DocumentRead.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await service.delete_document(document_id, current_user.id, session)
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
    current_user: User = Depends(get_current_user),
):
    try:
        await service.get_document(document_id, current_user.id, session)
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
    current_user: User = Depends(get_current_user),
):
    try:
        await service.get_document(document_id, current_user.id, session)
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
    current_user: User = Depends(get_current_user),
):
    try:
        await service.get_document(document_id, current_user.id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

    jobs = await JobRepository(session).list_by_document(document_id)
    return PaginatedResponse(
        items=[JobRead.model_validate(j) for j in jobs],
        total=len(jobs), page=1, page_size=max(len(jobs), 1),
    )

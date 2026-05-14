import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentDeletionError,
    DocumentNotFoundError,
    DuplicateDocumentError,
)
from app.documents import ingestion, storage
from app.documents.models import Document, DocumentStatus, IngestionJob
from app.documents.repository import ChunkRepository, DocumentRepository, JobRepository
from app.documents.schemas import DocumentMetadataUpdate, DocumentStatusUpdate


async def check_duplicate(sha256: str, session: AsyncSession) -> Document | None:
    return await DocumentRepository(session).get_by_sha256(sha256)


async def upload_document(
    file_data: bytes,
    filename: str,
    author: str | None,
    metadata: dict,
    session: AsyncSession,
) -> Document:
    mime_type = storage.validate_upload(filename, len(file_data))

    doc_id = uuid.uuid4()
    file_path, sha256 = await storage.save_file(file_data, filename, doc_id)

    existing = await DocumentRepository(session).get_by_sha256(sha256)
    if existing and existing.status != DocumentStatus.FAILED:
        await storage.delete_file(str(file_path))
        raise DuplicateDocumentError(str(existing.id))

    doc_repo = DocumentRepository(session)
    document = await doc_repo.create(Document(
        id=doc_id,
        filename=file_path.name,
        original_filename=filename,
        file_path=str(file_path),
        file_size=len(file_data),
        mime_type=mime_type,
        content_sha256=sha256,
        author=author,
        metadata_=metadata,
        status=DocumentStatus.PENDING,
    ))

    job_repo = JobRepository(session)
    job = await job_repo.create(IngestionJob(document_id=document.id))

    try:
        await job_repo.mark_started(job)
        await doc_repo.update_status(document, DocumentStatus.PROCESSING)

        chunk_data_list, page_count = ingestion.parse_and_chunk(Path(document.file_path), mime_type)
        chunk_models = ingestion.build_chunk_models(chunk_data_list, document.id)
        await ChunkRepository(session).bulk_insert(chunk_models)

        await doc_repo.update_status(
            document, DocumentStatus.PROCESSED,
            chunk_count=len(chunk_models), page_count=page_count,
        )
        await job_repo.mark_finished(job)

    except Exception as exc:
        await doc_repo.update_status(document, DocumentStatus.FAILED, error_message=str(exc))
        await job_repo.mark_finished(job, error_detail=str(exc))

    await session.commit()
    await session.refresh(document)
    return document


async def get_document(document_id: uuid.UUID, session: AsyncSession) -> Document:
    doc = await DocumentRepository(session).get_by_id(document_id)
    if not doc:
        raise DocumentNotFoundError(str(document_id))
    return doc


async def list_documents(
    session: AsyncSession,
    *,
    status: DocumentStatus | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Document], int]:
    return await DocumentRepository(session).list(status=status, q=q, page=page, page_size=page_size)


async def update_status(
    document_id: uuid.UUID, payload: DocumentStatusUpdate, session: AsyncSession
) -> Document:
    doc = await get_document(document_id, session)
    ingestion.validate_status_transition(doc.status, payload.status)
    await DocumentRepository(session).update_status(
        doc, payload.status,
        error_message=payload.error_message,
        chunk_count=payload.chunk_count,
        page_count=payload.page_count,
    )
    await session.commit()
    await session.refresh(doc)
    return doc


async def update_metadata(
    document_id: uuid.UUID, payload: DocumentMetadataUpdate, session: AsyncSession
) -> Document:
    doc = await get_document(document_id, session)
    await DocumentRepository(session).update_metadata(doc, author=payload.author, metadata=payload.metadata)
    await session.commit()
    await session.refresh(doc)
    return doc


async def delete_document(document_id: uuid.UUID, session: AsyncSession) -> None:
    doc = await get_document(document_id, session)
    if doc.status == DocumentStatus.PROCESSING:
        raise DocumentDeletionError("Cannot delete a document that is currently being processed.")
    await DocumentRepository(session).soft_delete(doc)
    await session.commit()

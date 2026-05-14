import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.models import Document, DocumentChunk, DocumentStatus, IngestionJob


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        result = await self._session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sha256(self, sha256: str) -> Document | None:
        result = await self._session.execute(
            select(Document).where(Document.content_sha256 == sha256)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        status: DocumentStatus | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int]:
        base = select(Document).where(Document.deleted_at.is_(None))
        if status:
            base = base.where(Document.status == status)
        if q:
            base = base.where(Document.filename.ilike(f"%{q}%"))

        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()

        result = await self._session.execute(
            base.order_by(Document.created_at.desc())
               .offset((page - 1) * page_size)
               .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        await self._session.refresh(document)
        return document

    async def update_status(
        self,
        document: Document,
        status: DocumentStatus,
        *,
        error_message: str | None = None,
        chunk_count: int | None = None,
        page_count: int | None = None,
    ) -> Document:
        document.status = status
        document.updated_at = datetime.now(timezone.utc)
        if status == DocumentStatus.PROCESSING:
            document.processing_started_at = datetime.now(timezone.utc)
        elif status in (DocumentStatus.PROCESSED, DocumentStatus.FAILED):
            document.processing_finished_at = datetime.now(timezone.utc)
        if error_message is not None:
            document.error_message = error_message
        if chunk_count is not None:
            document.chunk_count = chunk_count
        if page_count is not None:
            document.page_count = page_count
        await self._session.flush()
        return document

    async def update_metadata(
        self,
        document: Document,
        *,
        author: str | None = None,
        metadata: dict | None = None,
    ) -> Document:
        if author is not None:
            document.author = author
        if metadata is not None:
            document.metadata_ = metadata
        document.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return document

    async def soft_delete(self, document: Document) -> None:
        document.deleted_at = datetime.now(timezone.utc)
        document.updated_at = datetime.now(timezone.utc)
        await self._session.flush()


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, chunk_id: uuid.UUID, document_id: uuid.UUID) -> DocumentChunk | None:
        result = await self._session.execute(
            select(DocumentChunk).where(
                DocumentChunk.id == chunk_id,
                DocumentChunk.document_id == document_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_document(
        self,
        document_id: uuid.UUID,
        *,
        page_number: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[DocumentChunk], int]:
        base = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        if page_number is not None:
            base = base.where(DocumentChunk.page_number == page_number)

        total = (await self._session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()

        result = await self._session.execute(
            base.order_by(DocumentChunk.chunk_index)
               .offset((page - 1) * page_size)
               .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def bulk_insert(self, chunks: list[DocumentChunk]) -> None:
        self._session.add_all(chunks)
        await self._session.flush()


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, job: IngestionJob) -> IngestionJob:
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def list_by_document(self, document_id: uuid.UUID) -> list[IngestionJob]:
        result = await self._session.execute(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_started(self, job: IngestionJob) -> IngestionJob:
        job.started_at = datetime.now(timezone.utc)
        await self._session.flush()
        return job

    async def mark_finished(self, job: IngestionJob, *, error_detail: str | None = None) -> IngestionJob:
        job.finished_at = datetime.now(timezone.utc)
        job.error_detail = error_detail
        await self._session.flush()
        return job

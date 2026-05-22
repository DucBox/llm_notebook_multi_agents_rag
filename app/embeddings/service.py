import logging
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import DocumentNotFoundError
from app.documents.models import Document, DocumentChunk, DocumentStatus
from app.embeddings.providers.ollama import OllamaEmbeddingProvider

logger = logging.getLogger(__name__)


def _get_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )


async def embed_document(document_id: uuid.UUID, session: AsyncSession) -> dict:
    doc = await session.get(Document, document_id)
    if not doc or doc.deleted_at is not None:
        raise DocumentNotFoundError(str(document_id))

    if doc.status != DocumentStatus.PROCESSED:
        raise ValueError(f"Document must be PROCESSED before embedding. Current status: {doc.status}")

    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding.is_(None))
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = list(result.scalars().all())

    embedded_count = 0
    batch_size = settings.EMBEDDING_BATCH_SIZE

    if chunks:
        provider = _get_provider()
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i: i + batch_size]
            vectors = await provider.embed([c.text_content for c in batch])
            for chunk, vector in zip(batch, vectors):
                chunk.embedding = vector
            await session.flush()
            embedded_count += len(batch)

    await session.commit()
    return {
        "document_id": str(document_id),
        "embedded_chunks": embedded_count,
    }


async def get_embedding_status(document_id: uuid.UUID, session: AsyncSession) -> dict:
    doc = await session.get(Document, document_id)
    if not doc or doc.deleted_at is not None:
        raise DocumentNotFoundError(str(document_id))

    total_result = await session.execute(
        select(func.count()).where(DocumentChunk.document_id == document_id)
    )
    total = total_result.scalar_one()

    embedded_result = await session.execute(
        select(func.count())
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding.is_not(None))
    )
    embedded = embedded_result.scalar_one()

    return {
        "document_id": str(document_id),
        "total_chunks": total,
        "embedded_chunks": embedded,
        "pending_chunks": total - embedded,
        "is_complete": total > 0 and embedded == total,
    }

import logging
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import DocumentNotFoundError
from app.documents.models import Document, DocumentChunk, DocumentStatus
from app.embeddings.providers.ollama import OllamaEmbeddingProvider
from app.embeddings.providers.openai import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


def _get_online_provider() -> OpenAIEmbeddingProvider:
    return OpenAIEmbeddingProvider(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )


def _get_offline_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OFFLINE_EMBEDDING_MODEL,
        dimension=settings.OFFLINE_EMBEDDING_DIMENSION,
    )


async def embed_document(document_id: uuid.UUID, session: AsyncSession) -> dict:
    doc = await session.get(Document, document_id)
    if not doc or doc.deleted_at is not None:
        raise DocumentNotFoundError(str(document_id))

    if doc.status != DocumentStatus.PROCESSED:
        raise ValueError(f"Document must be PROCESSED before embedding. Current status: {doc.status}")

    # Load chunks missing online embedding
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding.is_(None))
        .order_by(DocumentChunk.chunk_index)
    )
    chunks_online = list(result.scalars().all())

    # Load chunks missing offline embedding
    result2 = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding_offline.is_(None))
        .order_by(DocumentChunk.chunk_index)
    )
    chunks_offline = list(result2.scalars().all())

    online_count = 0
    offline_count = 0
    batch_size = settings.EMBEDDING_BATCH_SIZE

    # Online embeddings
    if chunks_online:
        provider = _get_online_provider()
        for i in range(0, len(chunks_online), batch_size):
            batch = chunks_online[i: i + batch_size]
            vectors = await provider.embed([c.text_content for c in batch])
            for chunk, vector in zip(batch, vectors):
                chunk.embedding = vector
            await session.flush()
            online_count += len(batch)

    # Offline embeddings — fail gracefully if Ollama is not running
    if chunks_offline:
        try:
            offline_provider = _get_offline_provider()
            for i in range(0, len(chunks_offline), batch_size):
                batch = chunks_offline[i: i + batch_size]
                vectors = await offline_provider.embed([c.text_content for c in batch])
                for chunk, vector in zip(batch, vectors):
                    chunk.embedding_offline = vector
                await session.flush()
                offline_count += len(batch)
        except Exception as exc:
            logger.warning("Offline embedding skipped (Ollama unavailable?): %s", exc)

    await session.commit()
    return {
        "document_id": str(document_id),
        "embedded_online": online_count,
        "embedded_offline": offline_count,
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

    embedded_offline_result = await session.execute(
        select(func.count())
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding_offline.is_not(None))
    )
    embedded_offline = embedded_offline_result.scalar_one()

    return {
        "document_id": str(document_id),
        "total_chunks": total,
        "embedded_chunks": embedded,
        "embedded_offline_chunks": embedded_offline,
        "pending_chunks": total - embedded,
        "is_complete": total > 0 and embedded == total,
    }

import uuid

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.documents.models import Document, DocumentChunk
from app.embeddings.providers.openai import OpenAIEmbeddingProvider
from app.retrieval.schemas import ChunkResult


def _get_provider() -> OpenAIEmbeddingProvider:
    return OpenAIEmbeddingProvider(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )


async def semantic_search(
    query: str,
    top_n: int,
    session: AsyncSession,
    document_ids: list[uuid.UUID] | None = None,
    user_id: uuid.UUID | None = None,
) -> list[ChunkResult]:
    provider = _get_provider()
    vectors = await provider.embed([query])
    query_vector = vectors[0]

    cast_vec = sa.cast(query_vector, Vector(settings.EMBEDDING_DIMENSION))
    distance_col = DocumentChunk.embedding.op("<=>")(cast_vec).label("distance")

    stmt = (
        sa.select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            Document.filename.label("document_filename"),
            DocumentChunk.chunk_index,
            DocumentChunk.page_number,
            DocumentChunk.page_number_end,
            DocumentChunk.text_content,
            DocumentChunk.char_offset_start,
            DocumentChunk.char_offset_end,
            distance_col,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .where(Document.deleted_at.is_(None))
        .order_by(distance_col.asc())
        .limit(top_n)
    )

    if user_id:
        stmt = stmt.where(Document.user_id == user_id)
    if document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

    rows = (await session.execute(stmt)).mappings().all()

    return [
        ChunkResult(
            chunk_id=row["id"],
            document_id=row["document_id"],
            document_filename=row["document_filename"],
            chunk_index=row["chunk_index"],
            page_number=row["page_number"],
            page_number_end=row["page_number_end"],
            text_content=row["text_content"],
            char_offset_start=row["char_offset_start"],
            char_offset_end=row["char_offset_end"],
            score=round(1.0 - float(row["distance"]), 4),
        )
        for row in rows
    ]

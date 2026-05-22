import uuid

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.documents.models import Document, DocumentChunk
from app.embeddings.providers.ollama import OllamaEmbeddingProvider
from app.retrieval import reranker as reranker_module
from app.retrieval.schemas import ChunkResult


def _get_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.EMBEDDING_MODEL,
        dimension=settings.EMBEDDING_DIMENSION,
    )


async def semantic_search(
    query: str,
    top_n: int,
    session: AsyncSession,
    retrieve_n: int = 20,
    document_ids: list[uuid.UUID] | None = None,
    user_id: uuid.UUID | None = None,
    rerank: bool = False,
) -> list[ChunkResult]:
    provider = _get_provider()
    vectors = await provider.embed([query])
    query_vector = vectors[0]

    candidates_n = retrieve_n if rerank else top_n

    cast_vec = sa.cast(query_vector, Vector(settings.EMBEDDING_DIMENSION))
    distance_col = DocumentChunk.embedding.op("<=>", return_type=sa.Float)(cast_vec).label("distance")

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
        .limit(candidates_n)
    )

    if user_id:
        stmt = stmt.where(Document.user_id == user_id)
    if document_ids is not None:
        stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))

    rows = (await session.execute(stmt)).mappings().all()
    if not rows:
        return []

    chunks = [
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

    if rerank and settings.RERANKER_ENABLED:
        rerank_scores = await reranker_module.rerank(query, [c.text_content for c in chunks])
        for chunk, rr_score in zip(chunks, rerank_scores):
            chunk.rerank_score = round(float(rr_score), 4)
        chunks.sort(key=lambda c: c.rerank_score, reverse=True)

    return chunks[:top_n]

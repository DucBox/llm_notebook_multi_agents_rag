import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import DocumentNotFoundError
from app.embeddings import service

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post(
    "/documents/{document_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger embedding for all chunks of a document",
)
async def embed_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await service.embed_document(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get(
    "/documents/{document_id}/status",
    summary="Check embedding status for a document",
)
async def get_embedding_status(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    try:
        return await service.get_embedding_status(document_id, session)
    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.config import settings
from app.generation import service
from app.generation.schemas import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    session: AsyncSession = Depends(get_db),
):
    answer, sources = await service.generate_answer(
        query=payload.query,
        session=session,
        top_n=payload.top_n,
        retrieve_n=payload.retrieve_n,
        document_ids=payload.document_ids,
    )
    return GenerateResponse(
        query=payload.query,
        answer=answer,
        sources=sources,
        model=settings.GENERATION_MODEL,
    )

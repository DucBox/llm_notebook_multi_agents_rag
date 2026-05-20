from fastapi import APIRouter

from app.config import settings
from app.generation import service
from app.generation.schemas import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerateResponse)
async def generate(payload: GenerateRequest):
    answer = await service.generate_answer(
        query=payload.query,
        chunks=payload.chunks,
    )
    return GenerateResponse(
        query=payload.query,
        answer=answer,
        sources=payload.chunks,
        model=settings.GENERATION_MODEL,
    )

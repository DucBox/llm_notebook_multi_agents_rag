from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.config import settings
from app.generation import service
from app.generation.schemas import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
):
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

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.retrieval import service
from app.retrieval.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["retrieval"])


@router.post("", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = await service.semantic_search(
        query=payload.query,
        top_n=payload.top_n,
        session=session,
        retrieve_n=payload.retrieve_n,
        document_ids=payload.document_ids,
        user_id=current_user.id,
    )
    return QueryResponse(
        query=payload.query,
        top_n=payload.top_n,
        total_results=len(results),
        results=results,
    )

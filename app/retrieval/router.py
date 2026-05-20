from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.retrieval import service
from app.retrieval.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["retrieval"])


@router.post("", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
):
    results = await service.semantic_search(
        query=payload.query,
        top_n=payload.top_n,
        session=session,
        retrieve_n=payload.retrieve_n,
        document_ids=payload.document_ids,
    )
    return QueryResponse(
        query=payload.query,
        top_n=payload.top_n,
        total_results=len(results),
        results=results,
    )

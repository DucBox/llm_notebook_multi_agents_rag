import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.config import settings
from app.conversations import service
from app.conversations.schemas import (
    ChatRequest,
    ChatResponse,
    CompactResponse,
    ConversationCreate,
    ConversationRead,
    MessageRead,
)

from app.core.database import get_db
from app.core.exceptions import ConversationCompactingError

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.list_conversations(current_user.id, session)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await service.delete_conversation(conversation_id, current_user.id, session)


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_conversation(user_id=current_user.id, session=session)


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_conversation(conversation_id, session, current_user.id)


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_messages(conversation_id, session, current_user.id)




@router.post("/{conversation_id}/compact", response_model=CompactResponse)
async def manual_compact(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = await service.get_conversation(conversation_id, session, current_user.id)
    if conv.status == "compacting":
        raise ConversationCompactingError(str(conversation_id))
    await service.compact_conversation(conv, session)
    await session.refresh(conv)
    return CompactResponse(
        conversation_id=conversation_id,
        compacted=True,
        total_token_count=conv.total_token_count,
        context_limit_tokens=settings.CONTEXT_LIMIT_TOKENS,
        usage_pct=round(conv.total_token_count / settings.CONTEXT_LIMIT_TOKENS * 100, 1),
    )


@router.post("/{conversation_id}/chat", response_model=ChatResponse)
async def chat(
    conversation_id: uuid.UUID,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.chat(
        conversation_id=conversation_id,
        query=payload.query,
        session=session,
        user_id=current_user.id,
        document_ids=payload.document_ids,
        top_n=payload.top_n,
        retrieve_n=payload.retrieve_n,
        rerank=payload.rerank,
        model=payload.model,
    )

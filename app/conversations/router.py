import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations import service
from app.conversations.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationRead,
    MessageRead,
)
from app.core.database import get_db

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    session: AsyncSession = Depends(get_db),
):
    conv = await service.create_conversation(user_id=payload.user_id, session=session)
    return conv


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    return await service.get_conversation(conversation_id, session)


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    return await service.get_messages(conversation_id, session)


@router.post("/{conversation_id}/chat", response_model=ChatResponse)
async def chat(
    conversation_id: uuid.UUID,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db),
):
    return await service.chat(
        conversation_id=conversation_id,
        query=payload.query,
        session=session,
        document_ids=payload.document_ids,
        top_n=payload.top_n,
        retrieve_n=payload.retrieve_n,
    )

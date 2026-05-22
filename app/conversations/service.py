import uuid

import httpx
import sqlalchemy as sa
import tiktoken
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.conversations.models import Conversation, Message
from app.core.exceptions import ConversationCompactingError, ConversationNotFoundError
from app.retrieval import service as retrieval_service
from app.retrieval.schemas import ChunkResult

_ENCODING = tiktoken.get_encoding("cl100k_base")

_SYSTEM_INSTRUCTIONS = """\
You are LLM Notebook, an intelligent assistant specializing in analyzing and answering questions based on provided documents.
Hosted on local infrastructure by Ngô Quang Đức.

Rules:
- Only answer based on information found in the [Information in Documents] section.
- Always cite sources: mention the document name and page number (if available).
- If there is insufficient information, respond: "Không có câu trả lời cụ thể vì thiếu thông tin trong tài liệu."
- Be concise and accurate.
- IMPORTANT: Always respond in the SAME language as the user's question. If the user asks in Vietnamese, respond in Vietnamese. Do NOT respond in Chinese.
"""

_COMPACT_INSTRUCTIONS = """\
You are a conversation summarizer. Summarize the conversation history below concisely.
Retain important facts, events, and key conclusions from what the user asked and what was answered.
The summary will be used as background context for follow-up questions in the same session.
Respond in the same language as the conversation (Vietnamese if the conversation is in Vietnamese).
"""


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _build_prompt(
    query: str,
    chunks: list[ChunkResult],
    active_messages: list[Message],
    compacted_history: str | None,
) -> str:
    parts = []

    if compacted_history:
        parts.append("[Compacted History Chat]")
        parts.append(compacted_history)

    if active_messages:
        parts.append("[History Chat]")
        for msg in active_messages:
            role_label = "Người dùng" if msg.role == "user" else "Trợ lý"
            parts.append(f"{role_label}: {msg.content}")

    parts.append("[Information in Documents]")
    for i, chunk in enumerate(chunks, 1):
        page_info = f", trang {chunk.page_number}" if chunk.page_number else ""
        parts.append(f"\n[{i}] Nguồn: {chunk.document_filename}{page_info}")
        parts.append(chunk.text_content)
        parts.append("---")

    parts.append("\n[User Query]")
    parts.append(query)

    return "\n".join(parts)


def _sanitize(text: str) -> str:
    """Strip control characters that break JSON serialization (e.g. qwen think tokens)."""
    return "".join(ch for ch in text if ch >= " " or ch in "\t\n\r")


async def _llm_generate(prompt: str, model: str | None = None) -> str:
    actual_model = model or settings.LLM_MODEL
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
            json={
                "model": actual_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        return _sanitize(resp.json()["choices"][0]["message"]["content"] or "")


async def _llm_compact(history_text: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
            json={
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": _COMPACT_INSTRUCTIONS},
                    {"role": "user", "content": history_text},
                ],
            },
        )
        resp.raise_for_status()
        return _sanitize(resp.json()["choices"][0]["message"]["content"] or "")


async def _get_active_messages(conversation_id: uuid.UUID, session: AsyncSession) -> list[Message]:
    stmt = (
        sa.select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.is_compacted.is_(False))
        .order_by(Message.created_at, sa.case((Message.role == "user", 0), else_=1))
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def compact_conversation(conv: Conversation, session: AsyncSession) -> None:
    conv.status = "compacting"
    await session.commit()

    try:
        messages = await _get_active_messages(conv.id, session)

        if len(messages) <= 2:
            conv.status = "active"
            await session.commit()
            return

        to_compact = messages[:-2]
        to_keep = messages[-2:]

        history_lines = []
        if conv.compacted_history:
            history_lines.append(f"[Tóm tắt trước đó]\n{conv.compacted_history}\n")
            history_lines.append("[Hội thoại tiếp theo]")
        for msg in to_compact:
            role_label = "Người dùng" if msg.role == "user" else "Trợ lý"
            history_lines.append(f"{role_label}: {msg.content}")

        summary = await _llm_compact("\n".join(history_lines))

        to_compact_ids = [m.id for m in to_compact]
        await session.execute(
            sa.update(Message)
            .where(Message.id.in_(to_compact_ids))
            .values(is_compacted=True)
        )

        kept_tokens = sum(m.token_count for m in to_keep)
        conv.compacted_history = summary
        conv.total_token_count = _count_tokens(summary) + kept_tokens
        conv.status = "active"
        await session.commit()

    except Exception:
        conv.status = "active"
        await session.commit()
        raise


# ── Public API ──────────────────────────────────────────────────────────────


async def list_conversations(
    user_id: uuid.UUID,
    session: AsyncSession,
) -> list[Conversation]:
    stmt = (
        sa.select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    conv = await get_conversation(conversation_id, session, user_id)
    await session.delete(conv)
    await session.commit()


async def create_conversation(
    user_id: uuid.UUID | None,
    session: AsyncSession,
) -> Conversation:
    conv = Conversation(user_id=user_id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or (user_id is not None and conv.user_id != user_id):
        raise ConversationNotFoundError(str(conversation_id))
    return conv


async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
) -> list[Message]:
    await get_conversation(conversation_id, session, user_id)
    stmt = (
        sa.select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, sa.case((Message.role == "user", 0), else_=1))
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def chat(
    conversation_id: uuid.UUID,
    query: str,
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = None,
    top_n: int = 10,
    retrieve_n: int = 20,
    rerank: bool = False,
    model: str | None = None,
) -> dict:
    conv = await get_conversation(conversation_id, session, user_id)
    if conv.status == "compacting":
        raise ConversationCompactingError(str(conversation_id))

    chunks = await retrieval_service.semantic_search(
        query=query,
        top_n=top_n,
        session=session,
        retrieve_n=retrieve_n,
        document_ids=document_ids,
        user_id=conv.user_id,
        rerank=rerank,
    )

    active_messages = await _get_active_messages(conversation_id, session)
    prompt = _build_prompt(query, chunks, active_messages, conv.compacted_history)

    answer = await _llm_generate(prompt, model=model)

    user_tokens = _count_tokens(query)
    assistant_tokens = _count_tokens(answer)
    turn_tokens = user_tokens + assistant_tokens

    session.add(Message(
        conversation_id=conversation_id,
        role="user",
        content=query,
        token_count=user_tokens,
    ))
    await session.commit()

    session.add(Message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        token_count=assistant_tokens,
        sources=[c.model_dump(mode="json") for c in chunks],
    ))

    new_total = conv.total_token_count + turn_tokens
    conv.total_token_count = new_total
    await session.commit()
    await session.refresh(conv)

    compacting_triggered = False
    threshold = int(settings.COMPACT_THRESHOLD * settings.CONTEXT_LIMIT_TOKENS)
    if new_total > threshold:
        compacting_triggered = True
        await compact_conversation(conv, session)

    return {
        "conversation_id": conversation_id,
        "query": query,
        "answer": answer,
        "sources": chunks,
        "token_count_this_turn": turn_tokens,
        "total_token_count": conv.total_token_count,
        "context_limit_tokens": settings.CONTEXT_LIMIT_TOKENS,
        "usage_pct": round(conv.total_token_count / settings.CONTEXT_LIMIT_TOKENS * 100, 1),
        "compacting_triggered": compacting_triggered,
        "model": model or settings.LLM_MODEL,
    }

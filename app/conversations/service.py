import uuid

import sqlalchemy as sa
import tiktoken
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.conversations.models import Conversation, Message
from app.core.exceptions import ConversationCompactingError, ConversationNotFoundError
from app.retrieval import service as retrieval_service
from app.retrieval.schemas import ChunkResult

_ENCODING = tiktoken.get_encoding("cl100k_base")

_SYSTEM_INSTRUCTIONS = """\
Bạn là LLM Notebook, trợ lý thông minh chuyên phân tích và trả lời câu hỏi dựa trên tài liệu được cung cấp.

Quy tắc:
- Chỉ trả lời dựa trên thông tin trong phần [Information in Documents].
- Luôn trích dẫn nguồn: ghi rõ tên tài liệu và số trang (nếu có) khi đưa ra thông tin.
- Nếu không có đủ thông tin để trả lời, hãy phản hồi: "Không có câu trả lời cụ thể vì thiếu thông tin trong tài liệu."
- Trả lời ngắn gọn, chính xác. Dùng ngôn ngữ giống với câu hỏi của người dùng.
"""

_COMPACT_INSTRUCTIONS = """\
Bạn là công cụ tóm tắt lịch sử hội thoại. Hãy tóm tắt ngắn gọn nội dung hội thoại dưới đây.
Giữ lại các thông tin quan trọng, sự kiện, kết luận cốt lõi mà người dùng đã hỏi và được trả lời.
Bản tóm tắt sẽ được dùng làm ngữ cảnh nền cho các câu hỏi tiếp theo trong cùng phiên.
Trả lời bằng tiếng Việt, ngắn gọn, súc tích.
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

    prompt = "\n".join(parts)

    # --- DEBUG LOGGING (remove in prod) ---
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"[PROMPT DEBUG] has_compacted={bool(compacted_history)}  active_msgs={len(active_messages)}  chunks={len(chunks)}")
    print(prompt)
    print(sep)

    return prompt


async def _llm_generate(prompt: str) -> str:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.responses.create(
        model=settings.GENERATION_MODEL,
        reasoning={"effort": "low"},
        instructions=_SYSTEM_INSTRUCTIONS,
        input=prompt,
    )
    return response.output_text


async def _get_active_messages(conversation_id: uuid.UUID, session: AsyncSession) -> list[Message]:
    stmt = (
        sa.select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.is_compacted.is_(False))
        .order_by(Message.created_at)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def compact_conversation(conv: Conversation, session: AsyncSession) -> None:
    conv.status = "compacting"
    await session.commit()

    try:
        messages = await _get_active_messages(conv.id, session)

        # Need at least 2 turns (4 messages) to compact — keep the latest turn active
        if len(messages) <= 2:
            conv.status = "active"
            await session.commit()
            return

        # Split: compact everything except the last 1 turn (last user + assistant pair)
        to_compact = messages[:-2]
        to_keep = messages[-2:]

        # Build input for the compaction LLM call
        history_lines = []
        if conv.compacted_history:
            history_lines.append(f"[Tóm tắt trước đó]\n{conv.compacted_history}\n")
            history_lines.append("[Hội thoại tiếp theo]")
        for msg in to_compact:
            role_label = "Người dùng" if msg.role == "user" else "Trợ lý"
            history_lines.append(f"{role_label}: {msg.content}")

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.responses.create(
            model=settings.GENERATION_MODEL,
            instructions=_COMPACT_INSTRUCTIONS,
            input="\n".join(history_lines),
        )
        summary = resp.output_text

        sep = "=" * 60
        print(f"\n{sep}")
        print(f"[COMPACT] compacting {len(to_compact)} msgs → keeping last 1 turn ({len(to_keep)} msgs)")
        print(f"[COMPACT] summary:\n{summary}")
        print(sep)

        # Mark only the older messages as compacted, keep the last turn active
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
    await get_conversation(conversation_id, session, user_id)  # 404 + ownership guard
    stmt = (
        sa.select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    rows = await session.execute(stmt)
    return list(rows.scalars().all())


async def chat(
    conversation_id: uuid.UUID,
    query: str,
    session: AsyncSession,
    user_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = None,
    top_n: int = 5,
    retrieve_n: int = 10,
    rerank: bool = False,
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

    # Load active history and build prompt
    active_messages = await _get_active_messages(conversation_id, session)
    prompt = _build_prompt(query, chunks, active_messages, conv.compacted_history)

    # Generate answer
    answer = await _llm_generate(prompt)

    # Count tokens and persist messages
    user_tokens = _count_tokens(query)
    assistant_tokens = _count_tokens(answer)
    turn_tokens = user_tokens + assistant_tokens

    session.add(Message(
        conversation_id=conversation_id,
        role="user",
        content=query,
        token_count=user_tokens,
    ))
    session.add(Message(
        conversation_id=conversation_id,
        role="assistant",
        content=answer,
        token_count=assistant_tokens,
    ))

    new_total = conv.total_token_count + turn_tokens
    conv.total_token_count = new_total
    await session.commit()
    await session.refresh(conv)

    # Auto-compact if threshold exceeded
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
        "model": settings.GENERATION_MODEL,
    }

import uuid

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.retrieval import service as retrieval_service
from app.retrieval.schemas import ChunkResult

_SYSTEM_INSTRUCTIONS = """\
You are LLM Notebook, an assistant that answers questions strictly based on provided document chunks.

Rules:
- Answer ONLY from the context chunks below. Do not use outside knowledge.
- Always cite the source: mention the document filename and page number (if available).
- If the context does not contain enough information, say clearly: "Tôi không tìm thấy thông tin này trong các tài liệu được cung cấp."
- Be concise and accurate. Respond in the same language as the user's question.
"""


def _format_context(chunks: list[ChunkResult]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page_info = f", trang {chunk.page_number}" if chunk.page_number else ""
        parts.append(
            f"[{i}] Nguồn: {chunk.document_filename}{page_info}\n{chunk.text_content}"
        )
    return "\n\n---\n\n".join(parts)


async def generate_answer(
    query: str,
    session: AsyncSession,
    top_n: int = 5,
    retrieve_n: int | None = None,
    document_ids: list[uuid.UUID] | None = None,
    user_id: uuid.UUID | None = None,
) -> tuple[str, list[ChunkResult]]:
    chunks = await retrieval_service.semantic_search(
        query=query,
        top_n=top_n,
        session=session,
        retrieve_n=retrieve_n,
        document_ids=document_ids,
        user_id=user_id,
    )

    if not chunks:
        return "Tôi không tìm thấy thông tin này trong các tài liệu được cung cấp.", []

    context = _format_context(chunks)
    user_message = f"Ngữ cảnh tài liệu:\n\n{context}\n\nCâu hỏi: {query}"

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.responses.create(
        model=settings.GENERATION_MODEL,
        reasoning={"effort": "low"},
        instructions=_SYSTEM_INSTRUCTIONS,
        input=user_message,
    )

    answer = response.output_text
    return answer, chunks

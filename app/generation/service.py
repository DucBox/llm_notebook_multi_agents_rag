import httpx

from app.config import settings
from app.retrieval.schemas import ChunkResult

_SYSTEM_INSTRUCTIONS = """\
You are LLM Notebook, an intelligent assistant specializing in analyzing and answering questions based on provided documents.
Hosted on local infrastructure by Ngô Quang Đức.

Rules:
- Only answer based on information found in the [Information in Documents] section.
- Always cite sources: mention the document name and page number (if available).
- If there is insufficient information, respond: "Không có câu trả lời cụ thể vì thiếu thông tin trong tài liệu."
- Be concise and accurate.
- IMPORTANT: Always respond in the SAME language as the user's question.
"""


def _build_prompt(query: str, chunks: list[ChunkResult]) -> str:
    lines = ["[Information in Documents]"]
    for i, chunk in enumerate(chunks, 1):
        page_info = f", trang {chunk.page_number}" if chunk.page_number else ""
        lines.append(f"\n[{i}] Nguồn: {chunk.document_filename}{page_info}")
        lines.append(chunk.text_content)
        lines.append("---")

    lines.append("\n[User Query]")
    lines.append(query)

    return "\n".join(lines)


async def generate_answer(
    query: str,
    chunks: list[ChunkResult],
) -> str:
    if not chunks:
        return "Không có câu trả lời cụ thể vì thiếu thông tin trong tài liệu."

    prompt = _build_prompt(query, chunks)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
            json={
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""

from openai import AsyncOpenAI

from app.config import settings
from app.retrieval.schemas import ChunkResult

_SYSTEM_INSTRUCTIONS = """\
Bạn là LLM Notebook, trợ lý thông minh chuyên phân tích và trả lời câu hỏi dựa trên tài liệu được cung cấp.

Quy tắc:
- Chỉ trả lời dựa trên thông tin trong phần [Information in Documents].
- Luôn trích dẫn nguồn: ghi rõ tên tài liệu và số trang (nếu có) khi đưa ra thông tin.
- Nếu không có đủ thông tin để trả lời, hãy phản hồi: "Không có câu trả lời cụ thể vì thiếu thông tin trong tài liệu."
- Trả lời ngắn gọn, chính xác. Dùng ngôn ngữ giống với câu hỏi của người dùng.
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

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.responses.create(
        model=settings.GENERATION_MODEL,
        reasoning={"effort": "low"},
        instructions=_SYSTEM_INSTRUCTIONS,
        input=prompt,
    )

    return response.output_text

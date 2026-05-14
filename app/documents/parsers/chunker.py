import hashlib
from dataclasses import dataclass, field

from app.core.constants import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.documents.parsers.base import ParsedDocument, ParsedPage


@dataclass
class ChunkData:
    chunk_index: int
    text_content: str
    token_count: int
    char_offset_start: int
    char_offset_end: int
    page_number: int | None
    page_number_end: int | None
    content_sha256: str
    metadata: dict = field(default_factory=dict)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_page_for_offset(
    pages: list[ParsedPage], char_offset: int
) -> int | None:
    if not pages:
        return None
    cumulative = 0
    for page in pages:
        end = cumulative + len(page.text)
        if char_offset <= end:
            return page.page_number
        cumulative = end + 1
    return pages[-1].page_number


def _build_token_char_map(text: str, enc) -> list[int]:
    offsets: list[int] = []
    char_pos = 0
    for token in enc.encode(text):
        offsets.append(char_pos)
        char_pos += len(enc.decode([token]))
    offsets.append(char_pos)
    return offsets


def chunk_document(
    parsed: ParsedDocument,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[ChunkData]:
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")

    full_text = parsed.full_text
    all_tokens = enc.encode(full_text)

    if not all_tokens:
        return []

    token_positions = _build_token_char_map(full_text, enc)
    step = max(1, chunk_size - overlap)
    chunks: list[ChunkData] = []

    for i, start_token in enumerate(range(0, len(all_tokens), step)):
        end_token = min(start_token + chunk_size, len(all_tokens))
        chunk_tokens = all_tokens[start_token:end_token]
        chunk_text = enc.decode(chunk_tokens)

        char_start = token_positions[start_token]
        char_end = token_positions[end_token] if end_token < len(token_positions) else len(full_text)

        chunks.append(ChunkData(
            chunk_index=i,
            text_content=chunk_text,
            token_count=len(chunk_tokens),
            char_offset_start=char_start,
            char_offset_end=char_end,
            page_number=_find_page_for_offset(parsed.pages, char_start),
            page_number_end=_find_page_for_offset(parsed.pages, char_end - 1),
            content_sha256=_sha256(chunk_text),
        ))

        if end_token == len(all_tokens):
            break

    return chunks

from pathlib import Path

from app.core.constants import STATUS_TRANSITIONS
from app.core.exceptions import InvalidStatusTransitionError
from app.documents.models import DocumentChunk, DocumentStatus
from app.documents.parsers import parse_file
from app.documents.parsers.chunker import ChunkData, chunk_document


def validate_status_transition(current: DocumentStatus, target: DocumentStatus) -> None:
    allowed = STATUS_TRANSITIONS.get(current.value, set())
    if target.value not in allowed:
        raise InvalidStatusTransitionError(current.value, target.value)


def parse_and_chunk(file_path: Path, mime_type: str) -> tuple[list[ChunkData], int]:
    parsed = parse_file(file_path, mime_type)
    chunks = chunk_document(parsed)
    return chunks, parsed.page_count


def build_chunk_models(chunk_data_list: list[ChunkData], document_id) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            document_id=document_id,
            chunk_index=c.chunk_index,
            page_number=c.page_number,
            page_number_end=c.page_number_end,
            text_content=c.text_content,
            token_count=c.token_count,
            char_offset_start=c.char_offset_start,
            char_offset_end=c.char_offset_end,
            content_sha256=c.content_sha256,
            metadata_=c.metadata,
        )
        for c in chunk_data_list
    ]

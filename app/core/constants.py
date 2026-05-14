from typing import FrozenSet

ALLOWED_MIME_TYPES: FrozenSet[str] = frozenset({
    "application/pdf",
    "text/plain",
    "text/markdown",
})

ALLOWED_EXTENSIONS: FrozenSet[str] = frozenset({".pdf", ".txt", ".md"})

MAX_FILE_SIZE_BYTES_DEFAULT = 50 * 1024 * 1024  # 50 MB

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PENDING":    {"PROCESSING", "FAILED"},
    "PROCESSING": {"PROCESSED", "FAILED"},
    "PROCESSED":  set(),
    "FAILED":     {"PENDING"},
}

DEFAULT_CHUNK_SIZE = 512       # tokens per chunk
DEFAULT_CHUNK_OVERLAP = 64     # overlapping tokens between chunks

import hashlib
import re
import uuid
from pathlib import Path

import aiofiles
import aiofiles.os

from app.config import settings
from app.core.constants import ALLOWED_EXTENSIONS
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError

_MIME_MAP = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md":  "text/markdown",
}


def _detect_mime_type(filename: str) -> str:
    return _MIME_MAP.get(Path(filename).suffix.lower(), "application/octet-stream")


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200]


def validate_upload(filename: str, file_size: int) -> str:
    """Validates extension and size. Returns detected mime_type."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(_detect_mime_type(filename))
    if file_size > settings.max_file_size_bytes:
        raise FileTooLargeError(file_size, settings.max_file_size_bytes)
    return _detect_mime_type(filename)


async def save_file(data: bytes, filename: str, document_id: uuid.UUID) -> tuple[Path, str]:
    """Saves bytes to storage. Returns (file_path, sha256_hex)."""
    sanitized = _sanitize_filename(filename)
    doc_dir = Path(settings.STORAGE_PATH) / str(document_id)
    await aiofiles.os.makedirs(doc_dir, exist_ok=True)

    file_path = doc_dir / sanitized
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(data)

    return file_path, hashlib.sha256(data).hexdigest()


async def delete_file(file_path: str) -> None:
    path = Path(file_path)
    if path.exists():
        await aiofiles.os.remove(path)
        try:
            path.parent.rmdir()
        except OSError:
            pass

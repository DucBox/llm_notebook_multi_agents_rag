from pathlib import Path

from app.core.exceptions import UnsupportedFileTypeError
from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedPage
from app.documents.parsers.pdf import PDFParser
from app.documents.parsers.text import PlainTextParser

# Registry: thêm format mới chỉ cần append vào đây
_REGISTRY: list[BaseParser] = [
    PDFParser(),
    PlainTextParser(),
]


def get_parser(mime_type: str) -> BaseParser:
    for parser in _REGISTRY:
        if parser.can_parse(mime_type):
            return parser
    raise UnsupportedFileTypeError(mime_type)


def parse_file(file_path: Path, mime_type: str) -> ParsedDocument:
    return get_parser(mime_type).parse(file_path)


__all__ = [
    "BaseParser",
    "ParsedDocument",
    "ParsedPage",
    "get_parser",
    "parse_file",
]

from pathlib import Path

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedPage


class PlainTextParser(BaseParser):
    def supported_mime_types(self) -> frozenset[str]:
        return frozenset({"text/plain", "text/markdown"})

    def parse(self, file_path: Path) -> ParsedDocument:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return ParsedDocument.from_pages([ParsedPage(page_number=1, text=text)])

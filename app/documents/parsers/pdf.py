from pathlib import Path

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedPage


class PDFParser(BaseParser):
    def supported_mime_types(self) -> frozenset[str]:
        return frozenset({"application/pdf"})

    def parse(self, file_path: Path) -> ParsedDocument:
        import fitz  # PyMuPDF — lazy import

        pages: list[ParsedPage] = []
        with fitz.open(str(file_path)) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text")
                if text.strip():
                    pages.append(ParsedPage(page_number=i, text=text))

        return ParsedDocument.from_pages(pages)

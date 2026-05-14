from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedPage:
    page_number: int  # 1-based
    text: str


@dataclass
class ParsedDocument:
    pages: list[ParsedPage] = field(default_factory=list)
    full_text: str = ""
    page_count: int = 0

    @classmethod
    def from_pages(cls, pages: list[ParsedPage]) -> "ParsedDocument":
        full_text = "\n".join(p.text for p in pages)
        return cls(pages=pages, full_text=full_text, page_count=len(pages))


class BaseParser(ABC):
    @abstractmethod
    def supported_mime_types(self) -> frozenset[str]:
        """Returns the set of MIME types this parser handles."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        """Parses the file and returns a ParsedDocument."""

    def can_parse(self, mime_type: str) -> bool:
        return mime_type in self.supported_mime_types()

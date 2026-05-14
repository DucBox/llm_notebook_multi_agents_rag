import pytest

from app.documents.parsers.base import ParsedDocument, ParsedPage
from app.documents.parsers.chunker import ChunkData, _sha256, chunk_document


def _make_doc(text: str, pages: int = 1) -> ParsedDocument:
    page_size = len(text) // pages
    parsed_pages = []
    for i in range(pages):
        start = i * page_size
        end = start + page_size if i < pages - 1 else len(text)
        parsed_pages.append(ParsedPage(page_number=i + 1, text=text[start:end]))
    return ParsedDocument.from_pages(parsed_pages)


def test_empty_document_returns_no_chunks():
    chunks = chunk_document(_make_doc(""))
    assert chunks == []


def test_short_text_produces_single_chunk():
    chunks = chunk_document(_make_doc("Hello world, this is a short document."))
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].char_offset_start == 0
    assert chunks[0].char_offset_end > 0


def test_chunk_indices_are_sequential():
    text = " ".join(["word"] * 2000)
    chunks = chunk_document(_make_doc(text), chunk_size=100, overlap=10)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_char_offsets_cover_full_text():
    text = "The quick brown fox jumps over the lazy dog. " * 30
    chunks = chunk_document(_make_doc(text), chunk_size=50, overlap=5)
    assert chunks[0].char_offset_start == 0
    assert chunks[-1].char_offset_end <= len(text) + 1


def test_char_offsets_non_overlapping_at_boundaries():
    text = "abcdefghij " * 100
    chunks = chunk_document(_make_doc(text), chunk_size=50, overlap=0)
    for i in range(len(chunks) - 1):
        assert chunks[i].char_offset_end <= chunks[i + 1].char_offset_start + 1


def test_content_sha256_deterministic():
    doc = _make_doc("Same text produces same hash")
    assert chunk_document(doc)[0].content_sha256 == chunk_document(doc)[0].content_sha256


def test_sha256_helper():
    assert _sha256("hello") == _sha256("hello")
    assert _sha256("hello") != _sha256("world")


def test_token_count_positive():
    chunks = chunk_document(_make_doc("A sentence with several words that should count tokens correctly."))
    assert all(c.token_count and c.token_count > 0 for c in chunks)


def test_page_number_assigned_multi_page():
    page1 = ParsedPage(page_number=1, text="Page one content. " * 20)
    page2 = ParsedPage(page_number=2, text="Page two content. " * 20)
    doc = ParsedDocument.from_pages([page1, page2])
    chunks = chunk_document(doc, chunk_size=30, overlap=0)
    page_numbers = {c.page_number for c in chunks}
    assert 1 in page_numbers
    assert 2 in page_numbers

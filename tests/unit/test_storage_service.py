import pytest

from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.documents.storage import _sanitize_filename, validate_upload


def test_validate_upload_accepts_pdf():
    assert validate_upload("report.pdf", 1024) == "application/pdf"


def test_validate_upload_accepts_txt():
    assert validate_upload("notes.txt", 1024) == "text/plain"


def test_validate_upload_accepts_md():
    assert validate_upload("readme.md", 1024) == "text/markdown"


def test_validate_upload_rejects_unknown_extension():
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload("malware.exe", 1024)


def test_validate_upload_rejects_oversized_file():
    with pytest.raises(FileTooLargeError):
        validate_upload("big.pdf", 60 * 1024 * 1024)


def test_sanitize_filename_strips_path_traversal():
    result = _sanitize_filename("../../etc/passwd")
    assert "/" not in result
    assert ".." not in result


def test_sanitize_filename_replaces_special_chars():
    result = _sanitize_filename("my file (1).pdf")
    assert " " not in result
    assert "(" not in result


def test_sanitize_filename_preserves_extension():
    assert _sanitize_filename("document.pdf").endswith(".pdf")


def test_sanitize_filename_truncates_long_name():
    assert len(_sanitize_filename("a" * 300 + ".pdf")) <= 200

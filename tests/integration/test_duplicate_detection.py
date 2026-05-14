import hashlib
import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_check_duplicate_not_found(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents/check-duplicate",
        json={"content_sha256": "0" * 64},
    )
    assert response.status_code == 200
    assert response.json()["exists"] is False


@pytest.mark.asyncio
async def test_check_duplicate_found_after_upload(client: AsyncClient, sample_txt_file: bytes):
    unique_content = sample_txt_file + b" dedup_test_unique"
    sha256 = hashlib.sha256(unique_content).hexdigest()

    await client.post(
        "/api/v1/documents",
        files={"file": ("dedup.txt", io.BytesIO(unique_content), "text/plain")},
    )

    response = await client.post(
        "/api/v1/documents/check-duplicate",
        json={"content_sha256": sha256},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["document_id"] is not None


@pytest.mark.asyncio
async def test_upload_duplicate_returns_409(client: AsyncClient, sample_txt_file: bytes):
    unique_content = sample_txt_file + b" conflict_test_unique"

    first = await client.post(
        "/api/v1/documents",
        files={"file": ("conflict.txt", io.BytesIO(unique_content), "text/plain")},
    )
    assert first.status_code == 202

    second = await client.post(
        "/api/v1/documents",
        files={"file": ("conflict_copy.txt", io.BytesIO(unique_content), "text/plain")},
    )
    assert second.status_code == 409
    assert "existing_document_id" in second.json()

import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_txt_document(client: AsyncClient, sample_txt_file: bytes):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("test.txt", io.BytesIO(sample_txt_file), "text/plain")},
    )
    assert response.status_code == 202
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["status"] in ("PENDING", "PROCESSING", "PROCESSED", "FAILED")
    assert "id" in data
    assert data["content_sha256"] != ""


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("malware.exe", io.BytesIO(b"binary data"), "application/octet-stream")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient):
    response = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_documents_returns_paginated(client: AsyncClient, sample_txt_file: bytes):
    await client.post(
        "/api/v1/documents",
        files={"file": ("list_test.txt", io.BytesIO(sample_txt_file + b" unique1"), "text/plain")},
    )
    response = await client.get("/api/v1/documents", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_get_document_after_upload(client: AsyncClient, sample_txt_file: bytes):
    upload = await client.post(
        "/api/v1/documents",
        files={"file": ("get_test.txt", io.BytesIO(sample_txt_file + b" unique2"), "text/plain")},
    )
    assert upload.status_code == 202
    doc_id = upload.json()["id"]

    response = await client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_delete_document_soft_deletes(client: AsyncClient, sample_txt_file: bytes):
    upload = await client.post(
        "/api/v1/documents",
        files={"file": ("delete_test.txt", io.BytesIO(sample_txt_file + b" unique3"), "text/plain")},
    )
    doc_id = upload.json()["id"]

    delete = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete.status_code == 204

    get = await client.get(f"/api/v1/documents/{doc_id}")
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_update_document_metadata(client: AsyncClient, sample_txt_file: bytes):
    upload = await client.post(
        "/api/v1/documents",
        files={"file": ("meta_test.txt", io.BytesIO(sample_txt_file + b" unique4"), "text/plain")},
    )
    doc_id = upload.json()["id"]

    response = await client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"author": "John Doe"},
    )
    assert response.status_code == 200
    assert response.json()["author"] == "John Doe"


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "db" in data

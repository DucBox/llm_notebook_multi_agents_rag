from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import (
    ConversationCompactingError,
    ConversationNotFoundError,
    DocumentDeletionError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    FileTooLargeError,
    InvalidStatusTransitionError,
    UnsupportedFileTypeError,
)
from app.conversations.router import router as conversations_router
from app.documents.router import router as documents_router
from app.embeddings.router import router as embeddings_router
from app.generation.router import router as generation_router
from app.retrieval.router import router as retrieval_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.RERANKER_ENABLED:
        import asyncio
        from app.retrieval.reranker import rerank
        # Warmup: forces model download + weight loading before first real request
        await rerank("warmup", ["warmup"])
    yield


app = FastAPI(
    title="LLM Notebook API",
    version=settings.APP_VERSION,
    description="Multi-agent RAG system for document Q&A with citations",
    lifespan=lifespan,
)

app.include_router(documents_router, prefix="/api/v1")
app.include_router(embeddings_router, prefix="/api/v1")
app.include_router(retrieval_router, prefix="/api/v1")
app.include_router(generation_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    # Patch: list[UploadFile] generates contentMediaType (OAS 3.1) which Swagger UI
    # doesn't render as a file picker. Force format:binary (OAS 3.0 style) instead.
    upload_body = schema.get("components", {}).get("schemas", {}).get(
        "Body_upload_documents_api_v1_documents_post"
    )
    if upload_body and "files" in upload_body.get("properties", {}):
        upload_body["properties"]["files"] = {
            "type": "array",
            "items": {"type": "string", "format": "binary"},
            "description": "PDF, TXT, or Markdown files",
        }
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.get("/api/v1/health", tags=["system"])
async def health_check():
    from pathlib import Path
    db_status = "ok"
    storage_status = "ok"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
    try:
        test = Path(settings.STORAGE_PATH) / ".health"
        test.touch()
        test.unlink()
    except Exception:
        storage_status = "error"

    overall = "ok" if db_status == "ok" and storage_status == "ok" else "degraded"
    return {"status": overall, "db": db_status, "storage": storage_status, "version": settings.APP_VERSION}


# ── Global exception handlers ──────────────────────────────────────────────────

@app.exception_handler(DocumentNotFoundError)
async def _not_found(request: Request, exc: DocumentNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateDocumentError)
async def _duplicate(request: Request, exc: DuplicateDocumentError):
    return JSONResponse(
        status_code=409,
        content={"detail": "Document already exists", "existing_document_id": exc.existing_document_id},
    )


@app.exception_handler(InvalidStatusTransitionError)
async def _bad_transition(request: Request, exc: InvalidStatusTransitionError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(UnsupportedFileTypeError)
async def _unsupported(request: Request, exc: UnsupportedFileTypeError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(FileTooLargeError)
async def _too_large(request: Request, exc: FileTooLargeError):
    return JSONResponse(status_code=413, content={"detail": str(exc)})


@app.exception_handler(DocumentDeletionError)
async def _deletion(request: Request, exc: DocumentDeletionError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ConversationNotFoundError)
async def _conv_not_found(request: Request, exc: ConversationNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ConversationCompactingError)
async def _conv_compacting(request: Request, exc: ConversationCompactingError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import (
    DocumentDeletionError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    FileTooLargeError,
    InvalidStatusTransitionError,
    UnsupportedFileTypeError,
)
from app.documents.router import router as documents_router
from app.embeddings.router import router as embeddings_router

app = FastAPI(
    title="LLM Notebook API",
    version=settings.APP_VERSION,
    description="Multi-agent RAG system for document Q&A with citations",
)

app.include_router(documents_router, prefix="/api/v1")
app.include_router(embeddings_router, prefix="/api/v1")


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

# LLM Notebook Clone — Project Context

## Mục tiêu sản phẩm

Hệ thống multi-agent RAG cho phép người dùng:
- Upload tài liệu (PDF, TXT, Markdown)
- Đặt câu hỏi bằng ngôn ngữ tự nhiên
- Nhận câu trả lời kèm **trích dẫn chính xác**: document nào, trang nào, đoạn nào

Tham chiếu gần nhất: [Google NotebookLM](https://notebooklm.google.com) — nhưng self-hosted, customizable, và có multi-agent pipeline.

---

## Kiến trúc tổng thể

```
app/
├── core/          # Cross-cutting: DB engine, Base ORM, exceptions, constants
├── common/        # Shared Pydantic schemas (PaginatedResponse, ...)
│
├── documents/     # ✅ Phase 1 — DONE
├── embeddings/    # 🔲 Phase 2
├── retrieval/     # 🔲 Phase 2–3
├── conversations/ # 🔲 Phase 3
└── agents/        # 🔲 Phase 4
```

**Nguyên tắc**: Domain-first (vertical slice). Mỗi domain là một package khép kín — models, schemas, repository, service, router trong cùng một folder. Thêm domain mới không đụng vào domain cũ.

---

## Domain Map & Roadmap

### ✅ Phase 1 — `documents/` (Hoàn thành)

**Bài toán**: Nhận file từ user → lưu trữ → parse → chunk → lưu text thô vào DB.

**Gồm:**

| File | Vai trò |
|------|---------|
| `models.py` | ORM: `Document`, `DocumentChunk`, `IngestionJob` |
| `schemas.py` | Pydantic I/O: `DocumentRead`, `ChunkRead`, `JobRead`, ... |
| `repository.py` | SQL queries: `DocumentRepository`, `ChunkRepository`, `JobRepository` |
| `service.py` | Use cases: `upload_document`, `get_document`, `list_documents`, `delete_document`, ... |
| `ingestion.py` | State machine, parse+chunk orchestration |
| `storage.py` | File I/O: save/delete trên disk, SHA-256 |
| `router.py` | FastAPI routes: `/documents`, `/documents/{id}/chunks`, `/documents/{id}/jobs` |
| `parsers/` | Parser registry: `BaseParser` → `PDFParser`, `PlainTextParser` + `chunker` |

**API endpoints:**

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/v1/documents/check-duplicate` | Pre-upload SHA-256 check |
| POST | `/api/v1/documents` | Upload + auto-chunk (sync) |
| GET | `/api/v1/documents` | List + filter + paginate |
| GET | `/api/v1/documents/{id}` | Metadata chi tiết |
| PATCH | `/api/v1/documents/{id}` | Update author/metadata |
| PATCH | `/api/v1/documents/{id}/status` | Chuyển trạng thái (internal) |
| DELETE | `/api/v1/documents/{id}` | Soft delete |
| GET | `/api/v1/documents/{id}/chunks` | List chunks (paginated) |
| GET | `/api/v1/documents/{id}/chunks/{chunk_id}` | Single chunk — dùng cho citation Phase 3 |
| GET | `/api/v1/documents/{id}/jobs` | Ingestion job history |
| GET | `/api/v1/health` | Health check |

**DB Tables:** `documents`, `document_chunks`, `ingestion_jobs`

---

### 🔲 Phase 2 — `embeddings/` (Chưa implement)

**Bài toán**: Lấy `text_content` từ mỗi `DocumentChunk` → gọi embedding model → lưu vector vào DB.

**Sẽ gồm:**
- `embeddings/providers/base.py` — `BaseEmbeddingProvider` (abstract)
- `embeddings/providers/openai.py` — OpenAI `text-embedding-3-small`
- `embeddings/providers/local.py` — sentence-transformers (offline)
- `embeddings/service.py` — `embed_document(document_id)`, batch embedding
- `embeddings/router.py` — trigger embedding, check status

**DB change**: chỉ cần một migration:
```sql
ALTER TABLE document_chunks ADD COLUMN embedding vector(1536);
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

**Dependency**: `pgvector` PostgreSQL extension.

---

### 🔲 Phase 2–3 — `retrieval/` (Chưa implement)

**Bài toán**: Nhận câu hỏi → embed query → tìm top-K chunks gần nhất → trả về kèm citation metadata.

**Sẽ gồm:**
- `retrieval/schemas.py` — `QueryRequest`, `RetrievalResult` (chunk + score + citation)
- `retrieval/service.py` — `semantic_search()`, `hybrid_search()` (vector + full-text)
- `retrieval/router.py` — `POST /api/v1/query`

**Citation output** (đã chuẩn bị từ Phase 1):
```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "document_name": "annual_report.pdf",
  "page_number": 3,
  "char_offset_start": 1024,
  "char_offset_end": 1536,
  "score": 0.92
}
```

---

### 🔲 Phase 3 — `conversations/` (Chưa implement)

**Bài toán**: Quản lý lịch sử hội thoại. User hỏi nhiều câu liên tiếp trong cùng session.

**Sẽ gồm:**
- `conversations/models.py` — `Conversation`, `Message`, `Citation` ORM
- `conversations/service.py` — tạo/lấy conversation, thêm message, lưu citations
- `conversations/router.py` — `POST /api/v1/conversations`, `GET /api/v1/conversations/{id}/messages`

**DB Tables mới:** `conversations`, `messages`, `citations`

**Async**: Phase 3 thêm Celery + Redis. `ingestion_jobs.task_id` (đã có, hiện NULL) sẽ được populate.

---

### 🔲 Phase 4 — `agents/` (Chưa implement)

**Bài toán**: Multi-agent orchestration. Orchestrator nhận câu hỏi → phân tích → dispatch cho các worker agents → tổng hợp kết quả.

**Sẽ gồm:**
```
agents/
├── orchestrator.py         # Nhận query, tạo plan, dispatch workers
├── workers/
│   ├── retrieval_worker.py # Tìm kiếm trong RAG corpus
│   └── web_worker.py       # Tìm kiếm web nếu corpus không đủ
└── tools/                  # Tool wrappers cho agents
```

**Pattern**: Blackboard (shared state qua DB) — agents đọc/ghi vào `conversations` table thay vì truyền message trực tiếp với nhau.

---

## Tech Stack

| Layer | Công nghệ |
|-------|----------|
| Web framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Database | PostgreSQL 16 |
| Vector search | pgvector (Phase 2+) |
| File parsing | PyMuPDF (PDF), built-in (TXT/MD) |
| Tokenization | tiktoken (cl100k_base) |
| Async queue | Redis + Celery (Phase 3+) |
| Migrations | Alembic |
| Container | Docker + Docker Compose |
| CI | GitHub Actions |
| Observability | Langfuse / Helicone (Phase 3+) |

---

## Thiết kế DB — Forward-Compatible

```
documents (1) ──< document_chunks (many)   ← Phase 1: text, Phase 2: + embedding vector
documents (1) ──< ingestion_jobs (many)    ← Phase 1: sync, Phase 3: Celery task_id

conversations (1) ──< messages (many)      ← Phase 3
messages (1) ──< citations (many)          ← Phase 3, FK → document_chunks.id
```

**Idempotency**: `content_sha256 UNIQUE` trên `documents` — tránh duplicate embedding.
**Soft delete**: `deleted_at` trên `documents` — giữ `document_chunks` để citation link không bị broken.
**Chunk offsets**: `char_offset_start/end` + `page_number` trên `document_chunks` — đủ data để highlight passage trong PDF viewer Phase 3+.

---

## Conventions

### Import paths
```python
# ✅ Đúng — import từ domain
from app.documents.models import Document
from app.documents.service import upload_document
from app.core.exceptions import DocumentNotFoundError
from app.common.schemas import PaginatedResponse

# ❌ Sai — không cross-import giữa các domain
from app.embeddings.service import embed  # gọi từ documents/ — sai
```

### Thêm file format mới (ví dụ DOCX)
```python
# 1. Tạo app/documents/parsers/docx.py
class DocxParser(BaseParser):
    def supported_mime_types(self): return frozenset({"application/vnd.openxmlformats..."})
    def parse(self, file_path): ...

# 2. Append vào app/documents/parsers/__init__.py
_REGISTRY: list[BaseParser] = [PDFParser(), PlainTextParser(), DocxParser()]

# 3. Thêm extension vào app/core/constants.py
ALLOWED_EXTENSIONS = frozenset({".pdf", ".txt", ".md", ".docx"})
```

### Thêm embedding provider mới (Phase 2)
```python
# Tương tự parser — tạo class kế thừa BaseEmbeddingProvider, append vào registry
```

### Status transitions (Document)
```
PENDING → PROCESSING → PROCESSED
PENDING → FAILED
PROCESSING → FAILED
FAILED → PENDING  (manual retry)
PROCESSED → (terminal, không transition được)
```

---

## Chạy local

```bash
# Khởi động DB + API
docker-compose up

# API docs
open http://localhost:8000/docs

# Chạy tests (cần test DB)
TEST_DATABASE_URL=postgresql+asyncpg://llm_user:llm_pass@localhost:5432/llm_notebook_test \
  pytest tests/ -v
```

---

## Trạng thái hiện tại (Phase 1 — hoàn thành)

- [x] Upload + parse + chunk documents (PDF, TXT, MD)
- [x] SHA-256 deduplication
- [x] Soft delete với citation safety
- [x] State machine ingestion (PENDING → PROCESSING → PROCESSED/FAILED)
- [x] REST API đầy đủ (CRUD + chunks + jobs)
- [x] Docker Compose (api + postgres)
- [x] Alembic migrations
- [x] Unit tests (chunker, storage, state machine)
- [x] Integration tests (upload flow, dedup, delete)
- [x] GitHub Actions CI
- [ ] pgvector embeddings (Phase 2)
- [ ] Semantic search / RAG pipeline (Phase 2–3)
- [ ] Async Celery processing (Phase 3)
- [ ] Conversations + citations (Phase 3)
- [ ] Multi-agent orchestration (Phase 4)

# Phase 1 — Document Ingestion

## 1. Mục tiêu

Phase 1 xây dựng nền tảng lưu trữ và xử lý tài liệu — **Knowledge Base Ingestion API**. Đây là bước đầu tiên trong hệ thống multi-agent RAG: không có tài liệu được parse và chunk đúng cách thì các phase sau (embedding, semantic search, citation) không thể xây dựng được.

**Đầu vào:** File PDF, TXT, hoặc Markdown từ người dùng.

**Đầu ra:** Tài liệu được lưu trên disk, text được extract và chia thành các chunk nhỏ trong DB, sẵn sàng để embed ở Phase 2.

Schema DB được thiết kế **forward-compatible** ngay từ đầu — không cần migration lớn khi Phase 2 thêm vector embedding, Phase 3 thêm Celery async, Phase 3+ thêm citation linking.

---

## 2. Yêu cầu nghiệp vụ

| # | Yêu cầu | Ghi chú |
|---|---------|---------|
| BR-01 | Upload file PDF, TXT, MD | Giới hạn 50MB/file |
| BR-02 | Tránh duplicate: cùng 1 nội dung không được lưu 2 lần | SHA-256 hash toàn bộ nội dung file |
| BR-03 | Extract text từ file, chia thành các chunk nhỏ | Chunk dựa trên token (≤512 tokens), có overlap |
| BR-04 | Mỗi chunk phải biết mình ở trang nào, offset nào trong file gốc | Dùng cho citation system Phase 3+ |
| BR-05 | Có thể lấy danh sách tài liệu, filter theo trạng thái, phân trang | List API |
| BR-06 | Xóa tài liệu không xóa cứng — phải giữ lại để citation link không bị broken | Soft delete (`deleted_at`) |
| BR-07 | Theo dõi trạng thái xử lý của từng tài liệu | State machine: PENDING → PROCESSING → PROCESSED/FAILED |
| BR-08 | Lịch sử ingestion job cho từng tài liệu | Chuẩn bị cho Celery Phase 3 |

---

## 3. Những gì cần làm

```
1. Thiết kế DB schema (3 bảng: documents, document_chunks, ingestion_jobs)
2. Viết Alembic migration
3. Xây dựng file parser với abstract class (PDF + TXT/MD, extensible)
4. Viết chunker: token-based sliding window, tính char offset và page number
5. Xây dựng storage layer: lưu file, tính SHA-256, sanitize filename
6. Viết Repository layer: tất cả SQL queries
7. Viết Service layer: orchestrate toàn bộ upload flow
8. Expose qua REST API (FastAPI router)
9. Viết unit tests (chunker, storage, state machine) + integration tests (upload flow)
10. Docker Compose: api + postgres containers
11. GitHub Actions CI
```

---

## 4. Kế hoạch triển khai

Thứ tự triển khai đi từ **trong ra ngoài** — layer nào không phụ thuộc vào layer khác thì làm trước:

```
DB Schema → ORM Models → Parsers + Chunker → Storage → Repository → Service → Router → Tests
```

### 4.1 DB Schema

Thiết kế trước, vì mọi thứ còn lại phụ thuộc vào đây.

**Nguyên tắc:**
- UUID làm primary key (không leak count, safe khi expose trong API/citation link)
- Soft delete bằng `deleted_at` thay vì DELETE thật
- `content_sha256 UNIQUE` trên `documents` để guard duplicate ở tầng DB
- `char_offset_start/end` và `page_number` trên `document_chunks` — data sẵn sàng cho citation Phase 3 dù chưa dùng
- `ingestion_jobs.task_id` nullable — NULL ở Phase 1, populate bằng Celery task ID ở Phase 3

**Bảng `documents`:**

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID PK | `gen_random_uuid()` |
| filename | TEXT NOT NULL | Tên sau khi sanitize |
| original_filename | TEXT NOT NULL | Tên gốc user upload |
| file_path | TEXT NOT NULL | Đường dẫn trên Docker volume |
| file_size | BIGINT NOT NULL | Bytes |
| mime_type | TEXT NOT NULL | `application/pdf`, `text/plain`, `text/markdown` |
| content_sha256 | TEXT UNIQUE NOT NULL | SHA-256 hash nội dung file |
| author | TEXT | Optional |
| status | document_status | PENDING \| PROCESSING \| PROCESSED \| FAILED |
| error_message | TEXT | Populate khi FAILED |
| processing_started_at | TIMESTAMPTZ | |
| processing_finished_at | TIMESTAMPTZ | |
| page_count | INT | Số trang, populate sau PROCESSED |
| chunk_count | INT | Denormalized — tránh COUNT(*) mỗi lần query |
| metadata_ | JSONB default '{}' | Tags, source_url, language, v.v. |
| deleted_at | TIMESTAMPTZ | NULL = active |
| created_at / updated_at | TIMESTAMPTZ | Auto-managed |

Indexes:
```sql
CREATE INDEX idx_documents_status ON documents (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_created_at ON documents (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata_);
```

**Bảng `document_chunks`:**

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID PK | |
| document_id | UUID FK | ON DELETE CASCADE |
| chunk_index | INT NOT NULL | 0-based, thứ tự trong document |
| page_number | INT | Trang bắt đầu (nullable với TXT không có khái niệm trang) |
| page_number_end | INT | Trang kết thúc |
| text_content | TEXT NOT NULL | Raw text của chunk |
| token_count | INT | Pre-computed, dùng cho context budgeting Phase 2+ |
| char_offset_start | INT NOT NULL | Offset ký tự trong full text — citation anchor |
| char_offset_end | INT NOT NULL | |
| content_sha256 | TEXT NOT NULL | Chunk-level dedup |
| metadata_ | JSONB default '{}' | section_title, bbox PDF, v.v. |
| created_at | TIMESTAMPTZ | |

Unique constraint: `(document_id, chunk_index)` — không được có 2 chunk cùng index trong 1 document.

**Phase 2 chỉ cần thêm 2 dòng SQL:**
```sql
ALTER TABLE document_chunks ADD COLUMN embedding vector(1536);
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

**Bảng `ingestion_jobs`:**

| Column | Type | Ghi chú |
|--------|------|---------|
| id | UUID PK | |
| document_id | UUID FK | |
| task_id | TEXT | NULL Phase 1, Celery task ID Phase 3 |
| attempt_number | INT | |
| started_at / finished_at | TIMESTAMPTZ | |
| error_detail | TEXT | Stack trace khi FAILED |

---

### 4.2 Pydantic Schemas (API I/O)

Sau khi có DB schema, định nghĩa Pydantic schemas — là "contract" giữa API và client.

**Nguyên tắc:**
- `*Create` schema: input khi tạo mới (từ user)
- `*Read` schema: output trả về client (từ DB)
- `*Update` schema: input khi cập nhật (partial update)
- `from_attributes=True` để đọc từ SQLAlchemy ORM object
- `populate_by_name=True` để handle alias (`metadata_` trong ORM → `metadata` trong JSON)

Ví dụ `DocumentRead`:
```python
class DocumentRead(BaseModel):
    id: uuid.UUID
    filename: str
    status: DocumentStatus
    chunk_count: int | None
    metadata: dict = Field(alias="metadata_", default_factory=dict)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

> **Lý do dùng alias:** SQLAlchemy `DeclarativeBase` có thuộc tính `metadata` reserved, nên column phải đặt tên `metadata_` trong ORM. Pydantic alias giúp expose nó là `metadata` trong JSON response mà không cần rename ở DB.

---

### 4.3 Parser — Abstract Class + Registry

Thiết kế để dễ mở rộng format file sau này (DOCX, HTML, v.v.) mà không sửa code cũ — áp dụng **Open/Closed Principle**.

**`BaseParser` (abstract):**
```python
class BaseParser(ABC):
    @abstractmethod
    def supported_mime_types(self) -> frozenset[str]: ...

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument: ...

    def can_parse(self, mime_type: str) -> bool:
        return mime_type in self.supported_mime_types()
```

**`ParsedDocument`** là output chuẩn mà mọi parser phải trả về:
```python
@dataclass
class ParsedPage:
    page_number: int
    text: str

@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    full_text: str       # concatenate toàn bộ pages
    page_count: int
```

**Registry pattern** (`parsers/__init__.py`):
```python
_REGISTRY: list[BaseParser] = [
    PDFParser(),
    PlainTextParser(),
    # DocxParser(),  ← thêm format mới chỉ cần append ở đây
]

def get_parser(mime_type: str) -> BaseParser:
    for parser in _REGISTRY:
        if parser.can_parse(mime_type):
            return parser
    raise UnsupportedFileTypeError(mime_type)
```

Dùng `list` thay `dict` vì một parser có thể handle nhiều MIME type (`text/plain` + `text/markdown` cùng trong `PlainTextParser`).

**Thêm format DOCX sau này:**
1. Tạo `parsers/docx.py` kế thừa `BaseParser`
2. Append `DocxParser()` vào `_REGISTRY`
3. Thêm `.docx` vào `ALLOWED_EXTENSIONS` trong `core/constants.py`

Không cần sửa bất kỳ code nào khác.

---

### 4.4 Chunker — Token-based Sliding Window

**Yêu cầu:** Mỗi chunk cần biết `char_offset_start/end` và `page_number` để làm citation anchor Phase 3+.

**Thuật toán:**
1. Tokenize toàn bộ `full_text` bằng tiktoken (`cl100k_base` — cùng tokenizer với GPT-4/Claude)
2. Slide window với `chunk_size=512` tokens, `overlap=64` tokens
3. Với mỗi window: decode tokens → lấy text, tính `char_offset_start/end` từ token-char map, tìm `page_number` từ char offset

**Token-char map:**
```python
def _build_token_char_map(encoding, full_text: str) -> list[int]:
    # token_char_map[i] = char offset của token thứ i trong full_text
    # dùng để convert token index → char offset chính xác
```

**Output `ChunkData`:**
```python
@dataclass
class ChunkData:
    chunk_index: int
    text_content: str
    token_count: int
    char_offset_start: int
    char_offset_end: int
    page_number: int | None
    page_number_end: int | None
    content_sha256: str
```

---

### 4.5 REST API Design

**Base URL:** `/api/v1`

**Nguyên tắc RESTful:**
- Resource noun trong URL, không dùng verb (`/documents` không phải `/getDocuments`)
- HTTP method thể hiện action: GET (đọc), POST (tạo), PATCH (cập nhật partial), DELETE (xóa)
- Status code có nghĩa: 200 (ok), 202 (accepted/async), 204 (no content), 400 (bad request), 404 (not found), 409 (conflict), 422 (validation error)
- Paginated list response có chuẩn: `{items: [...], total: N, page: N, page_size: N}`

**Endpoints:**

| Method | Path | Mục đích | Response |
|--------|------|---------|----------|
| POST | `/documents/check-duplicate` | Kiểm tra SHA-256 trước khi upload | `{exists: bool, document_id?: uuid}` |
| POST | `/documents` | Upload + parse + chunk | 202 `DocumentRead` |
| GET | `/documents` | List + filter + paginate | 200 `PaginatedResponse[DocumentRead]` |
| GET | `/documents/{id}` | Chi tiết 1 document | 200 `DocumentRead` |
| PATCH | `/documents/{id}` | Cập nhật author/metadata | 200 `DocumentRead` |
| PATCH | `/documents/{id}/status` | Chuyển trạng thái (internal) | 200 `DocumentRead` |
| DELETE | `/documents/{id}` | Soft delete | 204 |
| GET | `/documents/{id}/chunks` | List chunks (paginated) | 200 `PaginatedResponse[ChunkRead]` |
| GET | `/documents/{id}/chunks/{chunk_id}` | 1 chunk (citation anchor) | 200 `ChunkRead` |
| GET | `/documents/{id}/jobs` | Lịch sử ingestion job | 200 `list[JobRead]` |
| GET | `/health` | Health check | 200 \| 503 |

> **Tại sao `POST /documents` trả 202 thay vì 201?**  
> Phase 1 xử lý sync nhưng 202 (Accepted) forward-compatible với Phase 3 async — client không cần thay đổi khi chuyển sang Celery. 201 (Created) ngụ ý resource đã sẵn sàng ngay, 202 ngụ ý "đã nhận, đang xử lý".

> **Tại sao `/check-duplicate` phải đăng ký TRƯỚC `/{document_id}`?**  
> FastAPI match route theo thứ tự. Nếu `/{document_id}` đứng trước, FastAPI sẽ cố parse "check-duplicate" thành UUID → lỗi 422.

**Chuẩn output paginated list:**
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### 4.6 Ingestion Flow (end-to-end)

```
POST /documents
    │
    ▼
validate_upload()           ← kiểm tra extension, file size
    │
    ▼
save_file()                 ← lưu disk, tính SHA-256
    │
    ▼
get_by_sha256()             ← check duplicate → 409 nếu tồn tại
    │
    ▼
INSERT document (PENDING)   ← tạo record trong DB
    │
    ▼
CREATE ingestion_job        ← log job, task_id=NULL Phase 1
    │
    ▼
parse_and_chunk()           ← parser → ParsedDocument → chunker → List[ChunkData]
    │
    ▼
bulk_insert chunks          ← INSERT tất cả chunks một lần
    │
    ▼
UPDATE status → PROCESSED   ← cập nhật chunk_count, page_count
    │
    ▼
session.commit()
    │
    ▼
return DocumentRead (202)
```

**Error path:** Bất kỳ bước nào thất bại → `UPDATE status → FAILED` + lưu `error_message` → `session.rollback()` → raise exception → FastAPI exception handler trả HTTP error.

**Single transaction:** Toàn bộ flow chạy trong 1 DB session. Nếu lỗi ở bước chunking, document record không bị orphan trong DB vì session rollback.

---

### 4.7 State Machine

```
PENDING ──→ PROCESSING ──→ PROCESSED  (terminal)
   │              │
   └──→ FAILED ←──┘
         │
         └──→ PENDING  (manual retry Phase 3)
```

Transition rules được định nghĩa trong `core/constants.py`:
```python
STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PENDING":    {"PROCESSING", "FAILED"},
    "PROCESSING": {"PROCESSED", "FAILED"},
    "PROCESSED":  set(),          # terminal — không transition được
    "FAILED":     {"PENDING"},
}
```

`validate_status_transition(current, target)` trong `documents/ingestion.py` enforce rules này và raise `InvalidStatusTransitionError` nếu vi phạm.

---

### 4.8 Kiến trúc 4 tầng (Layered Architecture)

```
Router  →  Service  →  Repository  →  ORM Model
  │            │              │              │
FastAPI    Business        SQL queries    SQLAlchemy
routes       logic         (async)       + PostgreSQL
```

- **Router** chỉ nhận request, validate input, gọi service, trả response — không chứa business logic
- **Service** orchestrate use case, không biết HTTP, không viết SQL
- **Repository** là nơi duy nhất viết SQL — service chỉ gọi repository methods
- **ORM** định nghĩa schema, không chứa logic

Mỗi tầng chỉ biết tầng ngay dưới nó. Router không biết repository. Service không biết FastAPI.

---

### 4.9 Domain-First Project Structure

```
app/
├── core/              # Cross-cutting: DB engine, Base ORM, exceptions, constants
├── common/            # Shared schemas: PaginatedResponse, ErrorResponse
└── documents/         # Domain package — khép kín
    ├── models.py      # ORM: Document, DocumentChunk, IngestionJob
    ├── schemas.py     # Pydantic: DocumentRead, ChunkRead, JobRead, ...
    ├── repository.py  # SQL: DocumentRepository, ChunkRepository, JobRepository
    ├── service.py     # Use cases: upload_document, get_document, ...
    ├── ingestion.py   # State machine + parse/chunk orchestration
    ├── storage.py     # File I/O: save/delete, SHA-256
    ├── router.py      # FastAPI routes
    └── parsers/
        ├── base.py    # BaseParser ABC, ParsedDocument, ParsedPage
        ├── pdf.py     # PDFParser (PyMuPDF)
        ├── text.py    # PlainTextParser (TXT + MD)
        ├── chunker.py # chunk_document() → List[ChunkData]
        └── __init__.py # Registry + get_parser()
```

**Tại sao domain-first thay vì layer-first (`models/`, `schemas/`, `services/`)?**

Layer-first hoạt động tốt với 1 domain, nhưng khi thêm Phase 2 (`embeddings/`), Phase 3 (`retrieval/`, `conversations/`), Phase 4 (`agents/`):
- Mỗi lần thêm feature phải đụng vào nhiều folder khác nhau
- Khó xác định "code của feature X nằm ở đâu"
- Không thể delete 1 domain mà không scan toàn bộ codebase

Domain-first: mỗi domain là 1 package khép kín. Thêm `embeddings/` không đụng vào `documents/`.

---

## 5. Testing Strategy

**Unit tests** — không cần DB, không cần disk:

| Test file | Kiểm tra |
|-----------|---------|
| `test_chunker.py` | Empty doc, single chunk, sequential indices, char offset coverage, SHA-256 deterministic, page number assignment |
| `test_storage_service.py` | validate_upload accept/reject, _sanitize_filename path traversal, special chars, length truncation |
| `test_ingestion_service.py` | Valid/invalid status transitions, PROCESSED là terminal |

**Integration tests** — cần PostgreSQL test DB:

| Test file | Kiểm tra |
|-----------|---------|
| `test_documents_api.py` | Upload TXT → 202, list → có document, get → metadata đúng, delete → 204, get sau delete → 404 |
| `test_duplicate_detection.py` | Upload cùng file 2 lần → lần 2 trả 409 |

Test DB dùng real PostgreSQL (không mock) — tránh divergence giữa mock behavior và production SQL.

```bash
TEST_DATABASE_URL=postgresql+asyncpg://llm_user:llm_pass@localhost:5432/llm_notebook_test \
  pytest tests/ -v
```

---

## 6. Forward Compatibility

| Column / Feature | Phase 1 | Phase 2+ |
|-----------------|---------|---------|
| `document_chunks.char_offset_start/end` | Lưu sẵn | Citation anchor Phase 3 |
| `document_chunks.page_number` | Lưu sẵn | Citation display Phase 3 |
| `document_chunks.token_count` | Lưu sẵn | Context budgeting Phase 2 |
| `ingestion_jobs.task_id` | NULL | Celery task ID Phase 3 |
| `documents.metadata_` JSONB | `{}` | Tags, source_url, language Phase 2+ |
| `POST /documents` → 202 | Sync xử lý | Async Celery Phase 3, client không đổi |
| `documents.deleted_at` | Soft delete | Chunk FK còn tồn tại, citation không bị broken |

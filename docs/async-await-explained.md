# Async / Await — Tại sao và dùng như thế nào

## 1. Vấn đề: blocking I/O

Giả sử server nhận 3 request cùng lúc, mỗi request cần query DB mất 100ms.

**Sync (blocking):**
```
Request 1: ──[query DB 100ms]──> trả response
Request 2:                       ──[query DB 100ms]──> trả response
Request 3:                                              ──[query DB 100ms]──> trả response
Tổng thời gian: 300ms
```

Server xử lý tuần tự — trong khi chờ DB trả kết quả cho request 1, server chỉ ngồi không, không làm gì cả. Request 2 và 3 phải xếp hàng đợi.

**Async (non-blocking):**
```
Request 1: ──[gửi query]──────────────────[nhận kết quả]──> trả response
Request 2:      ──[gửi query]────────────[nhận kết quả]──> trả response
Request 3:           ──[gửi query]──────[nhận kết quả]──> trả response
Tổng thời gian: ~100ms
```

Server gửi query cho DB rồi **không ngồi chờ** — chuyển sang xử lý request 2, request 3. Khi DB trả kết quả thì quay lại tiếp tục.

---

## 2. async/await là gì

`async def` — khai báo một function là **coroutine** (có thể tạm dừng và tiếp tục).

`await` — tại điểm này, function **tạm dừng** và nhường CPU cho task khác. Khi operation hoàn thành thì tiếp tục từ đây.

```python
async def get_document(doc_id: uuid.UUID, session: AsyncSession):
    result = await session.get(Document, doc_id)  # ← tạm dừng ở đây
    # Trong lúc chờ DB, event loop xử lý request khác
    # Khi DB trả kết quả, tiếp tục từ đây
    return result
```

Không có `await` → function chạy đến cuối không dừng → blocking như sync bình thường.

---

## 3. Ai quản lý việc "nhường CPU"?

**Event loop** — một vòng lặp vô hạn chạy trong background, liên tục kiểm tra:
- Task nào đang chờ I/O xong?
- Task nào vừa có kết quả, có thể tiếp tục?

```
Event loop:
┌─────────────────────────────────────────────┐
│  Kiểm tra task queue                        │
│  → Task 1 đang chờ DB? → skip              │
│  → Task 2 DB vừa trả kết quả? → chạy tiếp │
│  → Task 3 mới vào? → bắt đầu chạy         │
│  Lặp lại...                                 │
└─────────────────────────────────────────────┘
```

FastAPI + uvicorn tự quản lý event loop — developer không cần tự tạo.

---

## 4. Async chỉ hữu ích với I/O, KHÔNG hữu ích với CPU

`await` chỉ có ý nghĩa khi operation là **I/O bound** — tức là phần lớn thời gian là chờ external system:

| Operation | Async có ích? | Lý do |
|-----------|--------------|-------|
| Query PostgreSQL | ✅ | Chờ network + DB xử lý |
| Đọc file từ disk | ✅ | Chờ disk I/O |
| Gọi external API | ✅ | Chờ network |
| Tính toán SHA-256 | ❌ | CPU liên tục làm việc, không có điểm chờ |
| Token hóa text (tiktoken) | ❌ | CPU bound |
| Parse PDF (PyMuPDF) | ❌ | CPU bound |

**Quan trọng:** Nếu `await` một operation CPU-bound, bạn vẫn block event loop — async không giúp ích gì. CPU-bound nặng cần dùng `ProcessPoolExecutor` hoặc Celery worker riêng (Phase 3).

---

## 5. Trong project này dùng như thế nào

### Repository layer — await SQL queries

```python
# documents/repository.py
async def get_by_id(self, session: AsyncSession, doc_id: uuid.UUID) -> Document | None:
    result = await session.get(Document, doc_id)  # ← chờ DB
    return result

async def bulk_insert(self, session: AsyncSession, chunks: list[DocumentChunk]) -> None:
    session.add_all(chunks)
    await session.flush()  # ← chờ DB confirm insert
```

### Service layer — await repository calls

```python
# documents/service.py
async def upload_document(..., session: AsyncSession) -> Document:
    # validate, save file (sync — CPU/disk)
    mime_type = validate_upload(filename, file_size)
    file_path, sha256 = save_file(data, filename, document_id)

    # check duplicate — await vì query DB
    existing = await doc_repo.get_by_sha256(session, sha256)
    if existing:
        raise DuplicateDocumentError()

    # insert — await vì write DB
    document = await doc_repo.create(session, ...)

    # parse + chunk — KHÔNG await vì CPU bound
    chunks, page_count = parse_and_chunk(file_path, mime_type)

    # bulk insert chunks — await vì write DB
    await chunk_repo.bulk_insert(session, chunk_models)

    await session.commit()  # ← await vì I/O
    return document
```

### Router layer — async def để FastAPI quản lý

```python
# documents/router.py
@router.post("/documents")
async def upload_document_endpoint(
    file: UploadFile,
    session: AsyncSession = Depends(get_db),
):
    data = await file.read()  # ← chờ đọc file từ HTTP request
    result = await service.upload_document(data, ...)  # ← chờ service
    return result
```

---

## 6. Quy tắc khi viết async trong project này

**1. Function nào gọi `await` bên trong thì phải là `async def`:**
```python
# ❌ Sai — gọi await trong sync function
def get_doc(session, doc_id):
    return await session.get(Document, doc_id)  # SyntaxError

# ✅ Đúng
async def get_doc(session, doc_id):
    return await session.get(Document, doc_id)
```

**2. `async def` phải được `await` khi gọi:**
```python
# ❌ Sai — không await, trả về coroutine object, không chạy gì cả
result = get_doc(session, doc_id)

# ✅ Đúng
result = await get_doc(session, doc_id)
```

**3. Không `await` operation sync:**
```python
# ❌ Sai — validate_upload là sync function (không có await bên trong)
mime_type = await validate_upload(filename, size)

# ✅ Đúng
mime_type = validate_upload(filename, size)
```

**4. Async "lây" từ dưới lên trên** — nếu repository là async, service gọi nó phải async, router gọi service phải async. Không thể gọi async từ sync function bình thường.

---

## 7. Tóm tắt

| Khái niệm | Ý nghĩa thực tế |
|-----------|----------------|
| `async def` | Function có thể tạm dừng ở điểm `await` |
| `await` | Tạm dừng, nhường CPU cho task khác, tiếp tục khi có kết quả |
| Event loop | Bộ điều phối — quyết định task nào chạy tiếp |
| Async hữu ích khi | Chờ DB, chờ network, chờ disk |
| Async vô ích khi | CPU đang tính toán liên tục (parse, tokenize, hash) |
| asyncpg | PostgreSQL driver hỗ trợ async — bắt buộc để `await session.get()` hoạt động |

**Một process, một thread, nhiều request xử lý đồng thời** — đây là mô hình của FastAPI + asyncpg. Khác với cách truyền thống dùng multi-thread (mỗi request 1 thread), async dùng 1 thread nhưng không bao giờ ngồi chờ I/O.

"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TYPE document_status AS ENUM ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')
    """))

    op.execute(sa.text("""
        CREATE TABLE documents (
            id              UUID PRIMARY KEY,
            filename        TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path       TEXT NOT NULL,
            file_size       BIGINT NOT NULL,
            mime_type       TEXT NOT NULL,
            content_sha256  TEXT NOT NULL UNIQUE,
            author          TEXT,
            status          document_status NOT NULL DEFAULT 'PENDING',
            error_message   TEXT,
            processing_started_at  TIMESTAMPTZ,
            processing_finished_at TIMESTAMPTZ,
            page_count      INTEGER,
            chunk_count     INTEGER,
            metadata        JSONB NOT NULL DEFAULT '{}',
            deleted_at      TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(sa.text("CREATE INDEX idx_documents_content_sha256 ON documents (content_sha256)"))
    op.execute(sa.text("CREATE INDEX idx_documents_status ON documents (status) WHERE deleted_at IS NULL"))
    op.execute(sa.text("CREATE INDEX idx_documents_created_at ON documents (created_at DESC) WHERE deleted_at IS NULL"))
    op.execute(sa.text("CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata)"))

    op.execute(sa.text("""
        CREATE TABLE document_chunks (
            id                  UUID PRIMARY KEY,
            document_id         UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index         INTEGER NOT NULL,
            page_number         INTEGER,
            page_number_end     INTEGER,
            text_content        TEXT NOT NULL,
            token_count         INTEGER,
            char_offset_start   INTEGER NOT NULL,
            char_offset_end     INTEGER NOT NULL,
            content_sha256      TEXT NOT NULL,
            metadata            JSONB NOT NULL DEFAULT '{}',
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_chunk_document_index UNIQUE (document_id, chunk_index)
        )
    """))

    op.execute(sa.text("CREATE INDEX idx_chunks_document_id ON document_chunks (document_id)"))
    op.execute(sa.text("CREATE INDEX idx_chunks_page_number ON document_chunks (document_id, page_number)"))
    op.execute(sa.text("CREATE INDEX idx_chunks_char_offsets ON document_chunks (document_id, char_offset_start, char_offset_end)"))
    op.execute(sa.text("CREATE INDEX idx_chunks_metadata ON document_chunks USING GIN (metadata)"))

    op.execute(sa.text("""
        CREATE TABLE ingestion_jobs (
            id              UUID PRIMARY KEY,
            document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            task_id         TEXT,
            attempt_number  INTEGER NOT NULL DEFAULT 1,
            started_at      TIMESTAMPTZ,
            finished_at     TIMESTAMPTZ,
            error_detail    TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(sa.text("CREATE INDEX idx_jobs_document_id ON ingestion_jobs (document_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS ingestion_jobs"))
    op.execute(sa.text("DROP TABLE IF EXISTS document_chunks"))
    op.execute(sa.text("DROP TABLE IF EXISTS documents"))
    op.execute(sa.text("DROP TYPE IF EXISTS document_status"))

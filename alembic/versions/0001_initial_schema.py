"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE document_status AS ENUM ('PENDING', 'PROCESSING', 'PROCESSED', 'FAILED')")

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("original_filename", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False),
        sa.Column("mime_type", sa.Text, nullable=False),
        sa.Column("content_sha256", sa.Text, nullable=False, unique=True),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "PROCESSED", "FAILED", name="document_status"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("idx_documents_content_sha256", "documents", ["content_sha256"])
    op.create_index(
        "idx_documents_status",
        "documents",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_documents_created_at",
        "documents",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_documents_metadata",
        "documents",
        ["metadata"],
        postgresql_using="gin",
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("page_number_end", sa.Integer, nullable=True),
        sa.Column("text_content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("char_offset_start", sa.Integer, nullable=False),
        sa.Column("char_offset_end", sa.Integer, nullable=False),
        sa.Column("content_sha256", sa.Text, nullable=False),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_document_index"),
    )

    op.create_index("idx_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("idx_chunks_page_number", "document_chunks", ["document_id", "page_number"])
    op.create_index("idx_chunks_char_offsets", "document_chunks", ["document_id", "char_offset_start", "char_offset_end"])
    op.create_index("idx_chunks_metadata", "document_chunks", ["metadata"], postgresql_using="gin")

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.Text, nullable=True),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("idx_jobs_document_id", "ingestion_jobs", ["document_id"])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.execute("DROP TYPE document_status")

"""add offline embedding column to document_chunks

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding_offline vector(768)")
    op.execute(
        "CREATE INDEX idx_chunks_embedding_offline ON document_chunks "
        "USING hnsw (embedding_offline vector_cosine_ops) "
        "WHERE embedding_offline IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_offline")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_offline")

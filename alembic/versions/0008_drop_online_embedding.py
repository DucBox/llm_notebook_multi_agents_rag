"""drop online embedding, rename embedding_offline to embedding

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-22
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old HNSW index on online embedding before dropping the column
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")

    # Rename offline → canonical
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_offline")
    op.execute("ALTER TABLE document_chunks RENAME COLUMN embedding_offline TO embedding")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding")
    op.execute("ALTER TABLE document_chunks RENAME COLUMN embedding TO embedding_offline")
    op.execute(
        "CREATE INDEX idx_chunks_embedding_offline ON document_chunks "
        "USING hnsw (embedding_offline vector_cosine_ops) "
        "WHERE embedding_offline IS NOT NULL"
    )
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")

"""add user_id to documents

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable UUID — no FK yet, users table does not exist.
    # FK will be added in a later migration when the users table is introduced.
    op.execute(sa.text("ALTER TABLE documents ADD COLUMN user_id UUID"))
    op.execute(sa.text(
        "CREATE INDEX idx_documents_user_id ON documents (user_id) WHERE deleted_at IS NULL"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_documents_user_id"))
    op.execute(sa.text("ALTER TABLE documents DROP COLUMN IF EXISTS user_id"))

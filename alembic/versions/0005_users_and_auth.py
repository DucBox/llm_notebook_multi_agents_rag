"""users table and auth: per-user SHA256 dedup + FK constraints

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Users table
    op.execute(sa.text("""
        CREATE TABLE users (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email        VARCHAR(255) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE INDEX idx_users_email ON users (email)"))

    # 2. Add FK from documents.user_id → users.id
    op.execute(sa.text(
        "ALTER TABLE documents ADD CONSTRAINT fk_documents_user_id "
        "FOREIGN KEY (user_id) REFERENCES users(id)"
    ))

    # 3. Add user_id to conversations (already has column from migration 0004)
    #    Add FK from conversations.user_id → users.id
    op.execute(sa.text(
        "ALTER TABLE conversations ADD CONSTRAINT fk_conversations_user_id "
        "FOREIGN KEY (user_id) REFERENCES users(id)"
    ))

    # 4. Per-user SHA256 dedup: drop global unique, create composite unique
    op.execute(sa.text("ALTER TABLE documents DROP CONSTRAINT documents_content_sha256_key"))
    op.execute(sa.text(
        "CREATE UNIQUE INDEX idx_documents_sha256_user "
        "ON documents (content_sha256, user_id) WHERE deleted_at IS NULL"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS idx_documents_sha256_user"))
    op.execute(sa.text(
        "ALTER TABLE documents ADD CONSTRAINT documents_content_sha256_key "
        "UNIQUE (content_sha256)"
    ))
    op.execute(sa.text(
        "ALTER TABLE conversations DROP CONSTRAINT IF EXISTS fk_conversations_user_id"
    ))
    op.execute(sa.text(
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS fk_documents_user_id"
    ))
    op.execute(sa.text("DROP INDEX IF EXISTS idx_users_email"))
    op.execute(sa.text("DROP TABLE IF EXISTS users"))

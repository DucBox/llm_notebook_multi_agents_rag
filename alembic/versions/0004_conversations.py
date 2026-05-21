"""add conversations and messages tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            total_token_count INT NOT NULL DEFAULT 0,
            compacted_history TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX idx_conversations_user_id ON conversations (user_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_conversations_status ON conversations (status)"
    ))

    op.execute(sa.text("""
        CREATE TABLE messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            token_count INT NOT NULL DEFAULT 0,
            is_compacted BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX idx_messages_conversation_id ON messages (conversation_id, created_at)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_messages_active ON messages (conversation_id) WHERE is_compacted = FALSE"
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS messages"))
    op.execute(sa.text("DROP TABLE IF EXISTS conversations"))

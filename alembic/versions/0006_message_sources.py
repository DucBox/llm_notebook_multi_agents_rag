"""add sources column to messages

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("sources", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "sources")

"""add translate_workers to translation_settings

Revision ID: 008
Revises: 007
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "translation_settings",
        sa.Column("translate_workers", sa.Integer(), nullable=False, server_default="10"),
    )
    # Update existing rows that still have the default (set explicitly to 10)
    op.execute("UPDATE translation_settings SET translate_workers = 10")


def downgrade() -> None:
    op.drop_column("translation_settings", "translate_workers")

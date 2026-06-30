"""drop legacy processed_files and sync_state tables

Revision ID: 004
Revises: 003
Create Date: 2026-06-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("processed_files")
    op.drop_table("sync_state")


def downgrade() -> None:
    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scan_triggered", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "processed_files",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("dest_path", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["folder_id"], ["watched_folders.id"]),
        sa.UniqueConstraint("owner_id", "source_path", "content_hash", name="uq_owner_path_hash"),
    )

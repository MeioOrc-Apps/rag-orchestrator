"""Update chunk_size/chunk_overlap defaults from chars to words (1000→300, 100→30).

Revision ID: 009
Revises: 008
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("pipeline_settings", "chunk_size", server_default="500")
    op.alter_column("pipeline_settings", "chunk_overlap", server_default="50")
    op.execute(
        """
        UPDATE pipeline_settings
        SET chunk_size = 500, chunk_overlap = 50
        WHERE chunk_size IN (1000, 300) AND chunk_overlap IN (100, 30)
        """
    )


def downgrade():
    op.alter_column("pipeline_settings", "chunk_size", server_default="1000")
    op.alter_column("pipeline_settings", "chunk_overlap", server_default="100")
    op.execute(
        """
        UPDATE pipeline_settings
        SET chunk_size = 1000, chunk_overlap = 100
        WHERE chunk_size = 500 AND chunk_overlap = 50
        """
    )

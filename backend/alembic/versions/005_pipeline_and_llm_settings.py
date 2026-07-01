"""pipeline_settings table and enrichment_model in translation_settings

Revision ID: 005
Revises: 004
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add enrichment_model to translation_settings
    op.add_column(
        "translation_settings",
        sa.Column("enrichment_model", sa.Text(), nullable=False, server_default=""),
    )

    # Update seed row: disable translation by default, clear model
    op.execute(
        """
        UPDATE translation_settings
        SET enabled = false, model = '', enrichment_model = ''
        WHERE id = 1
        """
    )

    # Create pipeline_settings singleton table
    op.create_table(
        "pipeline_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("parse_batch_size", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_translation_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute(
        """
        INSERT INTO pipeline_settings (chunk_size, chunk_overlap, parse_batch_size, max_translation_retries, updated_at)
        SELECT 1000, 100, 20, 3, now()
        WHERE NOT EXISTS (SELECT 1 FROM pipeline_settings)
        """
    )


def downgrade() -> None:
    op.drop_table("pipeline_settings")
    op.drop_column("translation_settings", "enrichment_model")
    op.execute(
        """
        UPDATE translation_settings
        SET enabled = true, model = 'local:qwen2.5:7b'
        WHERE id = 1
        """
    )

"""Increase default translation batch_size from 5 to 200

Revision ID: 007
Revises: 006
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "translation_settings", "batch_size",
        server_default="200",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.execute("UPDATE translation_settings SET batch_size = 200 WHERE batch_size = 5")


def downgrade() -> None:
    op.alter_column(
        "translation_settings", "batch_size",
        server_default="5",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.execute("UPDATE translation_settings SET batch_size = 5 WHERE batch_size = 200")

"""Split prompt_template into prompt_template_en, prompt_template_pt, prompt_enrichment

Revision ID: 006
Revises: 005
Create Date: 2026-07-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_PROMPT_EN = (
    "Translate the following text to English. "
    "Output only the translation, no preamble:\n\n{text}"
)
_DEFAULT_PROMPT_PT = (
    "Translate the following text to Portuguese (Brazil). "
    "Output only the translation, no preamble:\n\n{text}"
)
_DEFAULT_PROMPT_ENRICHMENT = (
    "Expand this search query with synonyms and related terms for better retrieval. "
    "Output only the expanded query, no explanation:\n\n{text}"
)


def upgrade() -> None:
    # Rename existing column → prompt_template_en
    op.alter_column("translation_settings", "prompt_template", new_column_name="prompt_template_en")

    # Add prompt_template_pt
    op.add_column(
        "translation_settings",
        sa.Column("prompt_template_pt", sa.Text(), nullable=False, server_default=_DEFAULT_PROMPT_PT),
    )

    # Add prompt_enrichment
    op.add_column(
        "translation_settings",
        sa.Column("prompt_enrichment", sa.Text(), nullable=False, server_default=_DEFAULT_PROMPT_ENRICHMENT),
    )

    # Seed defaults into the existing row
    op.execute(
        f"""
        UPDATE translation_settings
        SET
            prompt_template_en = '{_DEFAULT_PROMPT_EN}',
            prompt_template_pt = '{_DEFAULT_PROMPT_PT}',
            prompt_enrichment = '{_DEFAULT_PROMPT_ENRICHMENT}'
        WHERE id = 1
        """
    )


def downgrade() -> None:
    op.drop_column("translation_settings", "prompt_enrichment")
    op.drop_column("translation_settings", "prompt_template_pt")
    op.alter_column("translation_settings", "prompt_template_en", new_column_name="prompt_template")

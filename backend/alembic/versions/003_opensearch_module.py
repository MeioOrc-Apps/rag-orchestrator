"""opensearch module — add files, chunks, translation_settings, search_query_log

Revision ID: 003
Revises: 002
Create Date: 2026-06-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # files — source of truth for OpenSearch-indexed files
    op.create_table(
        "files",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    op.create_index("idx_files_parse_status", "files", ["parse_status"])
    op.create_index("idx_files_domain", "files", ["domain"])
    op.create_index("idx_files_hash", "files", ["file_hash"])

    # chunks — unit of indexation
    op.create_table(
        "chunks",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_original", sa.Text(), nullable=False),
        sa.Column("source_language", sa.Text(), nullable=False),
        sa.Column("content_pt", sa.Text(), nullable=True),
        sa.Column("content_en", sa.Text(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("translation_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("translation_error", sa.Text(), nullable=True),
        sa.Column("translation_model", sa.Text(), nullable=True),
        sa.Column("translated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("opensearch_id", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_chunk_file_index"),
    )
    op.create_index("idx_chunks_file_id", "chunks", ["file_id"])
    op.create_index("idx_chunks_translation_status", "chunks", ["translation_status"])
    op.create_index("idx_chunks_index_status", "chunks", ["index_status"])

    # translation_settings — LLM model/prompt config
    op.create_table(
        "translation_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("target_language", sa.Text(), nullable=False, server_default="en"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # search_query_log — search audit log
    op.create_table(
        "search_query_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_original", sa.Text(), nullable=False),
        sa.Column("query_enriched", sa.Text(), nullable=True),
        sa.Column("domain_filter", sa.Text(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=True),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("enrichment_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_query_log_created", "search_query_log", ["created_at"])

    # Seed default translation settings (idempotent)
    op.execute(
        sa.text(
            """
            INSERT INTO translation_settings (model, prompt_template, target_language, batch_size, enabled, updated_at)
            SELECT 'local:qwen2.5:7b',
                   'Translate the following text to English. Output only the translation, no preamble:\n\n{text}',
                   'en', 5, true, now()
            WHERE NOT EXISTS (SELECT 1 FROM translation_settings)
            """
        )
    )


def downgrade() -> None:
    op.drop_index("idx_query_log_created", table_name="search_query_log")
    op.drop_table("search_query_log")
    op.drop_table("translation_settings")
    op.drop_index("idx_chunks_index_status", table_name="chunks")
    op.drop_index("idx_chunks_translation_status", table_name="chunks")
    op.drop_index("idx_chunks_file_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("idx_files_hash", table_name="files")
    op.drop_index("idx_files_domain", table_name="files")
    op.drop_index("idx_files_parse_status", table_name="files")
    op.drop_table("files")

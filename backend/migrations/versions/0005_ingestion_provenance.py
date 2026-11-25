"""Source provenance and durable reindex state; existing chunks remain usable."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("content_hash", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("pending_file_path", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("pending_content_hash", sa.String(64), nullable=True))
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.add_column(
        "documents",
        sa.Column("extraction_warnings", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "documents", sa.Column("index_metadata", sa.JSON(), nullable=False, server_default="{}")
    )
    op.add_column(
        "documents",
        sa.Column("index_status", sa.String(20), nullable=False, server_default="ready"),
    )
    op.add_column("documents", sa.Column("index_error", sa.Text(), nullable=True))
    op.add_column(
        "documents", sa.Column("index_started_at", sa.DateTime(timezone=True), nullable=True)
    )
    for name in ("page_start", "page_end", "start_offset", "end_offset"):
        op.add_column("document_chunks", sa.Column(name, sa.Integer(), nullable=True))
    for name in ("section", "section_key"):
        op.add_column("document_chunks", sa.Column(name, sa.Text(), nullable=True))


def downgrade():
    for name in ("section_key", "section", "end_offset", "start_offset", "page_end", "page_start"):
        op.drop_column("document_chunks", name)
    for name in (
        "index_started_at",
        "index_error",
        "index_status",
        "index_metadata",
        "extraction_warnings",
    ):
        op.drop_column("documents", name)
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_column("documents", "pending_content_hash")
    op.drop_column("documents", "pending_file_path")
    op.drop_column("documents", "content_hash")

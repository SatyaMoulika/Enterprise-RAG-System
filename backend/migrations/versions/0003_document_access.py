"""Employee document access; preserve existing documents as company-wide."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "documents",
        sa.Column("visibility", sa.String(20), server_default="company", nullable=False),
    )
    op.create_table(
        "document_grants",
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
    )


def downgrade():
    op.drop_table("document_grants")
    op.drop_column("documents", "visibility")

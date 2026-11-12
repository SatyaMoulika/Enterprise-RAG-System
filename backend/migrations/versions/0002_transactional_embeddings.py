"""Keep vectors and their model identity in the same transaction as document chunks."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("document_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
    op.add_column("document_chunks", sa.Column("embedding_model", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("document_chunks", "embedding_model")
    op.drop_column("document_chunks", "embedding")

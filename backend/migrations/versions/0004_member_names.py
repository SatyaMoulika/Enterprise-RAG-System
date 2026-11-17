"""Optional member display names; existing accounts keep email fallback."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("name", sa.String(120), nullable=False, server_default=""))


def downgrade():
    op.drop_column("users", "name")

"""Establish the migration lineage without introducing business tables.

Alembic creates its own version table. Future table changes require revisions;
app startup must never call metadata.create_all().
"""

revision: str = "0001_persistence_foundation"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""Create seller-scoped Meta connection metadata without credential plaintext."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_create_meta_connections"
down_revision = "0001_persistence_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_connections",
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("external_user_id", sa.String(255)),
        sa.Column("credential_reference", sa.String(512), unique=True),
        sa.Column("oauth_state_digest", sa.String(64), unique=True),
        sa.Column("oauth_state_expires_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_meta_connections_seller_id", "meta_connections", ["seller_id"])
    op.create_table(
        "meta_ad_account_links",
        sa.Column("link_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("meta_connections.connection_id"),
            nullable=False,
        ),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_account_id", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("seller_id", "external_account_id", name="seller_meta_account"),
    )
    op.create_index("ix_meta_ad_account_links_seller_id", "meta_ad_account_links", ["seller_id"])


def downgrade() -> None:
    op.drop_table("meta_ad_account_links")
    op.drop_table("meta_connections")

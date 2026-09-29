"""Persistent seller-scoped Meta connection metadata; never token plaintext.

PURPOSE: define connection and ad-account-link tables.
RESPONSIBILITY: persist safe metadata and credential references only.
DEPENDENCIES: SQLAlchemy and shared database metadata.
USED BY: Meta connection repository.
TESTED BY: tests/integration/meta/test_meta_connection_repository.py.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from marketing_ai.infrastructure.database.base import Base


class MetaConnectionModel(Base):
    __tablename__ = "meta_connections"
    connection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    seller_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    external_user_id: Mapped[str | None] = mapped_column(String(255))
    credential_reference: Mapped[str | None] = mapped_column(String(512), unique=True)
    oauth_state_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    oauth_state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ad_accounts: Mapped[list["MetaAdAccountLinkModel"]] = relationship(cascade="all, delete-orphan")


class MetaAdAccountLinkModel(Base):
    __tablename__ = "meta_ad_account_links"
    __table_args__ = (
        UniqueConstraint("seller_id", "external_account_id", name="seller_meta_account"),
    )
    link_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("meta_connections.connection_id"), nullable=False
    )
    seller_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

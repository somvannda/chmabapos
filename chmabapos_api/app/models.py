from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    platform_role: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    memberships: Mapped[list[Membership]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    """A server-side sign-in session that backs the rotating refresh token.

    The access token only carries this row's id (``sid``); presenting a session
    id that is missing, expired or revoked fails authentication, which is what
    makes logout and remote revocation take effect immediately. Only the hash of
    the refresh token is stored, never the token itself.
    """

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # The hash the previous rotation replaced. A presented token that matches
    # this (instead of the current one) is a replay: the session is revoked.
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remember: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(180))
    country: Mapped[str] = mapped_column(String(80), default="Cambodia")
    vertical: Mapped[str] = mapped_column(String(20), default="general")
    tax_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), default="USD")
    aba_payway_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aba_payway_status: Mapped[str] = mapped_column(String(20), default="none")
    chamabapay_store_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Company-wide settings bag (approval policy and future controls).
    settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    stores: Mapped[list[Store]] = relationship(back_populates="company", cascade="all, delete-orphan")
    memberships: Mapped[list[Membership]] = relationship(back_populates="company", cascade="all, delete-orphan")
    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="company", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_log_created", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalRequest(Base):
    """A held action waiting for an owner or manager to approve it (Phase 2)."""

    __tablename__ = "approval_requests"
    __table_args__ = (Index("ix_approval_request_company_status", "company_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Everything needed to execute the action once it is approved.
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_store_company_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Phnom_Penh")
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), default="USD")
    service_tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10.00"))
    preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    aba_payway_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    aba_payway_status: Mapped[str] = mapped_column(String(20), default="none")
    chamabapay_store_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Online ordering / QR-at-table: opt in and get a revocable public token.
    public_order_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    public_order_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    company: Mapped[Company] = relationship(back_populates="stores")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_membership_company_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="cashier")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="memberships")
    company: Mapped[Company] = relationship(back_populates="memberships")


class MembershipStore(Base):
    __tablename__ = "membership_stores"

    membership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"), primary_key=True)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    symbol: Mapped[str] = mapped_column(String(8))
    decimal_places: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CompanyCurrency(Base):
    __tablename__ = "company_currencies"

    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code", ondelete="CASCADE"), primary_key=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("company_id", "base_currency_code", "quote_currency_code", "effective_from", name="uq_exchange_rate_effective"),
        Index("ix_exchange_rate_lookup", "company_id", "base_currency_code", "quote_currency_code", "effective_from"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    base_currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    quote_currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    max_stores: Mapped[int] = mapped_column(Integer)
    max_members: Mapped[int] = mapped_column(Integer)
    transaction_limit: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscription_company_status", "company_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(20), ForeignKey("plans.code"))
    billing_cycle: Mapped[str] = mapped_column(String(20), default="monthly")
    status: Mapped[str] = mapped_column(String(20), default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_plan_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scheduled_store_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    scheduled_member_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    paused_store_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    paused_member_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="subscriptions")
    plan: Mapped[Plan] = relationship()


class BillingReminder(Base):
    __tablename__ = "billing_reminders"
    __table_args__ = (UniqueConstraint("subscription_id", "days_before", name="uq_billing_reminder_subscription_days"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    days_before: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("company_id", "parent_id", "name", name="uq_category_company_parent_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    parent: Mapped[Category | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Category]] = relationship(back_populates="parent", cascade="all")


class DiningArea(Base):
    """A named zone of a store's floor plan (Ground floor, Terrace, ...)."""

    __tablename__ = "dining_areas"
    __table_args__ = (UniqueConstraint("store_id", "name", name="uq_dining_area_store_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DiningTable(Base):
    """A physical table on the floor. ``status`` is denormalised for a fast floor
    render; whether the table is actually busy is owned by its open ticket (later
    phase)."""

    __tablename__ = "dining_tables"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uq_dining_table_store_name"),
        Index("ix_dining_table_area", "area_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    area_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dining_areas.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(40))
    seats: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(20), default="available")
    # Per-table token for the QR-at-table flow (nullable until generated).
    qr_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customer_company_created", "company_id", "created_at"), Index("ix_customer_company_phone", "company_id", "phone"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    points: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_product_company_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(180))
    sku: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), default="each")
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=True)
    track_serials: Mapped[bool] = mapped_column(Boolean, default=False)
    # Seeded demo rows created when a workspace is first set up so a merchant can
    # try a sale before entering their own catalogue. Excluded from "added a
    # product" counts (checklist, funnel) and never treated as a real item.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    modifier_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("modifier_groups.id", ondelete="SET NULL"), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    category: Mapped[Category | None] = relationship()


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"

    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    reorder_point: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movement_store_created", "store_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    movement_type: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Per-unit cost basis for the movement. Set on costed inflows (restock,
    # opening balance, purchase receipt, transfer-in) so COGS can be frozen
    # onto the sale line instead of being re-derived from mutable catalog cost.
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductOption(Base):
    __tablename__ = "product_options"
    __table_args__ = (UniqueConstraint("product_id", "name", name="uq_product_option_product_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    values: Mapped[list[ProductOptionValue]] = relationship(back_populates="option", cascade="all, delete-orphan")


class ProductOptionValue(Base):
    __tablename__ = "product_option_values"
    __table_args__ = (UniqueConstraint("option_id", "value", name="uq_product_option_value"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    option_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_options.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer, default=0)

    option: Mapped[ProductOption] = relationship(back_populates="values")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("product_id", "sku", name="uq_variant_product_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(80))
    barcode: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(180))
    # Optional per-variant image; falls back to the parent product image in the UI.
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VariantInventoryBalance(Base):
    __tablename__ = "variant_inventory_balances"

    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True)
    on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    reorder_point: Mapped[int] = mapped_column(Integer, default=10)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProductSerial(Base):
    __tablename__ = "product_serials"
    __table_args__ = (
        UniqueConstraint("company_id", "serial_number", name="uq_serial_company_number"),
        Index("ix_product_serial_product", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(120))
    imei: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_stock")
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Warranty the supplier gives the company; the clock starts when the unit is
    # received into stock.
    supplier_warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_warranty_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Warranty the shop promises the customer; the clock only starts when the
    # unit is actually sold (``sold_at``).
    customer_warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_warranty_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Per-unit condition for used / refurbished electronics. All nullable: serials
    # that pre-date this field, and non-electronics verticals, stay unassessed.
    condition_grade: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    battery_health: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battery_cycle_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TradeIn(Base):
    """A customer device accepted into stock (docs/trade-in-plan.md).

    A trade-in is stock intake plus a credit: the device becomes a graded
    ``ProductSerial`` stocked at ``assessed_value``, and that value is applied to
    a sale as a ``trade_in`` tender.
    """

    __tablename__ = "trade_ins"
    __table_args__ = (Index("ix_trade_in_store_created", "store_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"))
    serial_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_serials.id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(120))
    imei: Mapped[str | None] = mapped_column(String(40), nullable=True)
    condition_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    battery_health: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    assessed_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    kind: Mapped[str] = mapped_column(String(20), default="trade_in")
    status: Mapped[str] = mapped_column(String(20), default="accepted")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SerialConditionHistory(Base):
    """Append-only log of a unit's condition assessments.

    The current assessment is denormalised onto ``ProductSerial`` for fast reads;
    this table is the audit trail so a unit can be re-graded (e.g. after a
    battery swap) without losing its prior condition.
    """

    __tablename__ = "serial_condition_history"
    __table_args__ = (Index("ix_serial_condition_serial_graded", "serial_id", "graded_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    serial_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_serials.id", ondelete="CASCADE"), index=True)
    condition_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    battery_health: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battery_cycle_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    condition_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SerialServiceTicket(Base):
    __tablename__ = "serial_service_tickets"
    __table_args__ = (Index("ix_serial_ticket_serial_created", "serial_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    serial_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_serials.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    ticket_type: Mapped[str] = mapped_column(String(20), default="repair")
    status: Mapped[str] = mapped_column(String(20), default="open")
    summary: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WarrantyClaim(Base):
    """A formal warranty claim on a sold serial (docs/warranty-claim-plan.md).

    Hangs off one ``ProductSerial`` and runs an explicit state machine; the
    append-only ``WarrantyClaimEvent`` log records every transition.
    """

    __tablename__ = "warranty_claims"
    __table_args__ = (Index("ix_warranty_claim_store_created", "store_id", "claimed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    claim_number: Mapped[str] = mapped_column(String(32))
    serial_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_serials.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    order_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issue: Mapped[str] = mapped_column(String(180))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    replacement_serial_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_serials.id", ondelete="SET NULL"), nullable=True)
    refund_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("refunds.id", ondelete="SET NULL"), nullable=True)
    service_ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("serial_service_tickets.id", ondelete="SET NULL"), nullable=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    events: Mapped[list[WarrantyClaimEvent]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class WarrantyClaimEvent(Base):
    __tablename__ = "warranty_claim_events"
    __table_args__ = (Index("ix_warranty_claim_event_claim_created", "claim_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warranty_claims.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    claim: Mapped[WarrantyClaim] = relationship(back_populates="events")


class ModifierGroup(Base):
    __tablename__ = "modifier_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    min_select: Mapped[int] = mapped_column(Integer, default=0)
    max_select: Mapped[int] = mapped_column(Integer, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    modifiers: Mapped[list[Modifier]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Modifier(Base):
    __tablename__ = "modifiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("modifier_groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    price_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    ingredient_product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    group: Mapped[ModifierGroup] = relationship(back_populates="modifiers")


class Combo(Base):
    """A named bundle of products sold for a single price (see docs/combos-plan.md).

    A combo is logical, not stocked: selling one deducts each component's
    inventory (like a recipe), never a combo balance.
    """

    __tablename__ = "combos"
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_combo_company_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list[ComboItem]] = relationship(back_populates="combo", cascade="all, delete-orphan")
    groups: Mapped[list[ComboGroup]] = relationship(back_populates="combo", cascade="all, delete-orphan")


class ComboItem(Base):
    __tablename__ = "combo_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    combo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("combos.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("1"))
    position: Mapped[int] = mapped_column(Integer, default=0)

    combo: Mapped[Combo] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()


class ComboGroup(Base):
    """A choose-from-a-set group on a combo (docs/combos-choice-plan.md)."""

    __tablename__ = "combo_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    combo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("combos.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    min_select: Mapped[int] = mapped_column(Integer, default=1)
    max_select: Mapped[int] = mapped_column(Integer, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    combo: Mapped[Combo] = relationship(back_populates="groups")
    options: Mapped[list[ComboGroupOption]] = relationship(back_populates="group", cascade="all, delete-orphan")


class ComboGroupOption(Base):
    __tablename__ = "combo_group_options"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("combo_groups.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    position: Mapped[int] = mapped_column(Integer, default=0)

    group: Mapped[ComboGroup] = relationship(back_populates="options")
    product: Mapped[Product] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()


class ProductBatch(Base):
    __tablename__ = "product_batches"
    __table_args__ = (Index("ix_product_batch_product_expiry", "product_id", "expiry_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True)
    batch_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0"))
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StoreSequence(Base):
    """Per-store document counters (sales orders, purchase orders, ...).

    Numbers are unique per store, so each branch gets a tidy contiguous run
    (e.g. CHM-000042) even though the same prefix exists at another store.
    """

    __tablename__ = "store_sequences"

    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)
    scope: Mapped[str] = mapped_column(String(20), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_order_store_created", "store_id", "created_at"), UniqueConstraint("store_id", "order_number", name="uq_order_store_number"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True)
    order_number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(25), default="payment_pending")
    customer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tip: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    # How the sale was fulfilled: dine_in | takeaway | delivery. Defaults to
    # takeaway so existing "pay and go" orders are unchanged.
    order_type: Mapped[str] = mapped_column(String(20), default="takeaway", server_default="takeaway")
    # The table a dine-in sale was served at, snapshotted so reports and
    # receipts survive a table rename or delete.
    table_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dining_tables.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped[Customer | None] = relationship()
    items: Mapped[list[OrderItem]] = relationship(back_populates="order", cascade="all, delete-orphan")
    payments: Mapped[list[Payment]] = relationship(back_populates="order", cascade="all, delete-orphan")
    tenders: Mapped[list[OrderTender]] = relationship(back_populates="order", cascade="all, delete-orphan")
    refunds: Mapped[list[Refund]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"))
    product_name: Mapped[str] = mapped_column(String(180))
    sku: Mapped[str] = mapped_column(String(80))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=True)
    variant_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    modifiers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    # Per-unit cost frozen when the sale is fulfilled, so reports keep the
    # historical margin even if the catalog cost_price is edited later.
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Cosmetic grade of the sold unit(s), snapshotted at fulfilment so receipts
    # and margin-by-grade reporting stay stable if the serial is later re-graded.
    condition_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # When this line is a combo, product_id points at the lead component and the
    # bundle's identity/components are snapshotted here. ``combo_components`` is
    # used to deplete and restore each component's stock.
    combo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("combos.id", ondelete="SET NULL"), nullable=True, index=True)
    combo_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    combo_components: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Dine-in routing, snapshotted at fulfilment: which seat ordered the line and
    # which course it belongs to. Null for retail/takeaway lines.
    seat: Mapped[int | None] = mapped_column(Integer, nullable=True)
    course: Mapped[str | None] = mapped_column(String(40), nullable=True)

    order: Mapped[Order] = relationship(back_populates="items")
    serials: Mapped[list["ProductSerial"]] = relationship(viewonly=True, lazy="selectin")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (Index("ix_payment_external_id", "provider", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qr_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="payments")


class OrderTender(Base):
    __tablename__ = "order_tenders"
    __table_args__ = (Index("ix_order_tender_order", "order_id", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="payment")
    method: Mapped[str] = mapped_column(String(20), default="cash")
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[Order] = relationship(back_populates="tenders")


class HeldOrder(Base):
    __tablename__ = "held_orders"
    __table_args__ = (Index("ix_held_order_store_created", "store_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Parked carts carry the intended fulfilment too (see Order.order_type).
    order_type: Mapped[str] = mapped_column(String(20), default="takeaway", server_default="takeaway")
    # Open ticket: the table this cart serves, and its service state.
    table_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dining_tables.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    # Where the ticket came from: pos | qr | online.
    source: Mapped[str] = mapped_column(String(20), default="pos", server_default="pos")
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (Index("ix_refund_order_created", "order_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    method: Mapped[str] = mapped_column(String(20), default="cash")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[Order] = relationship(back_populates="refunds")


class BillingPayment(Base):
    __tablename__ = "billing_payments"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_billing_payment_provider_external"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True)
    provider: Mapped[str] = mapped_column(String(30), default="chamabapay")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="USD")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_id: Mapped[str] = mapped_column(String(255), unique=True)
    # Immutable purchase snapshot, captured when the checkout is created so a
    # later plan/price change never rewrites what the customer bought.
    plan_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    billing_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qr_string: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set exactly once, under a row lock, when fulfillment has been applied.
    # The durable idempotency guard: replaying a webhook/poll is a no-op.
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubscriptionCapacityAction(Base):
    """Audit trail of capacity pauses/restores forced by a plan's limits.

    Stores and staff are never deleted when a workspace drops to a smaller
    plan; they are paused. Each forced pause/restore is recorded here so the
    current paused set is reconstructable and reversible, independent of the
    JSON snapshot cached on ``Subscription``.
    """

    __tablename__ = "subscription_capacity_actions"
    __table_args__ = (
        Index("ix_capacity_action_company_created", "company_id", "created_at"),
        Index("ix_capacity_action_subscription_resource", "subscription_id", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    resource_type: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BillingReceipt(Base):
    """Immutable customer receipt issued after a successful plan payment.

    Created exactly once by fulfillment (guarded by
    ``BillingPayment.fulfilled_at``) and never rewritten, so billing history and
    accounting survive later plan/price changes.
    """

    __tablename__ = "billing_receipts"
    __table_args__ = (Index("ix_billing_receipt_company_created", "company_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True)
    billing_payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing_payments.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(20))
    billing_cycle: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="USD")
    provider: Mapped[str] = mapped_column(String(30), default="chamabapay")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)




class BillingRefund(Base):
    """A correction against a billing payment, recorded by support.

    Prepaid KHQR payments are non-refundable by policy; this exists so genuine
    billing errors can be corrected without mutating or deleting the original
    immutable ``BillingPayment``. Recording a refund never changes entitlement.
    """

    __tablename__ = "billing_refunds"
    __table_args__ = (Index("ix_billing_refund_company_created", "company_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    billing_payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing_payments.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="USD")
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refunded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    refunded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (Index("ix_invitation_email_company", "email", "company_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(40), default="cashier")
    store_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (Index("ix_shift_store_opened", "store_id", "opened_at"), Index("ix_shift_user_status", "user_id", "status"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    opening_float: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sales_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    cash_received: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    cash_refunds: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_created", "user_id", "created_at"), Index("ix_notification_store_created", "store_id", "created_at"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(String(600), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (Index("ix_supplier_company_name", "company_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupplierPrice(Base):
    """What one supplier charges for a product (or a specific variant).

    A row with ``variant_id`` set prices one sellable variant; a row with
    ``variant_id`` NULL prices the whole product and applies to products that
    have no variants. This is how the same specification bought from two
    suppliers at two prices is tracked without duplicating the variant.
    """

    __tablename__ = "supplier_product_prices"
    __table_args__ = (
        Index("ix_supplier_price_company_product", "company_id", "product_id"),
        # PostgreSQL treats NULLs as distinct, so a plain unique constraint
        # would let one product collect several "no variant" rows. Two partial
        # indexes give exactly one row per supplier per target.
        Index("uq_supplier_price_product", "supplier_id", "product_id", unique=True, postgresql_where=text("variant_id IS NULL")),
        Index("uq_supplier_price_variant", "supplier_id", "variant_id", unique=True, postgresql_where=text("variant_id IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=True, index=True)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str | None] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=True)
    supplier_sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_order_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_purchase_company_created", "company_id", "created_at"),
        Index("ix_purchase_store_status", "store_id", "status"),
        UniqueConstraint("store_id", "po_number", name="uq_purchase_order_store_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    po_number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    ordered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenantAuditLog(Base):
    __tablename__ = "tenant_audit_logs"
    __table_args__ = (Index("ix_tenant_audit_company_created", "company_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    actor_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlatformActivity(Base):
    """Platform-wide event stream fanned out to the operations Telegram group.

    Unlike ``AuditLog`` (admin actuations) and ``TenantAuditLog`` (a workspace's
    own trail), this is the cross-tenant feed: signups, logins, plan payments,
    sales, refunds, transfers and team changes. It also backs the daily digest
    aggregates, so every forwarded event is queryable after the fact.
    """

    __tablename__ = "platform_activities"
    __table_args__ = (
        Index("ix_platform_activity_created", "created_at"),
        Index("ix_platform_activity_type_created", "event_type", "created_at"),
        Index("ix_platform_activity_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MediaAsset(Base):
    """A reusable image owned by one company (the media library).

    Files are stored content-addressed on disk; this row is the catalogue entry
    that lets the UI browse and reuse them. ``sha256`` is unique per company so
    identical bytes collapse to a single asset, and ``company_id`` keeps one
    tenant's library invisible to another.
    """

    __tablename__ = "media_assets"
    __table_args__ = (UniqueConstraint("company_id", "sha256", name="uq_media_asset_company_sha"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailTemplate(Base):
    """A reusable mailing draft: subject + HTML body written by a platform admin."""

    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(300))
    body_html: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EmailSend(Base):
    """One mailing message: the outbox, the retry ledger and the delivery log.

    A row starts as ``queued`` and is drained by the send worker, which retries
    with backoff until ``sent`` or ``failed``. Test sends are written straight
    as ``sent``/``failed`` because they are delivered synchronously.

    ``status`` tracks the furthest delivery stage the provider has confirmed:
    ``sent`` (accepted by the relay) → ``delivered`` → ``opened`` → ``clicked``.
    ``bounced`` and ``complained`` are terminal failures. The provider's message
    id and per-stage timestamps come from Resend webhook events; SMTP reports
    none, so those rows never move past ``sent``.
    """

    __tablename__ = "email_sends"
    __table_args__ = (
        Index("ix_email_send_created", "created_at"),
        Index("ix_email_send_user", "user_id"),
        Index("ix_email_send_recipient", "recipient_email"),
        Index("ix_email_send_queue", "status", "next_attempt_at"),
        Index("ix_email_send_provider_message", "provider_message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    recipient_email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body_html: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="sent")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailSuppression(Base):
    """An address that must never receive marketing mail (unsubscribe list)."""

    __tablename__ = "email_suppressions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(60), default="unsubscribed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MailingDripDelivery(Base):
    """One automated drip step delivered to one user.

    The unique (user, step) pair is the dedupe guard: a scheduled run may be
    retried without emailing the same person the same step twice.
    """

    __tablename__ = "mailing_drip_deliveries"
    __table_args__ = (
        UniqueConstraint("user_id", "step_id", name="uq_mailing_drip_user_step"),
        Index("ix_mailing_drip_step", "step_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str] = mapped_column(String(60))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupportConversation(Base):
    """One support-chat thread, owned by a user within a company.

    Company and user are stored on the row (not just derived from the caller) so
    a thread stays scoped to its workspace and can be listed without joining.
    """

    __tablename__ = "support_conversations"
    __table_args__ = (Index("ix_support_conversation_user_updated", "user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SupportMessage(Base):
    """One turn in a support conversation (``user`` or ``assistant``)."""

    __tablename__ = "support_messages"
    __table_args__ = (Index("ix_support_message_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("support_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    guide_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HelpArticle(Base):
    """A DB-backed help article, so ops can edit help content without a deploy.

    Seeded from ``app/support_content.py`` at migration time; that module remains
    the fallback baseline if this table is empty. Bilingual text lives inline
    (``*_km``) rather than in a separate overlay like the static module.
    """

    __tablename__ = "help_articles"
    __table_args__ = (Index("ix_help_article_section_position", "section_id", "position"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    section_id: Mapped[str] = mapped_column(String(80))
    section_title: Mapped[str] = mapped_column(String(160))
    section_title_km: Mapped[str | None] = mapped_column(String(160), nullable=True)
    section_blurb: Mapped[str] = mapped_column(String(300))
    section_blurb_km: Mapped[str | None] = mapped_column(String(300), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    title_km: Mapped[str | None] = mapped_column(String(200), nullable=True)
    steps: Mapped[list] = mapped_column(JSON)
    steps_km: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tip: Mapped[str | None] = mapped_column(Text, nullable=True)
    tip_km: Mapped[str | None] = mapped_column(Text, nullable=True)
    verticals: Mapped[list] = mapped_column(JSON)
    roles: Mapped[list] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SupportTicket(Base):
    """A merchant support request tracked from escalation to closure.

    Created when a merchant uses "Talk to a human"; the admin panel can mark it
    resolved, which notifies the merchant. The ``reference`` is the short code the
    merchant sees in the confirmation.
    """

    __tablename__ = "support_tickets"
    __table_args__ = (
        UniqueConstraint("reference", name="uq_support_ticket_reference"),
        Index("ix_support_ticket_company_created", "company_id", "created_at"),
        Index("ix_support_ticket_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(20))
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportTicketMessage(Base):
    """One message in a support ticket thread (merchant, agent or system).

    The opening message lives on ``SupportTicket.question``; this table holds the
    back-and-forth plus a system note capturing the assistant context at creation.
    """

    __tablename__ = "support_ticket_messages"
    __table_args__ = (Index("ix_support_ticket_message_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), index=True)
    author_type: Mapped[str] = mapped_column(String(20), default="agent")
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

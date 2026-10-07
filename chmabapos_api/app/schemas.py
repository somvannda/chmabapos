from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator, model_validator

from app.config import settings
from app.features import derive_plan_marketing_features
from app.support_content import ALL_ROLES
from app.verticals import COMPANY_VERTICALS


PRODUCT_UNITS = {"each", "kg", "g", "l", "ml", "pack", "box", "dozen"}
# Cosmetic grade ladder for used / refurbished electronics. "parts" marks a unit
# sold for repair/refurbishment. ``None`` means the unit is unassessed.
SERIAL_CONDITION_GRADES = {"premium", "excellent", "good", "fair", "parts"}

# Company-wide display formats. An empty string means "use the device default",
# which keeps merchant data looking the same until they explicitly choose one.
DATE_FORMAT_VALUES = ("", "DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD", "D MMM YYYY")
TIME_FORMAT_VALUES = ("", "12h", "24h")


def normalize_condition_grade(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned not in SERIAL_CONDITION_GRADES:
        raise ValueError("condition_grade must be one of: " + ", ".join(sorted(SERIAL_CONDITION_GRADES)))
    return cleaned


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(APIModel):
    status: str
    service: str
    version: str
    database: str


class PublicStatsRead(APIModel):
    """Aggregate platform figures shown on the public marketing site.

    Counts cover the whole platform; ``value_processed`` is the net
    (paid sales minus refunds) for the busiest single currency so mixed
    currencies are never summed together.
    """

    active_stores: int
    completed_sales: int
    value_processed: Decimal
    currency_code: str
    active_products: int


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(APIModel):
    user: "UserRead"
    message: str
    dev_verification_token: str | None = None
    mailhog_url: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=6, max_length=64)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ResendVerificationResponse(APIModel):
    message: str
    dev_verification_token: str | None = None
    mailhog_url: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=4096)
    # Mirrors LoginRequest.remember_me: when true the issued token uses the
    # longer jwt_remember_ttl_minutes so a Google sign-in can stay signed in.
    remember_me: bool = False


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(APIModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: "UserRead"


class GoogleAuthResponse(TokenResponse):
    is_new_user: bool = False


class UserRead(APIModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_email_verified: bool
    platform_role: str | None = None
    preferences: dict | None = None
    created_at: datetime


class PreferencesUpdateRequest(BaseModel):
    preferences: dict


class CurrencyRead(APIModel):
    code: str
    name: str
    symbol: str
    decimal_places: int
    is_active: bool


def normalize_aba_payway_link(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("Payment link must start with https://")
    if len(cleaned) > 255:
        raise ValueError("Payment link is too long (max 255 characters)")
    return cleaned


class PlanRead(APIModel):
    code: str
    name: str
    monthly_price: Decimal
    max_stores: int
    max_members: int
    transaction_limit: int
    description: str | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)
    marketing_features: list[str] = Field(default_factory=list)
    is_active: bool

    @model_validator(mode="after")
    def _derive_marketing_features(self) -> "PlanRead":
        self.marketing_features = derive_plan_marketing_features(
            max_stores=self.max_stores,
            max_members=self.max_members,
            transaction_limit=self.transaction_limit,
            capabilities=self.capabilities,
            monthly_price=self.monthly_price,
        )
        return self


class StoreRead(APIModel):
    id: UUID
    company_id: UUID
    name: str
    address: str | None
    phone: str | None
    timezone: str
    currency_code: str
    service_tax_rate: Decimal = Decimal("10.00")
    preferences: dict[str, Any] | None = None
    aba_payway_link: str | None = None
    aba_payway_status: str = "none"
    public_order_enabled: bool = False
    public_order_token: str | None = None
    is_active: bool
    created_at: datetime


class SessionPolicyRead(APIModel):
    """Effective sign-in session policy for the caller's company."""

    company_ttl_minutes: int | None = None
    default_ttl_minutes: int
    max_ttl_minutes: int


class SessionPolicyUpdateRequest(BaseModel):
    # ``None`` clears the company override and reverts to the platform default.
    ttl_minutes: int | None = Field(default=None, ge=1)


class CompanyRead(APIModel):
    id: UUID
    name: str
    country: str
    vertical: str = "general"
    tax_id: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    default_currency_code: str
    aba_payway_link: str | None = None
    aba_payway_status: str = "none"
    # Merchant-chosen display formats (see Company.settings). Empty = device default.
    date_format: str = ""
    time_format: str = ""
    created_at: datetime


class PaymentLinkVerificationRead(APIModel):
    scope: str
    id: UUID
    aba_payway_link: str | None = None
    aba_payway_status: str
    ok: bool
    message: str


class PaymentLinkTestScanRead(APIModel):
    scope: str
    qr_string: str
    checkout_url: str | None = None
    payment_public_id: str
    amount: str
    currency: str
    expires_at: str | None = None


class PaymentLinkTestScanStatusRequest(BaseModel):
    payment_public_id: str = Field(min_length=1, max_length=255)


class PaymentLinkTestScanStatusRead(APIModel):
    scope: str
    status: str
    paid: bool
    # Set once a paid test scan auto-activates the link (see _test_scan_status).
    aba_payway_status: str | None = None


class SubscriptionRead(APIModel):
    id: UUID
    company_id: UUID
    plan_code: str
    billing_cycle: str
    status: str
    starts_at: datetime
    ends_at: datetime | None
    scheduled_plan_code: str | None = None
    scheduled_store_ids: list[str] | None = None
    scheduled_member_ids: list[str] | None = None

    def _grace_deadline(self) -> datetime | None:
        """``ends_at`` + grace for an active paid plan; ``None`` otherwise."""
        if self.status != "active" or self.ends_at is None:
            return None
        ends = self.ends_at if self.ends_at.tzinfo else self.ends_at.replace(tzinfo=timezone.utc)
        return ends + timedelta(hours=settings.billing_grace_hours)

    @computed_field
    @property
    def grace_ends_at(self) -> datetime | None:
        """Moment the plan truly stops being usable: ``ends_at`` + grace."""
        return self._grace_deadline()

    @computed_field
    @property
    def in_grace(self) -> bool:
        """True while a paid plan is past ``ends_at`` but still inside grace."""
        deadline = self._grace_deadline()
        if deadline is None:
            return False
        ends = self.ends_at if self.ends_at.tzinfo else self.ends_at.replace(tzinfo=timezone.utc)  # type: ignore[union-attr]
        return ends < datetime.now(timezone.utc) < deadline


class WorkspaceSetupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=180)
    store_name: str = Field(min_length=2, max_length=180)
    country: str = Field(default="Cambodia", min_length=2, max_length=80)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    vertical: str = Field(default="general", max_length=20)
    store_address: str | None = Field(default=None, max_length=255)
    store_phone: str | None = Field(default=None, max_length=40)
    timezone: str = Field(default="Asia/Phnom_Penh", max_length=80)
    plan_code: str = Field(default="free", max_length=20)
    billing_cycle: str = Field(default="monthly", max_length=20)
    # Onboarding goal answers. Bands mirror app/billing.py; capability answers
    # are capability keys the merchant opted into on top of their business type.
    store_count_band: str = Field(default="1", max_length=10)
    team_size_band: str = Field(default="1", max_length=10)
    capability_answers: list[str] = Field(default_factory=list)

    @field_validator("currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("plan_code", mode="after")
    @classmethod
    def lowercase_plan(cls, value: str) -> str:
        return value.lower()

    @field_validator("vertical", mode="after")
    @classmethod
    def validate_vertical(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in COMPANY_VERTICALS:
            raise ValueError(f"vertical must be one of {sorted(COMPANY_VERTICALS)}")
        return cleaned


class WorkspaceRead(APIModel):
    company: CompanyRead
    store: StoreRead
    subscription: SubscriptionRead
    membership_role: str
    billing_payment: dict[str, Any] | None = None
    # Feature packs the store's business type enables (see app/verticals.py).
    # Drives which catalog/POS fields the UI surfaces first; never a hard gate.
    capabilities: list[str] = Field(default_factory=list)
    # The business type's own packs before per-store overrides. Lets the client
    # label each pack and offer "reset to business-type defaults" without
    # duplicating the vertical -> packs mapping.
    capability_defaults: list[str] = Field(default_factory=list)
    # The effective plan's enabled feature keys (see app/features.py). Lets the
    # POS hide plan-gated surfaces instead of showing them and hitting a 403.
    plan_features: list[str] = Field(default_factory=list)
    # The caller's resolved permission keys (see app/permissions.py). Drives the
    # permission-aware UI as the fixed role checks are progressively replaced.
    permissions: list[str] = Field(default_factory=list)


class WorkspaceMembershipRead(APIModel):
    company_id: UUID
    name: str
    role: str
    is_current: bool = False


class WorkspaceSwitchRequest(BaseModel):
    company_id: UUID


class PermissionRead(BaseModel):
    key: str
    label: str
    group: str


class RoleRead(APIModel):
    id: UUID
    key: str
    name: str
    is_system: bool
    permissions: list[str] = Field(default_factory=list)


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    permissions: list[str] | None = None


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    country: str | None = Field(default=None, min_length=2, max_length=80)
    tax_id: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    vertical: str | None = Field(default=None, max_length=20)
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    aba_payway_link: str | None = Field(default=None, max_length=255)
    # Display formats applied across the app and printed receipts.
    date_format: str | None = None
    time_format: str | None = None

    @field_validator("date_format", mode="after")
    @classmethod
    def validate_date_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if cleaned == "":
            return ""
        if cleaned not in DATE_FORMAT_VALUES:
            raise ValueError("date_format must be one of: " + ", ".join(item for item in DATE_FORMAT_VALUES if item))
        return cleaned

    @field_validator("time_format", mode="after")
    @classmethod
    def validate_time_format(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if cleaned == "":
            return ""
        if cleaned not in TIME_FORMAT_VALUES:
            raise ValueError("time_format must be one of: " + ", ".join(item for item in TIME_FORMAT_VALUES if item))
        return cleaned

    @field_validator("vertical", mode="after")
    @classmethod
    def validate_vertical(cls, value: str | None) -> str | None:
        if value is not None and value not in COMPANY_VERTICALS:
            raise ValueError(f"vertical must be one of {sorted(COMPANY_VERTICALS)}")
        return value

    @field_validator("default_currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("aba_payway_link", mode="before")
    @classmethod
    def clean_aba_payway_link(cls, value: str | None) -> str | None:
        return normalize_aba_payway_link(value)


class ExchangeRateCreateRequest(BaseModel):
    base_currency_code: str = Field(min_length=3, max_length=3)
    quote_currency_code: str = Field(min_length=3, max_length=3)
    rate: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    effective_from: datetime | None = None

    @field_validator("base_currency_code", "quote_currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class ExchangeRateRead(APIModel):
    id: UUID
    company_id: UUID
    base_currency_code: str
    quote_currency_code: str
    rate: Decimal
    effective_from: datetime
    created_by: UUID
    created_at: datetime
    is_active: bool


class ExchangeRateUpdateRequest(BaseModel):
    is_active: bool


class ExchangeQuoteRead(APIModel):
    base_currency_code: str
    quote_currency_code: str
    rate: Decimal
    amount: Decimal
    converted_amount: Decimal
    quote_decimal_places: int


class StoreCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    timezone: str = Field(default="Asia/Phnom_Penh", max_length=80)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    service_tax_rate: Decimal = Field(default=Decimal("10.00"), ge=0, le=100, max_digits=5, decimal_places=2)

    @field_validator("currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class StoreUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=80)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    service_tax_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    preferences: dict[str, Any] | None = None
    aba_payway_link: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("aba_payway_link", mode="before")
    @classmethod
    def clean_aba_payway_link(cls, value: str | None) -> str | None:
        return normalize_aba_payway_link(value)


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: UUID | None = None


class CategoryRead(APIModel):
    id: UUID
    company_id: UUID
    parent_id: UUID | None
    name: str
    is_active: bool
    created_at: datetime


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    sku: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    image: str | None = Field(default=None, max_length=500)
    barcode: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    unit: str = Field(default="each", max_length=20)
    track_inventory: bool = True
    track_serials: bool = False
    attributes: dict[str, Any] | None = None
    modifier_group_id: UUID | None = None
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    reorder_point: int = Field(default=10, ge=0, le=2_000_000_000)

    @field_validator("unit", mode="after")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        if value not in PRODUCT_UNITS:
            raise ValueError(f"unit must be one of {sorted(PRODUCT_UNITS)}")
        return value


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    image: str | None = Field(default=None, max_length=500)
    barcode: str | None = Field(default=None, max_length=80)
    brand: str | None = Field(default=None, max_length=120)
    unit: str | None = Field(default=None, max_length=20)
    track_inventory: bool | None = None
    track_serials: bool | None = None
    attributes: dict[str, Any] | None = None
    modifier_group_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("unit", mode="after")
    @classmethod
    def validate_unit(cls, value: str | None) -> str | None:
        if value is not None and value not in PRODUCT_UNITS:
            raise ValueError(f"unit must be one of {sorted(PRODUCT_UNITS)}")
        return value


class ProductOptionValueRead(APIModel):
    id: UUID
    value: str
    position: int = 0


class ProductOptionRead(APIModel):
    id: UUID
    name: str
    position: int = 0
    values: list[ProductOptionValueRead] = Field(default_factory=list)


class ProductVariantRead(APIModel):
    id: UUID
    product_id: UUID
    sku: str
    barcode: str | None = None
    name: str
    image: str | None = None
    price: Decimal | None = None
    cost_price: Decimal | None = None
    attributes: dict[str, Any] | None = None
    is_active: bool = True
    position: int = 0
    on_hand: float = 0
    reorder_point: int = 10


class ProductVariantInput(BaseModel):
    id: UUID | None = None
    sku: str = Field(min_length=1, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=180)
    image: str | None = Field(default=None, max_length=500)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    attributes: dict[str, Any] | None = None
    is_active: bool = True
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    reorder_point: int = Field(default=10, ge=0, le=2_000_000_000)


class ProductVariantsSetRequest(BaseModel):
    variants: list[ProductVariantInput] = Field(default_factory=list)


class SupplierPriceRead(APIModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str | None = None
    product_id: UUID
    variant_id: UUID | None = None
    unit_cost: Decimal
    currency_code: str | None = None
    supplier_sku: str | None = None
    lead_time_days: int | None = None
    min_order_qty: int | None = None
    is_preferred: bool = False
    note: str | None = None
    updated_at: datetime | None = None


class SupplierPriceInput(BaseModel):
    # ``id`` lets a client round-trip a row it already knows about, but the
    # (supplier_id, variant_id) target is what actually identifies it.
    id: UUID | None = None
    supplier_id: UUID
    variant_id: UUID | None = None
    unit_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    supplier_sku: str | None = Field(default=None, max_length=80)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    min_order_qty: int | None = Field(default=None, ge=1, le=1_000_000)
    is_preferred: bool = False
    note: str | None = Field(default=None, max_length=255)


class SupplierPricesSetRequest(BaseModel):
    prices: list[SupplierPriceInput] = Field(default_factory=list)


class MediaAssetRead(APIModel):
    id: UUID
    url: str
    sha256: str
    content_type: str | None = None
    byte_size: int = 0
    original_filename: str | None = None
    created_at: datetime


class SerialPhotoRead(APIModel):
    id: UUID
    serial_id: UUID
    url: str
    position: int = 0
    created_at: datetime


class ProductSerialRead(APIModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    store_id: UUID | None = None
    serial_number: str
    imei: str | None = None
    status: str = "in_stock"
    cost_price: Decimal | None = None
    supplier_warranty_months: int | None = None
    supplier_warranty_until: datetime | None = None
    customer_warranty_months: int | None = None
    customer_warranty_until: datetime | None = None
    sold_at: datetime | None = None
    condition_grade: str | None = None
    battery_health: int | None = None
    battery_cycle_count: int | None = None
    condition_report: dict[str, Any] | None = None
    supplier_id: UUID | None = None
    supplier_name: str | None = None
    purchase_order_id: UUID | None = None
    graded_at: datetime | None = None
    graded_by: UUID | None = None
    photos: list[SerialPhotoRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProductSerialInput(BaseModel):
    serial_number: str = Field(min_length=1, max_length=120)
    imei: str | None = Field(default=None, max_length=40)
    variant_id: UUID | None = None
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    supplier_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    customer_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    condition_grade: str | None = Field(default=None, max_length=20)
    battery_health: int | None = Field(default=None, ge=0, le=100)
    battery_cycle_count: int | None = Field(default=None, ge=0, le=1_000_000)
    condition_report: dict[str, Any] | None = None
    supplier_id: UUID | None = None

    @field_validator("condition_grade")
    @classmethod
    def _validate_condition_grade(cls, value: str | None) -> str | None:
        return normalize_condition_grade(value)


class ProductSerialsSetRequest(BaseModel):
    serials: list[ProductSerialInput] = Field(default_factory=list)


class ProductSerialUpdateRequest(BaseModel):
    # Correcting a mistyped number is allowed only while the unit is unsold.
    serial_number: str | None = Field(default=None, min_length=1, max_length=120)
    status: Literal["in_stock", "sold", "returned", "defective"] | None = None
    imei: str | None = Field(default=None, max_length=40)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    supplier_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    customer_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    variant_id: UUID | None = None
    condition_grade: str | None = Field(default=None, max_length=20)
    battery_health: int | None = Field(default=None, ge=0, le=100)
    battery_cycle_count: int | None = Field(default=None, ge=0, le=1_000_000)
    condition_report: dict[str, Any] | None = None
    supplier_id: UUID | None = None

    @field_validator("condition_grade")
    @classmethod
    def _validate_condition_grade(cls, value: str | None) -> str | None:
        return normalize_condition_grade(value)


class SerialLookupRead(APIModel):
    id: UUID
    serial_number: str
    imei: str | None = None
    status: str
    product_id: UUID
    product_name: str
    variant_id: UUID | None = None
    variant_name: str | None = None
    store_id: UUID | None = None
    cost_price: Decimal | None = None
    supplier_warranty_months: int | None = None
    supplier_warranty_until: datetime | None = None
    customer_warranty_months: int | None = None
    customer_warranty_until: datetime | None = None
    sold_at: datetime | None = None
    condition_grade: str | None = None
    battery_health: int | None = None
    battery_cycle_count: int | None = None
    supplier_id: UUID | None = None
    supplier_name: str | None = None
    order_number: str | None = None
    customer_name: str | None = None
    photos: list[SerialPhotoRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class POSProductHit(APIModel):
    """A sellable catalogue line returned by the till search.

    ``variant_id`` is null for simple products; otherwise one hit is emitted per
    active variant, mirroring how the POS flattens products into cart lines.
    """

    product_id: UUID
    variant_id: UUID | None = None
    name: str
    variant_name: str | None = None
    sku: str
    barcode: str | None = None
    price: Decimal
    stock: float = 0
    image: str | None = None
    track_serials: bool = False


class POSSerialHit(APIModel):
    """An in-stock serial unit a cashier can add to the cart.

    Deliberately excludes cost, supplier and warranty fields: those belong to
    the manager-facing serial lookup, not the till. Cosmetic condition is safe
    to show so the cashier can pick the right unit.
    """

    id: UUID
    serial_number: str
    imei: str | None = None
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    variant_name: str | None = None
    sku: str
    price: Decimal
    image: str | None = None
    condition_grade: str | None = None
    battery_health: int | None = None
    battery_cycle_count: int | None = None


class POSSearchResult(APIModel):
    """Grouped results for the single POS search/scan field."""

    products: list[POSProductHit] = Field(default_factory=list)
    serials: list[POSSerialHit] = Field(default_factory=list)


class SerialConditionRequest(BaseModel):
    """Record a condition assessment for a unit (initial grade or a re-grade)."""

    condition_grade: str | None = Field(default=None, max_length=20)
    battery_health: int | None = Field(default=None, ge=0, le=100)
    battery_cycle_count: int | None = Field(default=None, ge=0, le=1_000_000)
    condition_report: dict[str, Any] | None = None

    @field_validator("condition_grade")
    @classmethod
    def _validate_condition_grade(cls, value: str | None) -> str | None:
        return normalize_condition_grade(value)


class SerialConditionHistoryRead(APIModel):
    id: UUID
    serial_id: UUID
    condition_grade: str | None = None
    battery_health: int | None = None
    battery_cycle_count: int | None = None
    condition_report: dict[str, Any] | None = None
    graded_by: UUID | None = None
    graded_at: datetime
    created_at: datetime


class SerialServiceTicketRead(APIModel):
    id: UUID
    serial_id: UUID
    store_id: UUID | None = None
    ticket_type: str
    status: str
    summary: str
    description: str | None = None
    cost: Decimal | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SerialServiceTicketCreateRequest(BaseModel):
    ticket_type: Literal["repair", "warranty", "inspection"] = "repair"
    summary: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class SerialServiceTicketUpdateRequest(BaseModel):
    status: Literal["open", "in_progress", "resolved", "cancelled"] | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class MarginReportRow(APIModel):
    product_id: UUID
    product_name: str
    sku: str
    quantity: float
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_percent: float


class ComboMarginRow(APIModel):
    combo_id: UUID | None = None
    combo_name: str
    quantity: float
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_percent: float


class MarginReport(APIModel):
    from_date: date
    to_date: date
    currency_code: str
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_percent: float
    rows: list[MarginReportRow] = Field(default_factory=list)
    combos: list[ComboMarginRow] = Field(default_factory=list)


class ConditionGradeMarginRow(APIModel):
    condition_grade: str | None = None
    quantity: float = 0
    revenue: Decimal = Decimal("0.00")
    cost: Decimal = Decimal("0.00")
    margin: Decimal = Decimal("0.00")
    margin_percent: float = 0.0


class ConditionOnHandRow(APIModel):
    condition_grade: str | None = None
    units: int = 0
    avg_battery_health: float | None = None


class ConditionBatteryBucket(APIModel):
    label: str
    count: int


class ConditionSupplierRow(APIModel):
    supplier_id: UUID | None = None
    supplier_name: str | None = None
    units: int = 0
    in_stock: int = 0
    sold: int = 0
    returned: int = 0
    defective: int = 0


class ConditionReport(APIModel):
    from_date: date
    to_date: date
    currency_code: str
    revenue: Decimal
    cost: Decimal
    margin: Decimal
    margin_percent: float
    by_grade: list[ConditionGradeMarginRow] = Field(default_factory=list)
    on_hand_by_grade: list[ConditionOnHandRow] = Field(default_factory=list)
    battery: list[ConditionBatteryBucket] = Field(default_factory=list)
    suppliers: list[ConditionSupplierRow] = Field(default_factory=list)


class AttributeSuggestions(APIModel):
    keys: list[str] = Field(default_factory=list)
    values: dict[str, list[str]] = Field(default_factory=dict)
    brands: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    skus: list[str] = Field(default_factory=list)
    variant_names: list[str] = Field(default_factory=list)
    variant_skus: list[str] = Field(default_factory=list)


class ModifierRead(APIModel):
    id: UUID
    name: str
    price_delta: Decimal
    ingredient_product_id: UUID | None = None
    quantity: int = 1
    is_default: bool = False
    position: int = 0


class ModifierGroupRead(APIModel):
    id: UUID
    name: str
    min_select: int = 0
    max_select: int = 1
    is_required: bool = False
    position: int = 0
    modifiers: list[ModifierRead] = Field(default_factory=list)


class ModifierInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price_delta: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)
    ingredient_product_id: UUID | None = None
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    is_default: bool = False


class ModifierGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    min_select: int = Field(default=0, ge=0, le=100)
    max_select: int = Field(default=1, ge=0, le=100)
    is_required: bool = False
    modifiers: list[ModifierInput] = Field(default_factory=list)


class ComboItemInput(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)


class ComboItemRead(APIModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    variant_name: str | None = None
    sku: str
    quantity: float = 1
    unit_price: Decimal
    position: int = 0


class ComboGroupOptionInput(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    price_delta: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)


class ComboGroupOptionRead(APIModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    variant_name: str | None = None
    sku: str
    price_delta: Decimal
    position: int = 0


class ComboGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    min_select: int = Field(default=1, ge=0, le=100)
    max_select: int = Field(default=1, ge=1, le=100)
    is_required: bool = True
    options: list[ComboGroupOptionInput] = Field(min_length=1, max_length=100)


class ComboGroupRead(APIModel):
    id: UUID
    name: str
    min_select: int = 1
    max_select: int = 1
    is_required: bool = True
    position: int = 0
    options: list[ComboGroupOptionRead] = Field(default_factory=list)


class ComboSelectionInput(BaseModel):
    group_id: UUID
    option_id: UUID
    quantity: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)


class ComboInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    sku: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    image: str | None = Field(default=None, max_length=500)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    is_active: bool = True
    items: list[ComboItemInput] = Field(default_factory=list, max_length=100)
    groups: list[ComboGroupInput] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_a_component(self) -> "ComboInput":
        # A combo is either fixed items, choice groups, or a mix.
        if not self.items and not self.groups:
            raise ValueError("A combo needs at least one item or group")
        return self


class ComboRead(APIModel):
    id: UUID
    company_id: UUID
    name: str
    sku: str | None = None
    description: str | None = None
    image: str | None = None
    price: Decimal
    is_active: bool
    position: int = 0
    created_at: datetime
    updated_at: datetime
    items: list[ComboItemRead] = Field(default_factory=list)
    groups: list[ComboGroupRead] = Field(default_factory=list)


class TradeInCreateRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    customer_id: UUID | None = None
    serial_number: str = Field(min_length=1, max_length=120)
    imei: str | None = Field(default=None, max_length=40)
    condition_grade: str | None = Field(default=None, max_length=20)
    battery_health: int | None = Field(default=None, ge=0, le=100)
    condition_report: dict[str, Any] | None = None
    assessed_value: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    kind: Literal["trade_in", "buyback"] = "trade_in"
    notes: str | None = Field(default=None, max_length=1000)


class TradeInRead(APIModel):
    id: UUID
    store_id: UUID
    customer_id: UUID | None = None
    product_id: UUID
    product_name: str
    serial_id: UUID | None = None
    order_id: UUID | None = None
    serial_number: str
    imei: str | None = None
    condition_grade: str | None = None
    battery_health: int | None = None
    assessed_value: Decimal
    kind: str
    status: str
    notes: str | None = None
    created_at: datetime


class WarrantyClaimCreateRequest(BaseModel):
    serial_id: UUID
    issue: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    customer_id: UUID | None = None


class WarrantyClaimDecideRequest(BaseModel):
    approve: bool
    resolution: Literal["repair", "replace", "refund", "deny"] | None = None
    note: str | None = Field(default=None, max_length=1000)


class WarrantyClaimResolveRequest(BaseModel):
    resolution: Literal["repair", "replace", "refund", "deny"]
    note: str | None = Field(default=None, max_length=1000)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    replacement_serial_number: str | None = Field(default=None, max_length=120)
    replacement_imei: str | None = Field(default=None, max_length=40)
    refund_id: UUID | None = None


class WarrantyClaimEventRead(APIModel):
    id: UUID
    from_status: str | None = None
    to_status: str
    note: str | None = None
    actor_id: UUID | None = None
    created_at: datetime


class WarrantyClaimRead(APIModel):
    id: UUID
    store_id: UUID
    claim_number: str
    serial_id: UUID
    serial_number: str | None = None
    customer_id: UUID | None = None
    order_id: UUID | None = None
    status: str
    resolution: str | None = None
    issue: str
    description: str | None = None
    cost: Decimal | None = None
    replacement_serial_id: UUID | None = None
    refund_id: UUID | None = None
    service_ticket_id: UUID | None = None
    claimed_at: datetime
    decided_at: datetime | None = None
    resolved_at: datetime | None = None
    events: list[WarrantyClaimEventRead] = Field(default_factory=list)


class ProductBatchRead(APIModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    store_id: UUID | None = None
    batch_code: str | None = None
    expiry_date: date | None = None
    quantity_on_hand: float = 0
    cost_price: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class ExpiringBatchRead(APIModel):
    id: UUID
    product_id: UUID
    product_name: str
    variant_id: UUID | None = None
    variant_name: str | None = None
    batch_code: str | None = None
    expiry_date: date | None = None
    quantity_on_hand: float = 0
    days_until_expiry: int | None = None


class ProductBatchInput(BaseModel):
    batch_code: str | None = Field(default=None, max_length=80)
    variant_id: UUID | None = None
    expiry_date: date | None = None
    quantity_on_hand: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ProductBatchesSetRequest(BaseModel):
    batches: list[ProductBatchInput] = Field(default_factory=list)


class ProductRead(APIModel):
    id: UUID
    company_id: UUID
    category_id: UUID | None
    name: str
    sku: str
    description: str | None
    image: str | None = None
    barcode: str | None = None
    brand: str | None = None
    unit: str = "each"
    track_inventory: bool = True
    track_serials: bool = False
    is_sample: bool = False
    attributes: dict[str, Any] | None = None
    modifier_group_id: UUID | None = None
    price: Decimal
    cost_price: Decimal | None
    tax_rate: Decimal | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    category: CategoryRead | None = None
    on_hand: float = 0
    reorder_point: int = 10
    variants: list[ProductVariantRead] = Field(default_factory=list)


class InventoryVariantRead(APIModel):
    variant_id: UUID
    name: str
    sku: str
    on_hand: float
    reorder_point: int
    status: Literal["healthy", "low", "out"]
    # Retail price and cost basis for this variant, when set. Used to value the
    # stock a variant holds without falling back to the parent product.
    price: Decimal | None = None
    cost_price: Decimal | None = None


class InventoryRead(APIModel):
    store_id: UUID
    product_id: UUID
    product_name: str
    sku: str
    price: Decimal
    # Catalog cost basis. Null when the product has no cost recorded; the UI
    # must not treat a missing cost as zero when valuing stock.
    cost_price: Decimal | None = None
    on_hand: float
    reorder_point: int
    status: Literal["healthy", "low", "out"]
    updated_at: datetime
    track_serials: bool = False
    image: str | None = None
    variants: list[InventoryVariantRead] = Field(default_factory=list)


APPROVAL_ACTIONS: tuple[str, ...] = ("refund", "discount", "cancel_paid_order", "price_cost_edit", "stock_write_off", "loyalty_adjust")

# Settings and permissions stay owner-only and are intentionally not configurable.
APPROVAL_OWNER_ONLY = ("settings_permissions",)


class ApprovalRule(BaseModel):
    mode: Literal["off", "review", "approval"] = "off"
    threshold: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    approvers: list[Literal["owner", "manager", "inventory_manager"]] = Field(default_factory=lambda: ["owner", "manager"])


def default_approval_policy() -> dict:
    return {
        "enabled": False,
        "maker_checker": True,
        "expiry_minutes": 60,
        "notify_in_app": True,
        "notify_telegram": False,
        "rules": {
            "refund": {"mode": "review", "threshold": "50", "approvers": ["owner", "manager"]},
            "discount": {"mode": "review", "threshold": "10", "approvers": ["owner", "manager"]},
            "cancel_paid_order": {"mode": "review", "threshold": None, "approvers": ["owner", "manager"]},
            "price_cost_edit": {"mode": "review", "threshold": None, "approvers": ["owner"]},
            "stock_write_off": {"mode": "review", "threshold": "10", "approvers": ["owner", "manager"]},
            "loyalty_adjust": {"mode": "review", "threshold": "100", "approvers": ["owner", "manager"]},
        },
    }


class ApprovalPolicy(BaseModel):
    enabled: bool = False
    maker_checker: bool = True
    expiry_minutes: int = Field(default=60, ge=5, le=1440)
    notify_in_app: bool = True
    notify_telegram: bool = False
    rules: dict[str, ApprovalRule] = Field(default_factory=dict)


class ApprovalPolicyRead(BaseModel):
    policy: ApprovalPolicy
    available: bool = False
    team_size: int = 0
    has_manager: bool = False
    has_inventory_manager: bool = False
    has_cashier: bool = False


class ApprovalDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class ApprovalRequestRead(APIModel):
    id: UUID
    action: str
    status: str
    amount: Decimal | None = None
    reason: str | None = None
    store_id: UUID | None = None
    requested_by: UUID | None = None
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    payload: dict[str, Any] | None = None


class StockMovementRead(APIModel):
    """One auditable change to on-hand stock, with why it happened."""

    id: UUID
    created_at: datetime
    product_id: UUID
    product_name: str
    variant_id: UUID | None = None
    variant_name: str | None = None
    quantity: Decimal
    movement_type: str
    reason: str | None = None
    reference_id: str | None = None
    unit_cost: Decimal | None = None
    actor: str | None = None


class InventoryAdjustRequest(BaseModel):
    quantity: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    reason: str = Field(default="manual_adjustment", min_length=1, max_length=255)
    variant_id: UUID | None = None


class InventoryRestockSerialInput(BaseModel):
    """One received unit, with its own cost, source and condition.

    When a restock sends ``serials``, each entry overrides the batch-level
    defaults on the parent request for that unit.
    """

    serial_number: str = Field(min_length=1, max_length=120)
    imei: str | None = Field(default=None, max_length=40)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    supplier_id: UUID | None = None
    supplier_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    customer_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    condition_grade: str | None = Field(default=None, max_length=20)
    battery_health: int | None = Field(default=None, ge=0, le=100)
    battery_cycle_count: int | None = Field(default=None, ge=0, le=1_000_000)
    condition_report: dict[str, Any] | None = None

    @field_validator("condition_grade")
    @classmethod
    def _validate_condition_grade(cls, value: str | None) -> str | None:
        return normalize_condition_grade(value)


class InventoryRestockRequest(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    supplier: str | None = Field(default=None, max_length=120)
    reference: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=255)
    variant_id: UUID | None = None
    serial_numbers: list[str] | None = Field(default=None, max_length=500)
    serials: list[InventoryRestockSerialInput] | None = Field(default=None, max_length=500)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    supplier_warranty_months: int | None = Field(default=None, ge=0, le=1200)
    customer_warranty_months: int | None = Field(default=None, ge=0, le=1200)


class StockTransferItemRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    # Required for serial-tracked products: the exact serials to move, one per unit.
    serial_numbers: list[str] | None = Field(default=None, max_length=500)


class StockTransferCreateRequest(BaseModel):
    to_store_id: UUID
    items: list[StockTransferItemRequest] = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=255)


class VariantStockTransferRequest(BaseModel):
    """Move stock between two variants of the same product (e.g. fixing a mis-set balance)."""

    from_variant_id: UUID
    to_variant_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    reason: str = Field(default="variant_transfer", min_length=1, max_length=255)


class ConsolidatedStoreReportRead(APIModel):
    store_id: UUID
    store_name: str
    transactions: int
    net_sales: Decimal
    gross_sales: Decimal
    items_sold: float
    refunds: Decimal = Decimal("0.00")
    refunds_count: int = 0
    average_order: Decimal = Decimal("0.00")


class ConsolidatedReportRead(APIModel):
    from_date: date
    to_date: date
    stores_count: int
    transactions: int
    items_sold: float
    gross_sales: Decimal
    discounts: Decimal
    tax: Decimal
    net_sales: Decimal
    refunds: Decimal
    refunds_count: int
    net_after_refunds: Decimal
    average_order: Decimal
    base_currency_code: str
    daily_sales: list[dict[str, Any]] = Field(default_factory=list)
    payment_methods: list[dict[str, Any]] = Field(default_factory=list)
    category_sales: list[dict[str, Any]] = Field(default_factory=list)
    top_products: list[dict[str, Any]] = Field(default_factory=list)
    per_store: list[ConsolidatedStoreReportRead] = Field(default_factory=list)
    transactions_detail: list[ReportTransactionRead] = Field(default_factory=list)


class MembershipRead(APIModel):
    id: UUID
    user_id: UUID
    company_id: UUID
    role: str
    status: str
    user: UserRead
    store_ids: list[UUID] = Field(default_factory=list)


class MembershipUpdateRequest(BaseModel):
    role: str | None = None
    store_ids: list[UUID] | None = None
    status: Literal["active", "revoked"] | None = None


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str = "cashier"
    store_ids: list[UUID] = Field(default_factory=list, max_length=20)


class InvitationRead(APIModel):
    id: UUID
    company_id: UUID
    email: EmailStr
    role: str
    store_ids: list[str]
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    dev_invitation_token: str | None = None


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=20)
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class CustomerBriefRead(APIModel):
    id: UUID
    name: str
    phone: str | None
    email: EmailStr | None


class CustomerRead(APIModel):
    id: UUID
    name: str
    phone: str | None
    email: EmailStr | None
    notes: str | None
    points: Decimal = Decimal("0.00")
    is_active: bool
    created_at: datetime


class CustomerDetailRead(APIModel):
    customer: CustomerRead
    orders_count: int = 0
    total_spent: Decimal = Decimal("0.00")
    orders: list["OrderRead"] = []


class ShiftOpenRequest(BaseModel):
    opening_float: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)


class ShiftCloseRequest(BaseModel):
    counted_cash: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    notes: str | None = Field(default=None, max_length=255)


class ShiftRead(APIModel):
    id: UUID
    store_id: UUID
    user_id: UUID
    cashier_name: str | None = None
    status: str
    opening_float: Decimal
    opened_at: datetime
    closed_at: datetime | None
    sales_total: Decimal = Decimal("0.00")
    cash_received: Decimal = Decimal("0.00")
    cash_refunds: Decimal = Decimal("0.00")
    expected_cash: Decimal = Decimal("0.00")
    counted_cash: Decimal | None = None
    difference: Decimal | None = None
    orders_count: int = 0
    notes: str | None = None


class NotificationRead(APIModel):
    id: UUID
    type: str
    title: str
    body: str | None = None
    is_read: bool = False
    created_at: datetime


class ModifierSelectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price_delta: Decimal = Field(default=Decimal("0.00"), max_digits=12, decimal_places=2)


class OrderItemRequest(BaseModel):
    product_id: UUID | None = None
    combo_id: UUID | None = None
    combo_selections: list[ComboSelectionInput] = Field(default_factory=list, max_length=100)
    variant_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    serial_numbers: list[str] = Field(default_factory=list, max_length=100)
    modifiers: list[ModifierSelectionInput] = Field(default_factory=list, max_length=50)
    seat: int | None = Field(default=None, ge=1, le=1000)
    course: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def require_product_or_combo(self) -> "OrderItemRequest":
        # A line sells either a single product/variant or a whole combo bundle.
        if (self.product_id is None) == (self.combo_id is None):
            raise ValueError("Provide either product_id or combo_id, not both")
        return self


class OrderTenderRequest(BaseModel):
    method: Literal["cash", "khqr", "trade_in"]
    currency_code: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    # For method="trade_in": the accepted TradeIn whose credit this tender applies.
    trade_in_id: UUID | None = None

    @field_validator("currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class OrderCreateRequest(BaseModel):
    items: list[OrderItemRequest] = Field(min_length=1, max_length=100)
    payment_method: Literal["cash", "khqr"] | None = None
    tenders: list[OrderTenderRequest] | None = Field(default=None, min_length=1, max_length=20)
    change_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=160)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    # Loyalty points to redeem against this sale; deducted with the order and
    # applied as a discount. Restored on a full refund.
    redeem_points: int = Field(default=0, ge=0, le=1_000_000)
    # Client idempotency key for offline replay: a repeated create with the same
    # id returns the existing order instead of creating a duplicate.
    client_order_id: str | None = Field(default=None, max_length=64)
    tip: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    order_type: Literal["dine_in", "takeaway", "delivery"] = "takeaway"
    table_id: UUID | None = None
    # Reservation / deposit. When ``pickup_at`` is set and the tendered amount is
    # less than the total, the order becomes a reservation: the deposit is taken
    # now, ``hold_stock`` decides whether inventory is drawn off the shelf, and
    # the balance is collected later via ``POST /orders/{id}/collect``.
    pickup_at: datetime | None = None
    pickup_note: str | None = Field(default=None, max_length=500)
    hold_stock: bool = True

    @field_validator("items")
    @classmethod
    def require_unique_products(cls, value: list[OrderItemRequest]) -> list[OrderItemRequest]:
        # A combo is keyed by its own id; a plain line by its product.
        keys = [(item.combo_id or item.product_id, item.variant_id) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Each product variant can appear only once per order")
        return value

    @field_validator("change_currency_code", mode="after")
    @classmethod
    def uppercase_change_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class OrderCollectRequest(BaseModel):
    """Settle the outstanding balance of a ``pending_pickup`` reservation."""

    tenders: list[OrderTenderRequest] = Field(min_length=1, max_length=20)
    change_currency_code: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("change_currency_code", mode="after")
    @classmethod
    def uppercase_change_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class OrderPickupUpdateRequest(BaseModel):
    """Update the pickup window of a ``pending_pickup`` reservation."""

    pickup_at: datetime
    pickup_note: str | None = Field(default=None, max_length=500)


class OrderCancelRequest(BaseModel):
    """Cancel a pending order/reservation.

    ``refund_deposit`` overrides the store's ``reservation_cancel_deposit``
    preference for this call: ``True`` refunds the collected deposit, ``False``
    forfeits it, and ``None`` follows the store setting.
    """

    refund_deposit: bool | None = None


class PaymentRead(APIModel):
    id: UUID
    order_id: UUID | None = None
    provider: str
    status: str
    amount: Decimal
    currency_code: str
    external_id: str | None
    reference_id: str | None
    qr_string: str | None
    checkout_url: str | None
    created_at: datetime
    approved_at: datetime | None


class OrderItemRead(APIModel):
    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    variant_name: str | None = None
    attributes: dict[str, Any] | None = None
    modifiers: list[dict[str, Any]] | None = None
    serials: list[str] = Field(default_factory=list)
    condition_grade: str | None = None
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: float
    line_total: Decimal
    combo_id: UUID | None = None
    combo_name: str | None = None
    combo_components: list[dict[str, Any]] | None = None
    seat: int | None = None
    course: str | None = None


DELIVERY_STATUSES = {"none", "pending", "assigned", "out_for_delivery", "delivered", "failed"}


class DeliveryUpdateRequest(BaseModel):
    driver_name: str | None = Field(default=None, max_length=120)
    delivery_address: str | None = Field(default=None, max_length=400)
    delivery_notes: str | None = Field(default=None, max_length=1000)
    status: str | None = None

    @field_validator("status", mode="after")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        if cleaned not in DELIVERY_STATUSES:
            raise ValueError("status must be one of: " + ", ".join(sorted(DELIVERY_STATUSES)))
        return cleaned


class OrderRead(APIModel):
    id: UUID
    store_id: UUID
    order_number: str
    status: str
    customer_name: str | None
    currency_code: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    tip: Decimal = Decimal("0.00")
    order_type: str = "takeaway"
    table_id: UUID | None = None
    # Reservation / deposit state. ``amount_paid`` is the sum of settled
    # payments (the deposit plus anything collected since) and ``balance_due``
    # is what is still owed before the order can be completed.
    deposit: Decimal = Decimal("0.00")
    amount_paid: Decimal = Decimal("0.00")
    balance_due: Decimal = Decimal("0.00")
    pickup_at: datetime | None = None
    pickup_note: str | None = None
    reservation_expires_at: datetime | None = None
    stock_held: bool = False
    delivery_status: str = "none"
    driver_name: str | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None
    assigned_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    paid_at: datetime | None
    refunded_amount: Decimal = Decimal("0.00")
    customer: CustomerBriefRead | None = None
    items: list[OrderItemRead]
    payments: list[PaymentRead]
    tenders: list["OrderTenderRead"]
    tendered_base_amount: Decimal
    change_amount: Decimal
    change_currency_code: str | None


class OrderTenderRead(APIModel):
    id: UUID
    order_id: UUID
    kind: Literal["payment", "change"]
    method: str
    currency_code: str
    amount: Decimal
    base_amount: Decimal
    exchange_rate: Decimal
    created_at: datetime


def held_line_key(product_id: UUID, variant_id: UUID | None, modifiers: list | None, seat: int | None = None) -> str:
    """Stable identity for a held line: product + variant + the set of modifiers.

    The same product with different options (a large oat latte vs a small one) is
    a distinct line, so uniqueness, merge and split all key on this instead of
    the product alone. ``seat`` is part of the identity too, so two identical
    drinks ordered by different seats stay distinct; course is not, so a line can
    be re-coursed without forking it. Accepts modifier objects (``.name``) or
    snapshot dicts.
    """
    names = ",".join(sorted((entry.name if hasattr(entry, "name") else entry.get("name", "")) for entry in (modifiers or [])))
    suffix = f":s{seat}" if seat else ""
    return f"{product_id}:{variant_id or ''}:{names}{suffix}"


class HeldItemRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    modifiers: list[ModifierSelectionInput] = Field(default_factory=list, max_length=50)
    seat: int | None = Field(default=None, ge=1, le=1000)
    course: str | None = Field(default=None, max_length=40)


class HeldOrderCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    order_type: Literal["dine_in", "takeaway", "delivery"] = "takeaway"
    table_id: UUID | None = None
    items: list[HeldItemRequest] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def require_unique_lines(cls, value: list[HeldItemRequest]) -> list[HeldItemRequest]:
        keys = [held_line_key(item.product_id, item.variant_id, item.modifiers, item.seat) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Each product variant and add-on combination can appear only once per held order")
        return value


class HeldOrderMergeRequest(BaseModel):
    into_id: UUID


class HeldOrderTransferRequest(BaseModel):
    table_id: UUID | None = None


class HeldOrderSplitRequest(BaseModel):
    items: list[HeldItemRequest] = Field(min_length=1, max_length=100)
    table_id: UUID | None = None

    @field_validator("items")
    @classmethod
    def require_unique_lines(cls, value: list[HeldItemRequest]) -> list[HeldItemRequest]:
        keys = [held_line_key(item.product_id, item.variant_id, item.modifiers, item.seat) for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Each product variant and add-on combination can appear only once per split")
        return value


class HeldOrderUpdateRequest(BaseModel):
    status: Literal["open", "served"]


class HeldOrderFireRequest(BaseModel):
    # Fire every unfired line in this course, or all unfired lines when omitted.
    course: str | None = Field(default=None, max_length=40)


class HeldLineUpdateRequest(BaseModel):
    # Identify the line by its current key; set its seat and/or course.
    line_key: str = Field(min_length=1, max_length=400)
    seat: int | None = Field(default=None, ge=1, le=1000)
    course: str | None = Field(default=None, max_length=40)


class HeldItemRead(APIModel):
    product_id: UUID
    variant_id: UUID | None = None
    variant_name: str | None = None
    attributes: dict[str, Any] | None = None
    modifiers: list[dict[str, Any]] | None = None
    line_key: str
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: float
    line_total: Decimal
    seat: int | None = None
    course: str | None = None
    fired_at: str | None = None


class HeldOrderRead(APIModel):
    id: UUID
    store_id: UUID
    created_by: UUID | None = None
    cashier_name: str | None = None
    label: str | None
    order_type: str = "takeaway"
    table_id: UUID | None = None
    status: str = "open"
    source: str = "pos"
    customer_note: str | None = None
    payment_status: str = "unpaid"
    payment_qr_string: str | None = None
    payment_checkout_url: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    item_count: float
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    items: list[HeldItemRead]


class PublicMenuVariant(APIModel):
    id: UUID
    name: str
    price: Decimal
    available: bool = True


class PublicMenuItem(APIModel):
    id: UUID
    name: str
    description: str | None = None
    image: str | None = None
    price: Decimal
    category: str | None = None
    available: bool = True
    # When a product sells in sizes/options the customer picks one; the price and
    # availability above then describe the product as a whole, not a variant.
    variants: list[PublicMenuVariant] = Field(default_factory=list)


class PublicMenuRead(APIModel):
    store_name: str
    table_name: str | None = None
    currency_code: str
    require_online_payment: bool = False
    items: list[PublicMenuItem] = Field(default_factory=list)


class PublicOrderItemRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    modifiers: list[ModifierSelectionInput] = Field(default_factory=list, max_length=50)


class PublicOrderSubmitRequest(BaseModel):
    items: list[PublicOrderItemRequest] = Field(min_length=1, max_length=100)
    customer_note: str | None = Field(default=None, max_length=500)
    # Optional: only used to email the customer their order acknowledgement.
    customer_name: str | None = Field(default=None, max_length=180)
    customer_email: EmailStr | None = None


class StorePublicOrderSettings(BaseModel):
    enabled: bool
    token: str | None = None
    require_online_payment: bool | None = None


class PublicOrderPaymentRead(APIModel):
    held_order_id: UUID
    payment_status: str = "unpaid"
    qr_string: str | None = None
    checkout_url: str | None = None
    paid: bool = False


DINING_TABLE_STATUSES = {"available", "occupied", "reserved", "cleaning"}


def _clean_dining_status(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in DINING_TABLE_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(sorted(DINING_TABLE_STATUSES)))
    return cleaned


class DiningAreaCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    position: int = Field(default=0, ge=0, le=10000)


class DiningAreaUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    position: int | None = Field(default=None, ge=0, le=10000)


class DiningAreaRead(APIModel):
    id: UUID
    store_id: UUID
    name: str
    position: int


class DiningTableCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    area_id: UUID | None = None
    seats: int = Field(default=2, ge=1, le=100)
    status: str = "available"
    position: int = Field(default=0, ge=0, le=10000)

    @field_validator("status", mode="after")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return _clean_dining_status(value)


class DiningTableUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    area_id: UUID | None = None
    seats: int | None = Field(default=None, ge=1, le=100)
    status: str | None = None
    position: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("status", mode="after")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        return _clean_dining_status(value) if value is not None else None


class DiningTableRead(APIModel):
    id: UUID
    store_id: UUID
    area_id: UUID | None = None
    name: str
    seats: int
    status: str
    qr_token: str | None = None
    position: int
    created_at: datetime


RESERVATION_KINDS = {"reservation", "waitlist"}
RESERVATION_STATUSES = {"booked", "waiting", "seated", "cancelled", "no_show"}


def _clean_reservation_kind(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in RESERVATION_KINDS:
        raise ValueError("kind must be one of: " + ", ".join(sorted(RESERVATION_KINDS)))
    return cleaned


def _clean_reservation_status(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in RESERVATION_STATUSES:
        raise ValueError("status must be one of: " + ", ".join(sorted(RESERVATION_STATUSES)))
    return cleaned


class ReservationCreateRequest(BaseModel):
    kind: str = "reservation"
    customer_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    party_size: int = Field(default=2, ge=1, le=100)
    reserved_at: datetime | None = None
    duration_minutes: int = Field(default=90, ge=1, le=1440)
    table_id: UUID | None = None
    status: str | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("kind", mode="after")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        return _clean_reservation_kind(value)

    @field_validator("status", mode="after")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        return _clean_reservation_status(value) if value is not None else None


class ReservationUpdateRequest(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    party_size: int | None = Field(default=None, ge=1, le=100)
    reserved_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    table_id: UUID | None = None
    status: str | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("status", mode="after")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        return _clean_reservation_status(value) if value is not None else None


class ReservationRead(APIModel):
    id: UUID
    store_id: UUID
    kind: str
    customer_name: str
    phone: str | None = None
    party_size: int
    reserved_at: datetime | None = None
    duration_minutes: int
    table_id: UUID | None = None
    table_name: str | None = None
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class RefundItemRequest(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    # Identifies the exact order line when a product appears more than once (e.g.
    # two combos sharing a lead component). Preferred over product/variant.
    order_item_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    serial_numbers: list[str] = Field(default_factory=list, max_length=100)


class RefundCreateRequest(BaseModel):
    method: Literal["cash", "original"] = "original"
    reason: str | None = Field(default=None, max_length=255)
    items: list[RefundItemRequest] = Field(min_length=1, max_length=100)


class RefundItemRead(APIModel):
    product_id: UUID
    # The exact order line, so callers can tell apart lines that share a product
    # (e.g. two combos with the same lead component).
    order_item_id: UUID | None = None
    variant_id: UUID | None = None
    variant_name: str | None = None
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: float
    line_total: Decimal


class RefundRead(APIModel):
    id: UUID
    order_id: UUID
    order_number: str | None = None
    cashier_name: str | None = None
    method: str
    reason: str | None
    currency_code: str
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    item_count: float
    items: list[RefundItemRead]
    created_at: datetime


class CheckoutRead(APIModel):
    order: OrderRead
    payment: PaymentRead


class BillingCheckoutRequest(BaseModel):
    plan_code: Literal["starter", "pro"]
    billing_cycle: Literal["monthly", "semi_annual", "annual"] = "monthly"


class BillingScheduleRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=20)
    keep_store_ids: list[str] = Field(default_factory=list)
    keep_member_ids: list[str] = Field(default_factory=list)


class BillingPaymentRead(APIModel):
    id: UUID
    subscription_id: UUID
    provider: str
    status: str
    amount: Decimal
    currency_code: str
    external_id: str | None
    reference_id: str
    qr_string: str | None
    checkout_url: str | None
    created_at: datetime
    approved_at: datetime | None


class BillingCheckoutRead(APIModel):
    subscription: SubscriptionRead
    payment: BillingPaymentRead


class BillingReceiptRead(APIModel):
    id: UUID
    receipt_number: str
    company_id: UUID
    subscription_id: UUID
    billing_payment_id: UUID
    plan_code: str
    billing_cycle: str
    period_start: datetime | None
    period_end: datetime | None
    amount: Decimal
    currency_code: str
    provider: str
    paid_at: datetime
    created_at: datetime


class BillingRefundCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str | None = Field(default=None, max_length=255)
    provider_reference: str | None = Field(default=None, max_length=255)


class BillingRefundRead(APIModel):
    id: UUID
    billing_payment_id: UUID
    company_id: UUID
    amount: Decimal
    currency_code: str
    reason: str | None
    provider_reference: str | None
    refunded_by: UUID | None
    refunded_at: datetime
    created_at: datetime


class CurrencySettingsRequest(BaseModel):
    primary_code: str = Field(min_length=3, max_length=3)
    enabled_codes: list[str] = Field(min_length=1, max_length=20)

    @field_validator("primary_code", mode="after")
    @classmethod
    def uppercase_primary(cls, value: str) -> str:
        return value.upper()

    @field_validator("enabled_codes", mode="after")
    @classmethod
    def uppercase_enabled(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(code.upper() for code in value))


class CompanyCurrencyRead(APIModel):
    currency: CurrencyRead
    is_enabled: bool
    is_primary: bool


class ReservationReportRow(APIModel):
    order_id: UUID
    order_number: str
    customer_name: str | None = None
    currency_code: str
    total: Decimal
    deposit: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    pickup_at: datetime | None = None
    reservation_expires_at: datetime | None = None
    overdue: bool = False
    payment_failed: bool = False
    created_at: datetime


class ReservationReport(APIModel):
    generated_at: datetime
    open_count: int
    overdue_count: int
    deposits_held: Decimal
    balances_due: Decimal
    rows: list[ReservationReportRow]


class ReportTransactionRead(APIModel):
    id: UUID
    order_number: str
    status: str
    customer_name: str | None = None
    currency_code: str
    store_id: UUID | None = None
    store_name: str | None = None
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    tip: Decimal = Decimal("0.00")
    total: Decimal
    refunded_amount: Decimal = Decimal("0.00")
    items_count: int
    units_count: int
    payment_method: str | None = None
    created_at: datetime


class ReportSummary(APIModel):
    from_date: date
    to_date: date
    gross_sales: Decimal
    net_sales: Decimal
    tax: Decimal
    discounts: Decimal
    transactions: int
    refunds: Decimal
    average_order: Decimal
    items_sold: float = 0
    refunds_count: int = 0
    net_after_refunds: Decimal = Decimal("0.00")
    # Devices accepted from customers in the period (trade-in / buyback intake).
    trade_in_value: Decimal = Decimal("0.00")
    trade_in_count: int = 0
    # Warranty claims filed in the period and the cost borne on them.
    warranty_claim_count: int = 0
    warranty_claim_cost: Decimal = Decimal("0.00")
    # Forward-looking run rate derived from the selected period. These are
    # estimates, not actuals, and are surfaced separately in the UI.
    days_in_period: int = 1
    average_daily_net: Decimal = Decimal("0.00")
    projected_next_30_days: Decimal = Decimal("0.00")
    top_products: list[dict[str, Any]] = Field(default_factory=list)
    top_combos: list[dict[str, Any]] = Field(default_factory=list)
    daily_sales: list[dict[str, Any]] = Field(default_factory=list)
    category_sales: list[dict[str, Any]] = Field(default_factory=list)
    payment_methods: list[dict[str, Any]] = Field(default_factory=list)
    transactions_detail: list[ReportTransactionRead] = Field(default_factory=list)


class AdminUserRead(APIModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_email_verified: bool
    platform_role: str | None
    created_at: datetime
    company_count: int
    last_login: datetime | None = None


class AdminMembershipRead(APIModel):
    company_id: UUID
    company_name: str
    role: str
    status: str
    created_at: datetime


class AdminUserSessionRead(APIModel):
    id: UUID
    user_agent: str | None = None
    ip_address: str | None = None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    active: bool


class AdminCompanyRead(APIModel):
    id: UUID
    name: str
    country: str
    default_currency_code: str
    aba_payway_link: str | None = None
    aba_payway_status: str = "none"
    is_active: bool
    created_at: datetime
    store_count: int
    member_count: int
    plan_code: str | None
    subscription_status: str | None


class AdminCompanyStoreRead(APIModel):
    id: UUID
    name: str
    is_active: bool
    currency_code: str
    created_at: datetime


class AdminCompanyMemberRead(APIModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    role: str
    status: str
    created_at: datetime


class AdminStoreRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    name: str
    address: str | None
    phone: str | None
    timezone: str
    currency_code: str
    aba_payway_link: str | None = None
    aba_payway_status: str = "none"
    is_active: bool
    created_at: datetime


class AdminSubscriptionRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    plan_code: str
    billing_cycle: str
    status: str
    starts_at: datetime
    ends_at: datetime | None
    created_at: datetime


class AdminBillingPaymentRead(APIModel):
    id: UUID
    company_id: UUID | None = None
    company_name: str | None = None
    subscription_id: UUID
    plan_code: str | None = None
    billing_cycle: str | None = None
    amount: Decimal
    currency_code: str
    provider: str
    status: str
    external_id: str | None = None
    reference_id: str
    created_at: datetime
    approved_at: datetime | None = None
    fulfilled_at: datetime | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None


class AdminBillingPlanMixRead(APIModel):
    plan_code: str
    subscriptions: int
    mrr: Decimal


class AdminBillingCycleMixRead(APIModel):
    billing_cycle: str
    subscriptions: int


class AdminBillingStatusCountRead(APIModel):
    status: str
    payments: int
    amount: Decimal


class AdminBillingAnalyticsRead(APIModel):
    """Revenue and plan health for the platform's own billing."""

    mrr: Decimal = Decimal("0.00")
    arr: Decimal = Decimal("0.00")
    revenue_total: Decimal = Decimal("0.00")
    revenue_30d: Decimal = Decimal("0.00")
    refunds_total: Decimal = Decimal("0.00")
    payments_total: int = 0
    payments_paid: int = 0
    payments_pending: int = 0
    payment_success_rate: float | None = None
    active_subscriptions: int = 0
    pending_subscriptions: int = 0
    plan_mix: list[AdminBillingPlanMixRead] = Field(default_factory=list)
    cycle_mix: list[AdminBillingCycleMixRead] = Field(default_factory=list)
    status_breakdown: list[AdminBillingStatusCountRead] = Field(default_factory=list)


class AdminPlanUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=255)
    monthly_price: Decimal | None = Field(default=None, ge=0)
    max_stores: int | None = Field(default=None, ge=1, le=1000)
    max_members: int | None = Field(default=None, ge=1, le=100000)
    transaction_limit: int | None = Field(default=None, ge=0, le=100000000)
    capabilities: dict[str, bool] | None = None
    is_active: bool | None = None


class AdminPlanCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=255)
    monthly_price: Decimal = Field(default=Decimal("0.00"), ge=0)
    max_stores: int = Field(default=1, ge=1, le=1000)
    max_members: int = Field(default=1, ge=1, le=100000)
    transaction_limit: int = Field(default=0, ge=0, le=100000000)
    capabilities: dict[str, bool] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("code", mode="after")
    @classmethod
    def lowercase_code(cls, value: str) -> str:
        return value.lower()


class AdminAuditLogRead(APIModel):
    id: UUID
    actor_user_id: UUID
    actor_email: EmailStr
    action: str
    entity_type: str
    entity_id: UUID | None
    details: dict[str, Any] | None
    created_at: datetime


class AdminActivityRead(APIModel):
    """One row in the unified platform activity feed.

    Merges cross-tenant ``PlatformActivity`` events with platform-admin
    ``AuditLog`` actuations so the control room shows everything happening on
    the platform, not just admin changes.
    """

    id: UUID
    source: Literal["platform", "admin"]
    event_type: str
    title: str
    actor_email: str | None = None
    user_id: UUID | None = None
    company_id: UUID | None = None
    store_id: UUID | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    details: dict[str, Any] | None = None
    created_at: datetime


class AdminUserDetailRead(APIModel):
    """Everything the control room needs to understand one account."""

    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_email_verified: bool
    platform_role: str | None
    created_at: datetime
    last_login: datetime | None = None
    company_count: int
    memberships: list[AdminMembershipRead] = Field(default_factory=list)
    sessions: list[AdminUserSessionRead] = Field(default_factory=list)
    recent_activity: list[AdminActivityRead] = Field(default_factory=list)


class AdminCompanyDetailRead(APIModel):
    """Business health of one tenant: people, plan, money and activity."""

    id: UUID
    name: str
    country: str
    vertical: str
    default_currency_code: str
    is_active: bool
    created_at: datetime
    store_count: int
    active_store_count: int
    member_count: int
    active_member_count: int
    customer_count: int
    product_count: int
    plan_code: str | None = None
    subscription_status: str | None = None
    billing_cycle: str | None = None
    subscription_ends_at: datetime | None = None
    revenue_total: Decimal = Decimal("0.00")
    orders_total: int = 0
    gmv_total: Decimal = Decimal("0.00")
    gmv_currency: str = "USD"
    last_activity: datetime | None = None
    stores: list[AdminCompanyStoreRead] = Field(default_factory=list)
    members: list[AdminCompanyMemberRead] = Field(default_factory=list)
    recent_activity: list[AdminActivityRead] = Field(default_factory=list)


class AdminOverviewRead(APIModel):
    users: int
    active_users: int
    companies: int
    active_companies: int
    stores: int
    active_stores: int
    paid_subscriptions: int
    pending_subscriptions: int
    # Business KPIs surfaced on the overview dashboard.
    new_users_7d: int = 0
    new_users_30d: int = 0
    new_companies_30d: int = 0
    active_users_30d: int = 0
    orders_total: int = 0
    orders_30d: int = 0
    gmv_30d: Decimal = Decimal("0.00")
    gmv_currency: str = "USD"
    platform_revenue_total: Decimal = Decimal("0.00")
    platform_revenue_30d: Decimal = Decimal("0.00")
    mrr: Decimal = Decimal("0.00")


class AdminFunnelStageRead(APIModel):
    key: str
    label: str
    count: int
    conversion_from_previous: float | None = None
    conversion_from_start: float | None = None


class AdminFunnelEmailRead(APIModel):
    """How one automated drip step performed: delivered vs. moved on.

    ``advanced`` counts recipients whose first advancement event landed within
    ``window_days`` of that specific send, so a multi-step stage is not
    double-counted by its later email.
    """

    step_id: str
    audience: str
    subject: str
    delivered: int = 0
    advanced: int = 0
    rate: float | None = None
    window_days: int = 7


class AdminTimeToFirstSaleRead(APIModel):
    """How long activation takes: company creation → first paid sale.

    ``median_hours`` and ``p90_hours`` are ``None`` when no company in the
    selected window has recorded a paid sale yet.
    """

    sample: int = 0
    median_hours: float | None = None
    p90_hours: float | None = None


class AdminFunnelRead(APIModel):
    """Signup-to-first-sale activation funnel across the platform."""

    window_days: int | None = None
    stages: list[AdminFunnelStageRead] = Field(default_factory=list)
    stalled_signups: int = 0
    stalled_workspaces: int = 0
    # Time to activation, so the guided setup's impact is measurable over time.
    time_to_first_sale: AdminTimeToFirstSaleRead = Field(default_factory=AdminTimeToFirstSaleRead)
    # Per-step drip performance, so an operator can see which email moves people.
    email: list[AdminFunnelEmailRead] = Field(default_factory=list)


class AdminSalesSummaryRead(APIModel):
    orders_total: int = 0
    orders_window: int = 0
    gmv_total: Decimal = Decimal("0.00")
    gmv_window: Decimal = Decimal("0.00")
    gmv_currency: str = "USD"
    average_order_value: Decimal = Decimal("0.00")
    refunds_window: Decimal = Decimal("0.00")
    refund_count_window: int = 0


class AdminSalesRankRead(APIModel):
    id: UUID
    name: str
    orders: int
    gmv: Decimal


class AdminSalesProductRead(APIModel):
    product_name: str
    sku: str
    quantity: Decimal
    revenue: Decimal


class AdminSalesMethodRead(APIModel):
    method: str
    orders: int
    amount: Decimal


class AdminInventorySummaryRead(APIModel):
    inventory_value: Decimal = Decimal("0.00")
    low_stock_count: int = 0
    out_of_stock_count: int = 0
    active_products: int = 0


class AdminSalesAnalyticsRead(APIModel):
    """Platform-wide sales and inventory picture for a rolling window."""

    window_days: int
    summary: AdminSalesSummaryRead
    top_companies: list[AdminSalesRankRead] = Field(default_factory=list)
    top_stores: list[AdminSalesRankRead] = Field(default_factory=list)
    top_products: list[AdminSalesProductRead] = Field(default_factory=list)
    payment_methods: list[AdminSalesMethodRead] = Field(default_factory=list)
    inventory: AdminInventorySummaryRead


class AdminSearchUserRead(APIModel):
    id: UUID
    email: EmailStr
    full_name: str
    platform_role: str | None = None
    is_active: bool


class AdminSearchCompanyRead(APIModel):
    id: UUID
    name: str
    country: str
    is_active: bool
    plan_code: str | None = None


class AdminSearchStoreRead(APIModel):
    id: UUID
    name: str
    company_id: UUID
    company_name: str
    is_active: bool


class AdminSearchRead(APIModel):
    query: str
    users: list[AdminSearchUserRead] = Field(default_factory=list)
    companies: list[AdminSearchCompanyRead] = Field(default_factory=list)
    stores: list[AdminSearchStoreRead] = Field(default_factory=list)


class AdminRetentionWeekRead(APIModel):
    week_start: date
    active_stores: int = 0
    active_users: int = 0
    orders: int = 0
    gmv: Decimal = Decimal("0.00")


class AdminRetentionCohortRead(APIModel):
    cohort_start: date
    companies: int = 0
    activated: int = 0
    activation_rate: float | None = None


class AdminRetentionRead(APIModel):
    """Engagement over time and signup-cohort activation."""

    weeks: int
    gmv_currency: str = "USD"
    active_companies: int = 0
    repeat_rate: float | None = None
    average_orders_per_active_company: float = 0.0
    weekly: list[AdminRetentionWeekRead] = Field(default_factory=list)
    cohorts: list[AdminRetentionCohortRead] = Field(default_factory=list)


class AdminAttentionItemRead(APIModel):
    kind: str
    label: str
    count: int = 0
    severity: str = "warning"
    page: str | None = None


class AdminAttentionRead(APIModel):
    """Things the platform team should act on right now."""

    generated_at: datetime
    items: list[AdminAttentionItemRead] = Field(default_factory=list)


class AdminUserUpdateRequest(BaseModel):
    is_active: bool | None = None
    platform_role: Literal["admin", "super_admin"] | None = None


class AdminPaymentLinkCompanyRead(APIModel):
    id: UUID
    name: str
    aba_payway_link: str | None
    aba_payway_status: str
    store_count: int = 0
    created_at: datetime


class AdminPaymentLinkStoreRead(APIModel):
    id: UUID
    company_id: UUID
    company_name: str
    name: str
    aba_payway_link: str | None
    aba_payway_status: str
    created_at: datetime


class AdminPaymentLinksRead(APIModel):
    companies: list[AdminPaymentLinkCompanyRead] = Field(default_factory=list)
    stores: list[AdminPaymentLinkStoreRead] = Field(default_factory=list)


class AdminPaymentLinkUpdateRequest(BaseModel):
    aba_payway_status: Literal["none", "pending", "active"]


class AdminPaymentLinkStatusRead(APIModel):
    scope: str
    id: UUID
    name: str
    aba_payway_link: str | None
    aba_payway_status: str


class ChmabaPaySettingsRead(APIModel):
    mode: str
    api_url: str
    platform_store_id: str | None = None
    resolved_platform_store_id: str | None = None
    api_key_set: bool = False
    webhook_secret_set: bool = False
    api_key_preview: str | None = None
    webhook_secret_preview: str | None = None
    environment: str = "development"


class ChmabaPaySettingsUpdateRequest(BaseModel):
    mode: Literal["mock", "live"] | None = None
    api_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=300)
    webhook_secret: str | None = Field(default=None, max_length=300)
    platform_store_id: str | None = Field(default=None, max_length=80)


class ChmabaPaySecretRevealRequest(BaseModel):
    field: Literal["api_key", "webhook_secret"]


class ChmabaPaySecretRevealRead(APIModel):
    field: str
    value: str | None = None


class AISettingsRead(APIModel):
    """Effective AI drafting configuration. The key is never returned raw."""

    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key_set: bool = False
    api_key_preview: str | None = None
    providers: list[dict[str, str]] = Field(default_factory=list)
    prices: dict[str, list[float]] = Field(default_factory=dict)


class AISettingsUpdateRequest(BaseModel):
    provider: Literal["openai", "deepseek", "anthropic"] | None = None
    model: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=300)
    prices: dict[str, list[float]] | None = None


class AISecretRevealRead(APIModel):
    value: str | None = None


class AIDraftRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)
    audience: str | None = Field(default=None, max_length=40)
    tone: str | None = Field(default=None, max_length=60)


class AIDraftRead(APIModel):
    subject: str
    body_html: str
    provider: str | None = None
    model: str | None = None


class AITestRead(APIModel):
    """Outcome of a small probe request against the configured AI provider."""

    ok: bool
    provider: str | None = None
    model: str | None = None
    detail: str | None = None


class SupportArticleRead(APIModel):
    """One step-by-step help article."""

    id: str
    title: str
    verticals: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    tip: str | None = None


class SupportSectionRead(APIModel):
    """A themed group of help articles, already filtered for the caller."""

    id: str
    title: str
    blurb: str
    articles: list[SupportArticleRead] = Field(default_factory=list)


class SupportStarterPromptsRead(APIModel):
    """Suggested questions shown when the help surface opens."""

    prompts: list[str] = Field(default_factory=list)


class SupportChatMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str = Field(min_length=1, max_length=2000)


class SupportChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[SupportChatMessage] = Field(default_factory=list)
    conversation_id: UUID | None = None
    language: Literal["en", "km"] = "en"


class SupportChatRead(APIModel):
    answer: str
    provider: str | None = None
    model: str | None = None
    guide_ids: list[str] = Field(default_factory=list)
    conversation_id: UUID | None = None


class SupportMessageRead(APIModel):
    id: UUID
    role: str
    content: str
    guide_ids: list[str] | None = None
    created_at: datetime


class SupportConversationRead(APIModel):
    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class SupportConversationDetailRead(APIModel):
    id: UUID
    title: str | None = None
    messages: list[SupportMessageRead] = Field(default_factory=list)


class SupportEscalationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    topic: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    history: list[SupportChatMessage] = Field(default_factory=list)
    guide_ids: list[str] = Field(default_factory=list)
    conversation_id: UUID | None = None
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=5)


class SupportEscalationRead(APIModel):
    received: bool
    priority: bool = False
    detail: str


class SupportTicketRead(APIModel):
    id: UUID
    reference: str
    question: str
    status: str
    resolution_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class SupportTicketAttachmentRead(APIModel):
    """A reference image on a ticket or one of its messages."""

    id: UUID
    url: str
    content_type: str | None = None
    byte_size: int
    original_filename: str | None = None
    created_at: datetime


class SupportTicketMessageRead(APIModel):
    id: UUID
    author_type: str
    body: str
    created_at: datetime
    attachments: list[SupportTicketAttachmentRead] = Field(default_factory=list)


class SupportTicketDetailRead(SupportTicketRead):
    attachments: list[SupportTicketAttachmentRead] = Field(default_factory=list)
    messages: list[SupportTicketMessageRead] = Field(default_factory=list)


class SupportTicketReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=5)


class SupportTicketUpdateRequest(BaseModel):
    status: Literal["open", "pending", "resolved", "closed"]
    resolution_note: str | None = Field(default=None, max_length=1000)


class SupportTicketAiDraftRequest(BaseModel):
    """Ask the assistant to rewrite (or start) a reply for a ticket."""

    body: str = Field(default="", max_length=4000)
    instruction: str | None = Field(default=None, max_length=500)
    tone: str | None = Field(default=None, max_length=60)


class SupportTicketAiDraftRead(APIModel):
    body: str
    provider: str | None = None
    model: str | None = None


class SupportTicketAiSuggestRead(APIModel):
    """A grounded suggested reply, plus whether the help corpus covered it."""

    body: str
    matched: bool = False
    guide_ids: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None


class SupportFeedbackRequest(BaseModel):
    rating: Literal["up", "down"]
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(default="", max_length=4000)
    guide_ids: list[str] = Field(default_factory=list)


class SupportFeedbackRead(APIModel):
    received: bool


class SupportQuestionCount(APIModel):
    question: str
    total: int
    down: int


class SupportFeedbackEntry(APIModel):
    rating: str
    question: str
    created_at: datetime


class AiModelUsage(APIModel):
    provider: str
    model: str
    calls: int
    prompt_tokens: int
    completion_tokens: int


class SupportInsightsRead(APIModel):
    """Roll-up of support feedback for the platform admin."""

    window_days: int
    feedback_up: int
    feedback_down: int
    satisfaction_rate: float | None = None
    escalations: int
    top_questions: list[SupportQuestionCount] = Field(default_factory=list)
    uncovered_questions: list[SupportQuestionCount] = Field(default_factory=list)
    recent_feedback: list[SupportFeedbackEntry] = Field(default_factory=list)
    ai_calls: int = 0
    ai_prompt_tokens: int = 0
    ai_completion_tokens: int = 0
    ai_estimated_cost_usd: float = 0.0
    ai_by_model: list[AiModelUsage] = Field(default_factory=list)


class SetupChecklistStepRead(APIModel):
    id: str
    title: str
    description: str
    done: bool
    href: str | None = None
    # Optional guidance for the in-app coach: an element to spotlight and a
    # matching help article. Both are advisory.
    anchor: str | None = None
    article_id: str | None = None


class SetupChecklistRead(APIModel):
    steps: list[SetupChecklistStepRead] = Field(default_factory=list)
    completed: int
    total: int
    # The journey's end state; the coach stops when this step is done.
    goal: str = "first_sale"
    next_step_id: str | None = None


class SampleProductsClearRead(APIModel):
    """Result of removing the seeded demo products from a workspace."""

    deleted: int = 0
    deactivated: int = 0


class HelpArticleRead(APIModel):
    id: str
    section_id: str
    section_title: str
    section_title_km: str | None = None
    section_blurb: str
    section_blurb_km: str | None = None
    title: str
    title_km: str | None = None
    steps: list[str] = Field(default_factory=list)
    steps_km: list[str] | None = None
    tip: str | None = None
    tip_km: str | None = None
    verticals: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    position: int = 0
    is_active: bool = True
    updated_at: datetime


class HelpArticleCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    section_id: str = Field(min_length=1, max_length=80)
    section_title: str = Field(min_length=1, max_length=160)
    section_title_km: str | None = Field(default=None, max_length=160)
    section_blurb: str = Field(min_length=1, max_length=300)
    section_blurb_km: str | None = Field(default=None, max_length=300)
    title: str = Field(min_length=1, max_length=200)
    title_km: str | None = Field(default=None, max_length=200)
    steps: list[str] = Field(min_length=1)
    steps_km: list[str] | None = None
    tip: str | None = None
    tip_km: str | None = None
    verticals: list[str] = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    position: int = 0
    is_active: bool = True

    @field_validator("verticals")
    @classmethod
    def _check_verticals(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - COMPANY_VERTICALS)
        if unknown:
            raise ValueError(f"unknown vertical(s): {', '.join(unknown)}")
        return value

    @field_validator("roles")
    @classmethod
    def _check_roles(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - set(ALL_ROLES))
        if unknown:
            raise ValueError(f"unknown role(s): {', '.join(unknown)}")
        return value


class HelpArticleUpdateRequest(BaseModel):
    section_id: str | None = Field(default=None, min_length=1, max_length=80)
    section_title: str | None = Field(default=None, min_length=1, max_length=160)
    section_title_km: str | None = Field(default=None, max_length=160)
    section_blurb: str | None = Field(default=None, min_length=1, max_length=300)
    section_blurb_km: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    title_km: str | None = Field(default=None, max_length=200)
    steps: list[str] | None = None
    steps_km: list[str] | None = None
    tip: str | None = None
    tip_km: str | None = None
    verticals: list[str] | None = None
    roles: list[str] | None = None
    position: int | None = None
    is_active: bool | None = None

    @field_validator("verticals")
    @classmethod
    def _check_verticals(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        unknown = sorted(set(value) - COMPANY_VERTICALS)
        if unknown:
            raise ValueError(f"unknown vertical(s): {', '.join(unknown)}")
        return value

    @field_validator("roles")
    @classmethod
    def _check_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        unknown = sorted(set(value) - set(ALL_ROLES))
        if unknown:
            raise ValueError(f"unknown role(s): {', '.join(unknown)}")
        return value


class MailingRecipientRead(APIModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_email_verified: bool
    created_at: datetime
    company_count: int


class MailingAudienceSegmentRead(APIModel):
    code: str
    label: str
    count: int


class MailingAudienceRead(APIModel):
    segments: list[MailingAudienceSegmentRead] = Field(default_factory=list)
    recipients: list[MailingRecipientRead] = Field(default_factory=list)


class MailingTokenRead(APIModel):
    """A personalization placeholder the composer can insert."""

    token: str
    label: str
    sample: str


class MailingImageRead(APIModel):
    """An uploaded mailing image. ``url`` is absolute, for embedding in email."""

    url: str
    path: str
    content_type: str
    byte_size: int


class MailingDripStepRead(APIModel):
    id: str
    day_offset: int
    audience: str
    enabled: bool
    subject: str
    body_html: str


class MailingDripWindowRead(APIModel):
    start_hour: int
    end_hour: int
    weekdays_only: bool
    timezone: str


class MailingDripRead(APIModel):
    max_age_days: int
    verified_only: bool = False
    max_per_run: int = 200
    send_window: MailingDripWindowRead
    steps: list[MailingDripStepRead] = Field(default_factory=list)


class MailingDripStepRequest(BaseModel):
    id: str = Field(min_length=1, max_length=60)
    day_offset: int = Field(default=1, ge=0, le=365)
    audience: str = Field(default="no_workspace", max_length=40)
    enabled: bool = True
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1)


class MailingDripWindowRequest(BaseModel):
    start_hour: int = Field(default=8, ge=0, le=23)
    end_hour: int = Field(default=20, ge=1, le=24)
    weekdays_only: bool = True
    timezone: str = Field(default="Asia/Phnom_Penh", max_length=60)


class MailingDripUpdateRequest(BaseModel):
    max_age_days: int = Field(default=30, ge=1, le=365)
    verified_only: bool = False
    max_per_run: int = Field(default=200, ge=1, le=500)
    send_window: MailingDripWindowRequest = Field(default_factory=MailingDripWindowRequest)
    steps: list[MailingDripStepRequest] = Field(default_factory=list, max_length=20)


class MailingDripRunRead(APIModel):
    queued: int
    skipped: int
    steps: int
    window: bool = True


class MailingQueueRunRead(APIModel):
    """Outcome of draining the send queue once."""

    processed: int
    sent: int
    failed: int
    retried: int
    skipped: int
    remaining: int


class SessionSettingsRead(APIModel):
    """Platform default and maximum sign-in session length, in minutes."""

    default_ttl_minutes: int
    max_ttl_minutes: int
    absolute_max_ttl_minutes: int


class SessionSettingsUpdateRequest(BaseModel):
    default_ttl_minutes: int | None = Field(default=None, ge=1)
    max_ttl_minutes: int | None = Field(default=None, ge=1)


class MailSettingsRead(APIModel):
    """Effective outbound mail configuration. The key is never returned raw."""

    provider: str
    providers: list[dict[str, str]] = Field(default_factory=list)
    from_address: str
    from_name: str | None = None
    reply_to: str | None = None
    support_inbox: str | None = None
    api_key_set: bool = False
    api_key_preview: str | None = None
    webhook_secret_set: bool = False
    webhook_secret_preview: str | None = None
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_username_set: bool = False


class MailSettingsUpdateRequest(BaseModel):
    provider: Literal["smtp", "resend"] | None = None
    resend_api_key: str | None = Field(default=None, max_length=300)
    resend_webhook_secret: str | None = Field(default=None, max_length=300)
    from_address: EmailStr | None = None
    from_name: str | None = Field(default=None, max_length=120)
    reply_to: EmailStr | None = None
    support_inbox: EmailStr | None = None


class MailSecretRevealRequest(BaseModel):
    field: Literal["api_key", "webhook_secret"] = "api_key"


class MailSecretRevealRead(APIModel):
    field: str
    value: str | None = None


class MailTestRequest(BaseModel):
    to: EmailStr


class MailTestRead(APIModel):
    sent: bool
    provider: str
    detail: str | None = None


class EmailTemplateRead(APIModel):
    id: UUID
    name: str
    subject: str
    body_html: str
    created_at: datetime
    updated_at: datetime


class EmailTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1)


class EmailTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body_html: str | None = Field(default=None, min_length=1)


class MailingSendRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1)
    audience: str = Field(default="no_workspace", max_length=40)
    template_id: UUID | None = None
    min_age_hours: int | None = Field(default=24, ge=0, le=8760)
    max_age_days: int | None = Field(default=None, ge=0, le=3650)
    search: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=200, ge=1, le=500)
    test_email: EmailStr | None = None


class MailingSendResultRead(APIModel):
    recipients: int
    queued: int = 0
    sent: int
    failed: int
    skipped: int
    test: bool = False


class EmailSendRead(APIModel):
    id: UUID
    recipient_email: EmailStr
    subject: str
    body_html: str
    status: str
    error: str | None = None
    template_id: UUID | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    source: str = "manual"
    attempts: int = 0
    delivered_at: datetime | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_event_at: datetime | None = None
    created_at: datetime


class EmailSuppressionRead(APIModel):
    id: UUID
    email: EmailStr
    reason: str
    created_at: datetime


class AdminStatusUpdateRequest(BaseModel):
    is_active: bool


class ChmabaPayWebhookPayment(BaseModel):
    """Normalized ChmabaPay payment from a webhook ``data.payment`` block.

    Extra fields are ignored so the contract can evolve without 400s.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    status: str
    amount: Decimal | None = None
    currency: str = "USD"
    reference_id: str | None = None
    approved_at: datetime | None = None


class ChmabaPayWebhookData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    payment: ChmabaPayWebhookPayment


class ChmabaPayWebhookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    type: str | None = None
    created: datetime | None = None
    data: ChmabaPayWebhookData


RegisterResponse.model_rebuild()
TokenResponse.model_rebuild()
OrderRead.model_rebuild()


class QzSignRequest(BaseModel):
    """One QZ Tray request string to sign (see docs/native-printing.md)."""

    request: str


class QzSignRead(BaseModel):
    """The base64 RSA signature for a QZ request, plus the algorithm used."""

    signature: str
    algorithm: str = "SHA512"

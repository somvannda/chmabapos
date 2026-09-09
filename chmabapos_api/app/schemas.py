from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.features import derive_plan_marketing_features


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(APIModel):
    status: str
    service: str
    version: str
    database: str


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
    is_active: bool
    created_at: datetime


class CompanyRead(APIModel):
    id: UUID
    name: str
    country: str
    tax_id: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    default_currency_code: str
    aba_payway_link: str | None = None
    aba_payway_status: str = "none"
    created_at: datetime


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


class WorkspaceSetupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=180)
    store_name: str = Field(min_length=2, max_length=180)
    country: str = Field(default="Cambodia", min_length=2, max_length=80)
    currency_code: str = Field(default="USD", min_length=3, max_length=3)
    store_address: str | None = Field(default=None, max_length=255)
    store_phone: str | None = Field(default=None, max_length=40)
    timezone: str = Field(default="Asia/Phnom_Penh", max_length=80)
    plan_code: str = Field(default="free", max_length=20)
    billing_cycle: str = Field(default="monthly", max_length=20)

    @field_validator("currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("plan_code", mode="after")
    @classmethod
    def lowercase_plan(cls, value: str) -> str:
        return value.lower()


class WorkspaceRead(APIModel):
    company: CompanyRead
    store: StoreRead
    subscription: SubscriptionRead
    membership_role: str
    billing_payment: dict[str, Any] | None = None


class CompanyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    country: str | None = Field(default=None, min_length=2, max_length=80)
    tax_id: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    aba_payway_link: str | None = Field(default=None, max_length=255)

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
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    image: str | None = Field(default=None, max_length=10_000_000)
    opening_stock: int = Field(default=0, ge=0, le=2_000_000_000)
    reorder_point: int = Field(default=10, ge=0, le=2_000_000_000)


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    sku: str | None = Field(default=None, min_length=1, max_length=80)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    image: str | None = Field(default=None, max_length=10_000_000)
    is_active: bool | None = None


class ProductRead(APIModel):
    id: UUID
    company_id: UUID
    category_id: UUID | None
    name: str
    sku: str
    description: str | None
    image: str | None = None
    price: Decimal
    cost_price: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    category: CategoryRead | None = None
    on_hand: int = 0
    reorder_point: int = 10


class InventoryRead(APIModel):
    store_id: UUID
    product_id: UUID
    product_name: str
    sku: str
    price: Decimal
    on_hand: int
    reorder_point: int
    status: Literal["healthy", "low", "out"]
    updated_at: datetime


class InventoryAdjustRequest(BaseModel):
    quantity: int = Field(ge=0, le=2_000_000_000)
    reason: str = Field(default="manual_adjustment", min_length=1, max_length=255)


class InventoryRestockRequest(BaseModel):
    quantity: int = Field(gt=0, le=2_000_000_000)
    supplier: str | None = Field(default=None, max_length=120)
    reference: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=255)


class StockTransferItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=2_000_000_000)


class StockTransferCreateRequest(BaseModel):
    to_store_id: UUID
    items: list[StockTransferItemRequest] = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=255)


class ConsolidatedStoreReportRead(APIModel):
    store_id: UUID
    store_name: str
    transactions: int
    net_sales: Decimal
    gross_sales: Decimal
    items_sold: int
    refunds: Decimal = Decimal("0.00")
    refunds_count: int = 0
    average_order: Decimal = Decimal("0.00")


class ConsolidatedReportRead(APIModel):
    from_date: date
    to_date: date
    stores_count: int
    transactions: int
    items_sold: int
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
    role: Literal["manager", "cashier", "inventory_manager"] | None = None
    store_ids: list[UUID] | None = None
    status: Literal["active", "revoked"] | None = None


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: Literal["manager", "cashier", "inventory_manager"] = "cashier"
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


class OrderItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=10_000)


class OrderTenderRequest(BaseModel):
    method: Literal["cash", "card", "khqr"]
    currency_code: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(gt=0, max_digits=20, decimal_places=8)

    @field_validator("currency_code", mode="after")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class OrderCreateRequest(BaseModel):
    items: list[OrderItemRequest] = Field(min_length=1, max_length=100)
    payment_method: Literal["cash", "card", "khqr"] | None = None
    tenders: list[OrderTenderRequest] | None = Field(default=None, min_length=1, max_length=20)
    change_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=160)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    tip: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)

    @field_validator("items")
    @classmethod
    def require_unique_products(cls, value: list[OrderItemRequest]) -> list[OrderItemRequest]:
        product_ids = [item.product_id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product can appear only once per order")
        return value

    @field_validator("change_currency_code", mode="after")
    @classmethod
    def uppercase_change_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


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
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


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


class HeldItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=10_000)


class HeldOrderCreateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)
    items: list[HeldItemRequest] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def require_unique_products(cls, value: list[HeldItemRequest]) -> list[HeldItemRequest]:
        product_ids = [item.product_id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Each product can appear only once per held order")
        return value


class HeldItemRead(APIModel):
    product_id: UUID
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class HeldOrderRead(APIModel):
    id: UUID
    store_id: UUID
    created_by: UUID
    cashier_name: str | None = None
    label: str | None
    created_at: datetime
    item_count: int
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    items: list[HeldItemRead]


class RefundItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=10_000)


class RefundCreateRequest(BaseModel):
    method: Literal["cash", "card", "original"] = "original"
    reason: str | None = Field(default=None, max_length=255)
    items: list[RefundItemRequest] = Field(min_length=1, max_length=100)


class RefundItemRead(APIModel):
    product_id: UUID
    product_name: str
    sku: str
    unit_price: Decimal
    quantity: int
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
    item_count: int
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
    items_sold: int = 0
    refunds_count: int = 0
    net_after_refunds: Decimal = Decimal("0.00")
    top_products: list[dict[str, Any]] = Field(default_factory=list)
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


class AdminOverviewRead(APIModel):
    users: int
    active_users: int
    companies: int
    active_companies: int
    stores: int
    active_stores: int
    paid_subscriptions: int
    pending_subscriptions: int


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


class CutLuySettingsRead(APIModel):
    mode: str
    api_url: str
    store_link: str | None = None
    callback_url: str | None = None
    checkout_success_url: str | None = None
    checkout_failure_url: str | None = None
    api_key_set: bool = False
    webhook_secret_set: bool = False
    environment: str = "development"


class CutLuySettingsUpdateRequest(BaseModel):
    mode: Literal["mock", "live"] | None = None
    api_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=300)
    webhook_secret: str | None = Field(default=None, max_length=300)
    store_link: str | None = Field(default=None, max_length=500)
    callback_url: str | None = Field(default=None, max_length=500)
    checkout_success_url: str | None = Field(default=None, max_length=500)
    checkout_failure_url: str | None = Field(default=None, max_length=500)


class AdminStatusUpdateRequest(BaseModel):
    is_active: bool


class CutLuyWebhookPayment(BaseModel):
    id: str
    status: Literal["pending", "scanned", "paid", "expired", "failed"]
    amount: Decimal
    currency: str = "USD"
    reference_id: str | None = None
    approved_at: datetime | None = None


class CutLuyWebhookData(BaseModel):
    payment: CutLuyWebhookPayment


class CutLuyWebhookEvent(BaseModel):
    id: str
    type: str
    created: datetime
    data: CutLuyWebhookData


RegisterResponse.model_rebuild()
TokenResponse.model_rebuild()
OrderRead.model_rebuild()

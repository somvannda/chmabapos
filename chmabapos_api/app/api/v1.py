from __future__ import annotations

import csv
import io
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from starlette.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.billing import FREE_PLAN_CODE, is_in_force, load_entitlement, recommend_plan
from app import support_content
from pathlib import Path

from app.config import settings
from app.media import delete_by_url, upsert_media_asset
from app.schemas import held_line_key
from app.verticals import CAPABILITY_KEYS, capabilities_for, default_capabilities, default_categories, sample_products
from app.deps import SESSION_EXPIRED_DETAIL, StoreContext, get_current_membership, get_current_session_id, get_current_user, get_db, get_store_context, get_store_context_read, require_roles
from app.email import html_to_text, send_email, send_invitation_email, send_new_signin_email, send_password_changed_email, send_password_reset_email, send_store_ready_email, send_verification_email, send_welcome_email, username_for
from app.services import mail as mail_service
from app.services import mail_events
from app.services import mailing as mailing_service
from app.services import ai as ai_service
from app.services import activity as activity_service
from app.services import help_repo
from app.services import support as support_service
from app.models import (
    ApprovalRequest,
    BillingPayment,
    BillingReceipt,
    Category,
    Combo,
    ComboGroup,
    ComboGroupOption,
    ComboItem,
    Company,
    CompanyCurrency,
    Currency,
    Customer,
    DiningArea,
    DiningTable,
    Reservation,
    EmailVerificationToken,
    ExchangeRate,
    HeldOrder,
    InventoryBalance,
    Invitation,
    MediaAsset,
    Membership,
    MembershipStore,
    Modifier,
    ModifierGroup,
    Notification,
    Order,
    OrderItem,
    OrderTender,
    PasswordResetToken,
    Payment,
    Plan,
    Product,
    ProductBatch,
    ProductSerial,
    ProductSerialPhoto,
    SerialConditionHistory,
    SerialServiceTicket,
    ProductVariant,
    PurchaseOrder,
    Refund,
    Shift,
    StockMovement,
    Store,
    StoreSequence,
    Supplier,
    SupplierPrice,
    SupportTicket,
    SupportTicketMessage,
    TenantAuditLog,
    TradeIn,
    WarrantyClaim,
    WarrantyClaimEvent,
    Subscription,
    User,
    VariantInventoryBalance,
    utcnow,
)
from app.schemas import (
    BillingCheckoutRead,
    BillingCheckoutRequest,
    BillingPaymentRead,
    BillingReceiptRead,
    BillingScheduleRequest,
    CategoryCreateRequest,
    CategoryUpdateRequest,
    CategoryRead,
    CompanyCurrencyRead,
    CompanyRead,
    CompanyUpdateRequest,
    CurrencyRead,
    CurrencySettingsRequest,
    CustomerBriefRead,
    CustomerCreateRequest,
    CustomerDetailRead,
    ChmabaPayWebhookEvent,
    ComboInput,
    ComboGroupOptionRead,
    ComboGroupRead,
    ComboItemRead,
    ComboMarginRow,
    ComboRead,
    CustomerRead,
    CustomerUpdateRequest,
    ExchangeRateCreateRequest,
    ExchangeQuoteRead,
    DiningAreaCreateRequest,
    DiningAreaRead,
    DiningAreaUpdateRequest,
    DiningTableCreateRequest,
    DiningTableRead,
    ReservationCreateRequest,
    ReservationRead,
    ReservationUpdateRequest,
    DiningTableUpdateRequest,
    ExchangeRateRead,
    ExchangeRateUpdateRequest,
    GoogleAuthResponse,
    GoogleSignInRequest,
    HealthResponse,
    HeldItemRead,
    HeldOrderCreateRequest,
    HeldOrderMergeRequest,
    HeldOrderRead,
    HeldOrderSplitRequest,
    HeldOrderTransferRequest,
    HeldLineUpdateRequest,
    HeldOrderFireRequest,
    HeldOrderUpdateRequest,
    InvitationCreateRequest,
    InvitationAcceptRequest,
    InvitationRead,
    InventoryAdjustRequest,
    InventoryRead,
    InventoryRestockRequest,
    InventoryRestockSerialInput,
    InventoryVariantRead,
    LoginRequest,
    MediaAssetRead,
    MembershipRead,
    MembershipUpdateRequest,
    ModifierGroupInput,
    ModifierGroupRead,
    ModifierRead,
    NotificationRead,
    OrderCancelRequest,
    OrderCollectRequest,
    DeliveryUpdateRequest,
    OrderCreateRequest,
    OrderRead,
    OrderTenderRead,
    OrderTenderRequest,
    PaymentLinkVerificationRead,
    PaymentLinkTestScanRead,
    PaymentLinkTestScanStatusRead,
    PaymentLinkTestScanStatusRequest,
    PaymentRead,
    PlanRead,
    POSProductHit,
    POSSearchResult,
    POSSerialHit,
    PRODUCT_UNITS,
    PublicStatsRead,
    ProductBatchInput,
    ExpiringBatchRead,
    ProductBatchRead,
    ProductBatchesSetRequest,
    ProductCreateRequest,
    ProductRead,
    ProductSerialInput,
    ProductSerialRead,
    ProductSerialsSetRequest,
    ProductSerialUpdateRequest,
    TradeInCreateRequest,
    TradeInRead,
    WarrantyClaimCreateRequest,
    WarrantyClaimDecideRequest,
    WarrantyClaimEventRead,
    WarrantyClaimRead,
    WarrantyClaimResolveRequest,
    PublicMenuRead,
    PublicMenuItem,
    PublicMenuVariant,
    PublicOrderSubmitRequest,
    PublicOrderPaymentRead,
    StorePublicOrderSettings,
    SerialConditionHistoryRead,
    SerialConditionRequest,
    SerialLookupRead,
    SerialPhotoRead,
    SerialServiceTicketCreateRequest,
    SerialServiceTicketRead,
    SerialServiceTicketUpdateRequest,
    ProductUpdateRequest,
    ProductVariantRead,
    ProductVariantsSetRequest,
    SupplierPriceInput,
    SupplierPriceRead,
    SupplierPricesSetRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    ProfileUpdateRequest,
    PreferencesUpdateRequest,
    ChangePasswordRequest,
    RefundCreateRequest,
    RefundItemRequest,
    RefundItemRead,
    RefundRead,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ConsolidatedReportRead,
    ConsolidatedStoreReportRead,
    AttributeSuggestions,
    APPROVAL_ACTIONS,
    ApprovalDecisionRequest,
    ApprovalPolicy,
    ApprovalPolicyRead,
    ApprovalRequestRead,
    default_approval_policy,
    MarginReport,
    ConditionBatteryBucket,
    ConditionGradeMarginRow,
    ConditionOnHandRow,
    ConditionReport,
    ConditionSupplierRow,
    MarginReportRow,
    ReportSummary,
    ReportTransactionRead,
    ReservationReport,
    ReservationReportRow,
    ShiftCloseRequest,
    ShiftOpenRequest,
    ShiftRead,
    StoreCreateRequest,
    StoreRead,
    StoreUpdateRequest,
    SetupChecklistRead,
    SampleProductsClearRead,
    SetupChecklistStepRead,
    SessionPolicyRead,
    SessionPolicyUpdateRequest,
    StockTransferCreateRequest,
    StockTransferItemRequest,
    StockMovementRead,
    SubscriptionRead,
    SupportArticleRead,
    SupportChatRead,
    SupportChatRequest,
    SupportConversationDetailRead,
    SupportConversationRead,
    SupportEscalationRead,
    SupportEscalationRequest,
    SupportFeedbackRead,
    SupportFeedbackRequest,
    SupportMessageRead,
    SupportSectionRead,
    SupportStarterPromptsRead,
    SupportTicketRead,
    SupportTicketDetailRead,
    SupportTicketMessageRead,
    SupportTicketReplyRequest,
    SupportTicketUpdateRequest,
    TokenResponse,
    UserRead,
    VariantStockTransferRequest,
    VerifyEmailRequest,
    WorkspaceRead,
    WorkspaceSetupRequest,
)
from app.security import create_opaque_token, create_token, create_verification_code, hash_opaque_token, hash_password, verify_password
from app.services.billing_lifecycle import enforce_plan_capacity, pause_stores_over_capacity, record_capacity_actions, restore_capacity, revoke_staff_over_capacity
from app.services.google_auth import GOOGLE_AUTH_URL, exchange_authorization_code, verify_google_id_token
from app.services.orders import complete_order, ensure_transaction_available, hold_order_stock, release_order_stock, weighted_average_cost
from app.services.billing_emails import queue_billing_failure_email, queue_billing_receipt_email
from app.services.email_layout import transactional_email
from app.services.inventory import low_stock_items
from app.services.sale_emails import queue_online_order_acknowledgement, queue_refund_confirmation, queue_service_ticket_email, receipt_body
from app.services.store_notifications import daily_summary_body, low_stock_body, owner_emails, queue_public_order_note, queue_refund_note, queue_shift_closed_note, queue_team_activity
from app.services.sessions import create_session, is_new_device, revoke_session_by_token, revoke_user_sessions, rotate_session
from app.services.session_policy import load_platform_session_policy, session_cookie_max_age
from app.services.activity import record_activity
from app.services.payments.base import PaymentProviderError, ProviderPayment
from app.services.payments.chamabapay import ChmabaPayClient
from app.services.payments.registry import payment_provider_for
from app.services.platform_config import load_payment_settings, save_payment_settings
from app.services.pricing import period_end, period_total

logger = logging.getLogger("chmabapos.api.v1")


router = APIRouter()
owner_roles = Depends(require_roles("owner"))
catalog_roles = Depends(require_roles("owner", "manager", "inventory_manager"))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime:
    if value is None:
        return now_utc()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_currency(db: AsyncSession, code: str) -> Currency:
    result = await db.execute(select(Currency).where(Currency.code == code.upper(), Currency.is_active.is_(True)))
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Currency {code.upper()} is not supported")
    return currency


async def require_enabled_currency(db: AsyncSession, company_id: UUID, code: str) -> Currency:
    currency = await get_currency(db, code)
    result = await db.execute(select(CompanyCurrency).where(CompanyCurrency.company_id == company_id, CompanyCurrency.currency_code == currency.code, CompanyCurrency.is_enabled.is_(True)))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Currency {currency.code} is not enabled for this company")
    return currency


async def get_exchange_rate(db: AsyncSession, company_id: UUID, base_code: str, quote_code: str, at: datetime | None = None) -> Decimal:
    base_code = base_code.upper()
    quote_code = quote_code.upper()
    if base_code == quote_code:
        return Decimal("1")
    effective_at = as_utc(at)
    direct_result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.company_id == company_id, ExchangeRate.base_currency_code == base_code, ExchangeRate.quote_currency_code == quote_code, ExchangeRate.is_active.is_(True), ExchangeRate.effective_from <= effective_at)
        .order_by(ExchangeRate.effective_from.desc())
        .limit(1)
    )
    direct = direct_result.scalar_one_or_none()
    if direct:
        return direct.rate
    inverse_result = await db.execute(
        select(ExchangeRate)
        .where(ExchangeRate.company_id == company_id, ExchangeRate.base_currency_code == quote_code, ExchangeRate.quote_currency_code == base_code, ExchangeRate.is_active.is_(True), ExchangeRate.effective_from <= effective_at)
        .order_by(ExchangeRate.effective_from.desc())
        .limit(1)
    )
    inverse = inverse_result.scalar_one_or_none()
    if inverse:
        return (Decimal("1") / inverse.rate).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No exchange rate configured for {base_code}/{quote_code}")


def round_currency(amount: Decimal, decimal_places: int) -> Decimal:
    quantum = Decimal("1") if decimal_places == 0 else Decimal("1") / (Decimal("10") ** decimal_places)
    return amount.quantize(quantum, rounding=ROUND_HALF_UP)


def user_read(user: User) -> UserRead:
    return UserRead.model_validate(user)


def product_read(product: Product, balance: InventoryBalance | None = None, variants: list[ProductVariantRead] | None = None) -> ProductRead:
    return ProductRead(
        id=product.id,
        company_id=product.company_id,
        category_id=product.category_id,
        name=product.name,
        sku=product.sku,
        description=product.description,
        image=product.image,
        barcode=product.barcode,
        brand=product.brand,
        unit=product.unit,
        track_inventory=product.track_inventory,
        track_serials=product.track_serials,
        is_sample=product.is_sample,
        attributes=product.attributes,
        modifier_group_id=product.modifier_group_id,
        price=product.price,
        cost_price=product.cost_price,
        tax_rate=product.tax_rate,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
        category=CategoryRead.model_validate(product.category) if product.category else None,
        on_hand=balance.on_hand if balance else 0,
        reorder_point=balance.reorder_point if balance else 10,
        variants=variants or [],
    )


def variant_read(variant: ProductVariant, balance: VariantInventoryBalance | None = None) -> ProductVariantRead:
    return ProductVariantRead(
        id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        barcode=variant.barcode,
        name=variant.name,
        image=variant.image,
        price=variant.price,
        cost_price=variant.cost_price,
        attributes=variant.attributes,
        is_active=variant.is_active,
        position=variant.position,
        on_hand=balance.on_hand if balance else 0,
        reorder_point=balance.reorder_point if balance else 10,
    )


async def load_product_variants(db: AsyncSession, store_id: UUID, product: Product) -> list[ProductVariantRead]:
    variants = (await db.execute(select(ProductVariant).where(ProductVariant.product_id == product.id).order_by(ProductVariant.position, ProductVariant.name))).scalars().all()
    if not variants:
        return []
    variant_ids = [variant.id for variant in variants]
    balances_result = await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store_id, VariantInventoryBalance.variant_id.in_(variant_ids)))
    balances = {balance.variant_id: balance for balance in balances_result.scalars().all()}
    return [variant_read(variant, balances.get(variant.id)) for variant in variants]


async def get_plan(db: AsyncSession, plan_code: str) -> Plan:
    result = await db.execute(select(Plan).where(Plan.code == plan_code, Plan.is_active.is_(True)))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan not found")
    return plan


async def get_company(db: AsyncSession, company_id: UUID) -> Company:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def store_limit_block_detail(db: AsyncSession, company_id: UUID) -> str | None:
    """Return a human-friendly 403 detail if the company cannot add a store.

    Limits come from the effective plan (in-force subscription, or Free once a
    paid plan expires). A pending upgrade that raises the cap is surfaced so the
    owner knows to finish it. Returns None when adding a store is allowed.
    """
    ent = await load_entitlement(db, company_id)
    if not ent.subscription:
        return ent.denied_reason(action="add more stores")
    store_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company_id, Store.is_active.is_(True)))
    plan = ent.plan
    if plan and store_count >= plan.max_stores:
        if ent.pending and ent.pending_plan and ent.pending_plan.max_stores > plan.max_stores:
            return f"Your active {plan.name} plan allows {plan.max_stores} store(s). Complete your {ent.pending_plan.name} payment to unlock up to {ent.pending_plan.max_stores} store(s)."
        return f"{plan.name} plan allows {plan.max_stores} store(s)"
    return None


async def member_capacity_block_detail(db: AsyncSession, company_id: UUID, *, count_invited: bool, action: str) -> str | None:
    """Return a human-friendly 403 detail if the company cannot add team members."""
    ent = await load_entitlement(db, company_id)
    if not ent.subscription:
        return ent.denied_reason(action=action)
    statuses = ["active", "invited"] if count_invited else ["active"]
    member_count = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company_id, Membership.status.in_(statuses)))
    plan = ent.plan
    if plan and member_count >= plan.max_members:
        if ent.pending and ent.pending_plan and ent.pending_plan.max_members > plan.max_members:
            return f"Your active {plan.name} plan allows {plan.max_members} team member(s). Complete your {ent.pending_plan.name} payment to invite up to {ent.pending_plan.max_members}."
        return f"{plan.name} plan allows {plan.max_members} team member(s)"
    return None


async def require_plan_feature(db: AsyncSession, company_id: UUID, feature: str) -> None:
    """Raise 403 unless the effective plan includes ``feature``.

    The effective plan is the in-force paid subscription, or Free once a paid
    plan expires — an expired plan no longer unlocks paid features.
    """
    ent = await load_entitlement(db, company_id)
    if ent.plan.capabilities.get(feature):
        return
    if ent.subscription is None or ent.expired is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ent.denied_reason(action="use this feature"))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"The {ent.plan.name} plan does not include this feature. Upgrade your plan to unlock it.",
    )


_SEQUENCE_MODELS: dict[str, type] = {
    "order": Order,
    "purchase_order": PurchaseOrder,
    "warranty": WarrantyClaim,
}


async def next_document_number(db: AsyncSession, *, store_id: UUID, scope: str, prefix: str) -> str:
    """Allocate the next per-store sequential document number like ``PREFIX-000042``.

    Each (store, scope) pair keeps its own counter row in ``store_sequences`` so a
    branch's receipts/POs read CHM-000042, CHM-000043, ... independently of other
    stores. Numbers are unique per store (enforced by ``uq_order_store_number`` /
    ``uq_purchase_order_store_number``); the counter row is locked to stay safe
    under concurrent cashiers. A missing counter row is seeded one past however
    many documents the store already has.
    """
    model = _SEQUENCE_MODELS[scope]
    for _attempt in range(3):
        row = (
            await db.execute(
                select(StoreSequence)
                .where(StoreSequence.store_id == store_id, StoreSequence.scope == scope)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            try:
                async with db.begin_nested():
                    existing = await db.scalar(select(func.count()).select_from(model).where(model.store_id == store_id))
                    db.add(StoreSequence(store_id=store_id, scope=scope, next_value=int(existing or 0) + 1))
                    await db.flush()
                continue
            except IntegrityError:
                continue
        digits = str(row.next_value).rjust(max(6, len(str(row.next_value))), "0")
        number = f"{prefix}-{digits}"
        row.next_value += 1
        return number
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not allocate a document number. Try again.")


async def get_membership_stores(db: AsyncSession, membership_id: UUID) -> list[UUID]:
    result = await db.execute(select(MembershipStore.store_id).where(MembershipStore.membership_id == membership_id))
    return list(result.scalars().all())


def _aba_link_merchant_account_id(raw_link: str) -> str | None:
    """Best-effort slug from an ABA PayWay share link.

    e.g. ``https://link.payway.com.kh/ABAPAYpe518710Y`` -> ``ABAPAYpe518710Y``.
    """
    cleaned = (raw_link or "").split("?", 1)[0].rstrip("/")
    if "/" not in cleaned:
        return None
    slug = cleaned.rsplit("/", 1)[-1].strip()
    return slug or None


def aba_payway_status_message(status: str) -> tuple[bool, str]:
    """Merchant-readable outcome for a payment-link verification attempt."""
    if status == "active":
        return True, "Connection verified. KHQR checkout is live."
    if status == "pending":
        return True, "Link accepted. It is awaiting activation on the provider."
    if status == "error":
        return False, "We could not verify this ABA PayWay link. Check the link and try again."
    return False, "Save an ABA PayWay link before testing the connection."


async def sync_aba_payway_link(
    db: AsyncSession,
    obj: Company | Store,
    raw_link: str | None,
    *,
    external_id: str,
    merchant_name: str | None,
    force: bool = False,
) -> str:
    """Set a merchant's ABA PayWay link and register it with the active provider.

    With ChmabaPay active the link is validated and the merchant's ChmabaPay
    store is activated automatically (no manual review). Any other provider keeps
    the legacy ``pending`` lifecycle. Clearing the link removes the connection.
    ``force`` re-validates the saved link even when it is unchanged, which backs
    the explicit "test connection" action.
    """
    cleaned = (raw_link or "").strip() or None
    previous = getattr(obj, "aba_payway_link", None) or None
    changed = cleaned != previous
    obj.aba_payway_link = cleaned
    if not cleaned:
        obj.aba_payway_status = "none"
        obj.chamabapay_store_id = None
        return obj.aba_payway_status

    provider = await payment_provider_for(db)
    ensure_store = getattr(provider, "ensure_store", None)
    if ensure_store is None:
        if changed or force:
            obj.aba_payway_status = "pending"
        return obj.aba_payway_status

    if not changed and getattr(obj, "chamabapay_store_id", None) and not force:
        return obj.aba_payway_status

    try:
        result = await ensure_store(
            external_id,
            cleaned,
            merchant_account_id=_aba_link_merchant_account_id(cleaned),
            merchant_name=merchant_name,
            store_id=getattr(obj, "chamabapay_store_id", None),
        )
    except PaymentProviderError:
        obj.aba_payway_status = "error"
        obj.chamabapay_store_id = None
        return obj.aba_payway_status

    obj.chamabapay_store_id = result.get("id") or getattr(obj, "chamabapay_store_id", None)
    obj.aba_payway_status = "active" if (result.get("status") or "active") == "active" else "pending"
    return obj.aba_payway_status


async def active_payment_provider(db: AsyncSession) -> ChmabaPayClient:
    """Resolve the ChmabaPay provider (admin-managed settings, env fallback)."""
    cfg = await load_payment_settings(db)
    return ChmabaPayClient(
        mode=cfg.get("chamabapay_mode") or None,
        api_url=cfg.get("chamabapay_api_url") or None,
        api_key=cfg.get("chamabapay_api_key") or None,
    )


async def resolve_platform_store_id(db: AsyncSession, provider: ChmabaPayClient) -> str | None:
    """Find the ChmabaPay store that collects Chmaba plan fees.

    Uses the effective settings — a value stored by an admin overrides the env
    default (``load_payment_settings``) — otherwise auto-detects the account's
    internal store (``is_internal``) and caches it, so the platform store id is
    not something operators must supply.
    """
    configured = (await load_payment_settings(db)).get("chamabapay_platform_store_id")
    if configured:
        return configured
    try:
        stores = await provider.list_stores()
    except PaymentProviderError:
        return None
    internal = next((store for store in stores if store.get("is_internal")), None)
    store_id = (internal or {}).get("id")
    if store_id:
        await save_payment_settings(db, {"chamabapay_platform_store_id": store_id})
        return store_id
    return None


async def request_billing_payment(db: AsyncSession, amount, reference: str, metadata: dict) -> tuple[str, ProviderPayment]:
    """Create a billing payment with ChmabaPay.

    Rolls the transaction back and raises 502 on provider failure.
    """
    provider = await active_payment_provider(db)
    store_ref = await resolve_platform_store_id(db, provider)
    if not store_ref:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ChmabaPay platform store not found. Create an internal store in ChmabaPay, or set CHAMABAPAY_PLATFORM_STORE_ID.",
        )
    try:
        result = await provider.create_payment(amount, reference, idempotency_key=reference, store_ref=store_ref, metadata=metadata)
    except PaymentProviderError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return provider.name, result


async def reconcile_pending_order_payment(db: AsyncSession, order: Order) -> bool:
    """Re-check a pending KHQR order payment with the provider.

    ChmabaPay QR codes expire in about three minutes but can still settle after
    expiry ("late payment"). On read, an open KHQR payment is re-checked against
    the provider and the order completed when it reports PAID. A no-op for
    providers without reconciliation, and safe to call repeatedly.
    """
    if order.status == "paid":
        return False
    open_payments = [payment for payment in order.payments if payment.status != "paid" and payment.external_id]
    if not open_payments:
        return False
    provider = await active_payment_provider(db)
    reconcile = getattr(provider, "reconcile", None)
    if reconcile is None:
        return False
    paid = False
    changed = False
    for payment in open_payments:
        try:
            result = await reconcile(payment.external_id)
        except PaymentProviderError:
            continue
        payment_status = str(result.get("status", "")).upper()
        if payment_status == "PAID":
            payment.status = "paid"
            await complete_order(db, order.id)
            paid = True
            changed = True
            break
        if payment_status == "FAILED" and payment.status == "pending":
            payment.status = "failed"
            changed = True
    if changed:
        await db.commit()
    return paid


async def workspace_response(db: AsyncSession, membership: Membership, store: Store) -> WorkspaceRead:
    company = await get_company(db, membership.company_id)
    subscription_result = await db.execute(
        select(Subscription).where(Subscription.company_id == company.id, Subscription.status.in_(["active", "pending"])).order_by(Subscription.created_at.desc())
    )
    subscription = subscription_result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has no active plan")
    billing_payment_result = await db.execute(
        select(BillingPayment)
        .where(BillingPayment.subscription_id == subscription.id, BillingPayment.status != "paid")
        .order_by(BillingPayment.created_at.desc())
        .limit(1)
    )
    billing_payment = billing_payment_result.scalar_one_or_none()
    entitlement = await load_entitlement(db, company.id)
    return WorkspaceRead(
        company=CompanyRead.model_validate(company),
        store=StoreRead.model_validate(store),
        subscription=SubscriptionRead.model_validate(subscription),
        membership_role=membership.role,
        billing_payment=BillingPaymentRead.model_validate(billing_payment).model_dump(mode="json") if billing_payment else None,
        capabilities=list(capabilities_for(company.vertical, store.preferences)),
        capability_defaults=list(default_capabilities(company.vertical)),
        plan_features=sorted(key for key, enabled in entitlement.plan.capabilities.items() if enabled),
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    await db.execute(select(1))
    return HealthResponse(status="ok", service=settings.app_name, version="v1", database="connected")


async def issue_verification_code(db: AsyncSession, user_id: UUID) -> str:
    """Issue a fresh email confirmation code, retiring any previous one.

    Codes are six digits (one in a million) and ``token_hash`` is globally
    unique, so two users can draw the same code. Retry instead of letting the
    insert violate the unique constraint.
    """
    await db.execute(
        EmailVerificationToken.__table__.update()
        .where(EmailVerificationToken.user_id == user_id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now_utc())
    )
    for _ in range(20):
        code = create_verification_code()
        digest = hash_opaque_token(code)
        exists = (await db.execute(select(EmailVerificationToken.id).where(EmailVerificationToken.token_hash == digest))).scalar_one_or_none()
        if exists is None:
            db.add(EmailVerificationToken(user_id=user_id, token_hash=digest, expires_at=now_utc() + timedelta(hours=24)))
            return code
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not issue a confirmation code. Please try again.")


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    await db.flush()
    code = await issue_verification_code(db, user.id)
    await record_activity(db, "user.registered", user=user, details={"full_name": user.full_name})
    await db.commit()
    await db.refresh(user)
    await send_verification_email(user.email, code)
    return RegisterResponse(
        user=user_read(user),
        message="Check your email to confirm your account",
        dev_verification_token=code if settings.environment in {"development", "test"} else None,
        mailhog_url=settings.mailhog_ui_url if settings.environment in {"development", "test"} else None,
    )


@router.post("/auth/resend-verification", response_model=ResendVerificationResponse, tags=["auth"])
async def resend_verification(payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)) -> ResendVerificationResponse:
    email = payload.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or user.is_email_verified:
        # Stay vague so the endpoint cannot be used to probe which emails exist.
        return ResendVerificationResponse(message="If this email belongs to an unverified Chmaba account, a new code is on its way.")
    code = await issue_verification_code(db, user.id)
    await db.commit()
    await send_verification_email(user.email, code)
    return ResendVerificationResponse(
        message="A new confirmation code was sent to your email",
        dev_verification_token=code if settings.environment in {"development", "test"} else None,
        mailhog_url=settings.mailhog_ui_url if settings.environment in {"development", "test"} else None,
    )


@router.post("/auth/verify-email", response_model=UserRead, tags=["auth"])
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> UserRead:
    result = await db.execute(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_opaque_token(payload.token)))
    verification = result.scalar_one_or_none()
    if not verification or verification.used_at or verification.expires_at < now_utc():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token is invalid or expired")
    user_result = await db.execute(select(User).where(User.id == verification.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_email_verified = True
    verification.used_at = now_utc()
    await record_activity(db, "user.email_verified", user=user)
    await db.commit()
    await db.refresh(user)
    await send_welcome_email(user.email, user.full_name, username_for(user.email, user.full_name))
    return user_read(user)


def _refresh_cookie_samesite() -> str:
    """Return the SameSite mode the refresh cookie must use.

    The web app and the API may live on different origins. In that case a
    "lax" cookie set on the API origin is a third-party cookie and is not sent
    on the fetch to ``/auth/refresh``, which silently ends the session when the
    short access token expires. Production runs over HTTPS, so "none" (which
    requires Secure) is safe; local development stays "lax" over plain http.
    """
    return "none" if settings.environment == "production" else "lax"


def _set_refresh_cookie(response: Response, token: str, *, max_age: int | None) -> None:
    """Store the refresh token in an httpOnly cookie.

    ``max_age`` is the remaining lifetime of the session in seconds, so the
    cookie and the server-side session expire together. The cookie is httpOnly
    so JavaScript (and therefore any XSS) can never read it.
    """
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        samesite=_refresh_cookie_samesite(),
        secure=settings.environment == "production",
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect")
    if not user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Confirm your email before signing in")
    new_device = await is_new_device(db, user.id, user_agent=request.headers.get("user-agent"))
    session, refresh_token = await create_session(db, user, remember=payload.remember_me, request=request)
    await record_activity(db, "user.logged_in", user=user, details={"method": "password"})
    cookie_max_age = session_cookie_max_age(session)
    await db.commit()
    if new_device:
        # Best-effort security notice; never block the sign-in if mail is down.
        try:
            await send_new_signin_email(
                user.email,
                user.full_name,
                device=request.headers.get("user-agent"),
                ip=request.client.host if request.client else None,
            )
        except Exception:
            pass
    _set_refresh_cookie(response, refresh_token, max_age=cookie_max_age)
    return TokenResponse(
        access_token=create_token(user.id, session_id=session.id),
        expires_in=settings.jwt_access_ttl_minutes * 60,
        user=user_read(user),
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["auth"])
async def refresh_access_token(response: Response, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Rotate the refresh cookie and mint a fresh short-lived access token."""
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_EXPIRED_DETAIL)
    session, new_token = await rotate_session(db, raw, request=request)
    if session is None or new_token is None:
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_EXPIRED_DETAIL)
    user = (await db.execute(select(User).where(User.id == session.user_id, User.is_active.is_(True)))).scalar_one_or_none()
    if user is None:
        session.revoked_at = now_utc()
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=SESSION_EXPIRED_DETAIL)
    cookie_max_age = session_cookie_max_age(session)
    await db.commit()
    _set_refresh_cookie(response, new_token, max_age=cookie_max_age)
    return TokenResponse(
        access_token=create_token(user.id, session_id=session.id),
        expires_in=settings.jwt_access_ttl_minutes * 60,
        user=user_read(user),
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
async def logout(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    """Revoke the current session so its access token stops working at once."""
    raw = request.cookies.get(settings.session_cookie_name)
    if raw:
        await revoke_session_by_token(db, raw)
        await db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response


@router.post("/auth/google", response_model=GoogleAuthResponse, tags=["auth"])
async def google_signin(payload: GoogleSignInRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)) -> GoogleAuthResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    try:
        claims = verify_google_id_token(payload.id_token, settings.google_client_id)
    except Exception:
        logger.exception("Google ID token verification failed during POST /auth/google")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google sign-in failed. Please try again")
    user, is_new_user = await _google_claims_to_user(db, claims)
    session, refresh_token = await create_session(db, user, remember=payload.remember_me, request=request)
    await record_activity(db, "user.google_signup" if is_new_user else "user.google_login", user=user)
    cookie_max_age = session_cookie_max_age(session)
    await db.commit()
    await db.refresh(user)
    if is_new_user:
        await send_welcome_email(user.email, user.full_name, username_for(user.email, user.full_name))
    _set_refresh_cookie(response, refresh_token, max_age=cookie_max_age)
    return GoogleAuthResponse(
        access_token=create_token(user.id, session_id=session.id),
        expires_in=settings.jwt_access_ttl_minutes * 60,
        user=user_read(user),
        is_new_user=is_new_user,
    )


async def _google_claims_to_user(db: AsyncSession, claims: dict) -> tuple[User, bool]:
    """Find or create the merchant behind verified Google claims. Returns (user, is_new_user)."""
    sub = claims.get("sub")
    email = (claims.get("email") or "").lower().strip()
    if not sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google did not return a valid profile")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your Google account email is not verified")

    result = await db.execute(select(User).where(User.google_sub == sub))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None and user.google_sub is not None and user.google_sub != sub:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already linked to a different Google account",
            )

    is_new_user = user is None
    if is_new_user:
        full_name = (claims.get("name") or "").strip() or email.split("@", 1)[0]
        user = User(
            email=email,
            full_name=full_name[:160],
            password_hash=hash_password(secrets.token_urlsafe(48)),
            is_email_verified=True,
            google_sub=sub,
        )
        db.add(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated")
        if user.platform_role in {"admin", "super_admin"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sign in with Google is only available for merchant accounts. Admins must use email and password",
            )
        if user.google_sub is None:
            user.google_sub = sub
        if not user.is_email_verified:
            user.is_email_verified = True
    return user, is_new_user


@router.get("/auth/google/authorize", tags=["auth"])
async def google_authorize(remember: bool = Query(default=False)) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    # The OAuth round-trip has no request body, so the "remember me" choice
    # rides along in the state (which is already CSRF-bound to a cookie) and is
    # read back in the callback. ".r" = remembered, ".p" = session-only.
    state = secrets.token_urlsafe(24) + (".r" if remember else ".p")
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "state": state,
            "prompt": "select_account",
        }
    )
    redirect = RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        "chmaba_oauth_state",
        state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return redirect


@router.get("/auth/google/callback", tags=["auth"])
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    def redirect_to_login(notice: str, *, extra: dict[str, str] | None = None) -> RedirectResponse:
        params = {"google_error": notice} if extra is None else extra
        target = f"{settings.frontend_url}/login#{urlencode(params)}"
        response = RedirectResponse(target, status_code=status.HTTP_302_FOUND)
        response.delete_cookie("chmaba_oauth_state", path="/")
        return response

    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        return redirect_to_login("Google sign-in is not configured")
    expected_state = request.cookies.get("chmaba_oauth_state")
    if error or not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return redirect_to_login("Google sign-in was cancelled or failed. Please try again")
    remember = state.endswith(".r")
    try:
        token_response = await exchange_authorization_code(
            code, settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri
        )
        claims = verify_google_id_token(token_response["id_token"], settings.google_client_id)
        user, is_new_user = await _google_claims_to_user(db, claims)
        await record_activity(db, "user.google_signup" if is_new_user else "user.google_login", user=user)
        await db.commit()
        await db.refresh(user)
    except HTTPException as exc:
        await db.rollback()
        return redirect_to_login(exc.detail)
    except Exception:
        await db.rollback()
        logger.exception("Google OAuth callback failed after authorization code exchange")
        return redirect_to_login("Google sign-in failed. Please try again")
    session, refresh_token = await create_session(db, user, remember=remember, request=request)
    cookie_max_age = session_cookie_max_age(session)
    await db.commit()
    if is_new_user:
        await send_welcome_email(user.email, user.full_name, username_for(user.email, user.full_name))
    access_token = create_token(user.id, session_id=session.id)
    response = redirect_to_login(
        "",
        extra={"access_token": access_token, "is_new_user": "1" if is_new_user else "0"},
    )
    _set_refresh_cookie(response, refresh_token, max_age=cookie_max_age)
    return response


@router.post("/auth/request-password-reset", tags=["auth"])
async def request_password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email == payload.email.lower(), User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user:
        raw_token = create_opaque_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=hash_opaque_token(raw_token), expires_at=now_utc() + timedelta(minutes=30)))
        await record_activity(db, "user.password_reset_requested", user=user)
        await db.commit()
        await send_password_reset_email(user.email, raw_token)
    return {"message": "If an active account exists for this email, a reset link has been sent"}


@router.post("/auth/reset-password", tags=["auth"])
async def reset_password(payload: PasswordResetConfirmRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_opaque_token(payload.token)))
    reset_token = result.scalar_one_or_none()
    if not reset_token or reset_token.used_at or reset_token.expires_at < now_utc():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset token is invalid or expired")
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password reset token is invalid or expired")
    user.password_hash = hash_password(payload.password)
    reset_token.used_at = now_utc()
    await record_activity(db, "user.password_reset", user=user)
    await db.commit()
    # Best-effort security notice; never fail the reset if mail is down.
    try:
        await send_password_changed_email(user.email, user.full_name)
    except Exception:
        pass
    return {"message": "Password has been reset. You can sign in now"}


@router.get("/auth/me", response_model=UserRead, tags=["auth"])
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return user_read(user)


@router.post("/workspaces/setup", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED, tags=["workspace"])
async def setup_workspace(payload: WorkspaceSetupRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> WorkspaceRead:
    existing_membership = await db.execute(select(Membership).where(Membership.user_id == user.id))
    if existing_membership.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already belongs to a workspace")
    currency_result = await db.execute(select(Currency).where(Currency.code == payload.currency_code, Currency.is_active.is_(True)))
    currency = currency_result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency is not supported")
    plan = await get_plan(db, payload.plan_code)
    company = Company(name=payload.company_name.strip(), country=payload.country, default_currency_code=currency.code, vertical=payload.vertical)
    db.add(company)
    await db.flush()
    store = Store(company_id=company.id, name=payload.store_name.strip(), address=payload.store_address, phone=payload.store_phone, timezone=payload.timezone, currency_code=currency.code)
    # Turn the onboarding answers into a per-store configuration: remember what
    # the merchant told us, and seed any capability packs they opted into that
    # their business type does not already enable. Stored as a delta so the
    # defaults keep tracking ``Company.vertical`` if it changes later.
    seeded_caps = [key for key in payload.capability_answers if key in CAPABILITY_KEYS]
    default_caps = set(default_capabilities(payload.vertical))
    added_caps = [key for key in seeded_caps if key not in default_caps]
    store.preferences = {
        "onboarding_profile": {
            "store_count_band": payload.store_count_band,
            "team_size_band": payload.team_size_band,
            "capability_answers": seeded_caps,
        },
        "capability_overrides": {"added": added_caps, "removed": []},
    }
    membership = Membership(company_id=company.id, user_id=user.id, role="owner", status="active")
    db.add_all([store, membership])
    await db.flush()
    db.add(MembershipStore(membership_id=membership.id, store_id=store.id))
    db.add(CompanyCurrency(company_id=company.id, currency_code=currency.code, is_enabled=True, is_primary=True))
    subscription = Subscription(company_id=company.id, plan_code=plan.code, billing_cycle=payload.billing_cycle, status="active" if plan.code == "free" else "pending", starts_at=now_utc(), ends_at=None)
    db.add(subscription)
    await db.flush()
    for name in default_categories(payload.vertical):
        db.add(Category(company_id=company.id, name=name))
    await db.flush()
    # Seed a few demo products so the owner can try a sale before entering
    # their own catalogue. They are flagged ``is_sample`` and excluded from
    # "added a product" counts everywhere.
    category_ids = {
        category.name: category.id
        for category in (await db.execute(select(Category).where(Category.company_id == company.id))).scalars().all()
    }
    for index, sample in enumerate(sample_products(payload.vertical)):
        opening_stock = Decimal(str(sample.get("opening_stock", 0)))
        cost_price = Decimal(str(sample["cost_price"])) if sample.get("cost_price") is not None else None
        product = Product(
            company_id=company.id,
            category_id=category_ids.get(str(sample.get("category"))),
            name=str(sample["name"]),
            sku=f"SAMPLE-{payload.vertical.upper()}-{index + 1}",
            price=Decimal(str(sample["price"])),
            cost_price=cost_price,
            unit=str(sample.get("unit", "each")),
            is_sample=True,
        )
        db.add(product)
        await db.flush()
        db.add(InventoryBalance(store_id=store.id, product_id=product.id, on_hand=opening_stock, reorder_point=10))
        if opening_stock:
            db.add(
                StockMovement(
                    store_id=store.id,
                    product_id=product.id,
                    quantity=opening_stock,
                    movement_type="opening_balance",
                    reason="sample_product",
                    unit_cost=cost_price,
                    created_by=user.id,
                )
            )
    billing_payment = None
    if plan.code != "free":
        billing_cycle = payload.billing_cycle
        total_amount = period_total(plan.monthly_price, billing_cycle)
        reference = f"plan-{company.id}-{uuid.uuid4().hex}"
        metadata = {"type": "subscription", "subscription_id": str(subscription.id), "plan_code": plan.code, "billing_cycle": billing_cycle}
        provider_name, provider_payment = await request_billing_payment(db, total_amount, reference, metadata)
        metadata["provider"] = provider_name
        billing_payment = BillingPayment(subscription_id=subscription.id, company_id=company.id, plan_code=plan.code, billing_cycle=billing_cycle, provider=provider_name, amount=total_amount, currency_code=provider_payment.currency, external_id=provider_payment.id, reference_id=provider_payment.reference_id or reference, status=provider_payment.status, qr_string=provider_payment.qr_string, checkout_url=provider_payment.checkout_url, provider_metadata=metadata)
        db.add(billing_payment)
    await db.commit()
    await db.refresh(membership)
    await db.refresh(store)
    await db.refresh(subscription)
    await send_store_ready_email(user.email, user.full_name, username_for(user.email, user.full_name), store.name)
    return WorkspaceRead(company=CompanyRead.model_validate(company), store=StoreRead.model_validate(store), subscription=SubscriptionRead.model_validate(subscription), membership_role=membership.role, billing_payment=BillingPaymentRead.model_validate(billing_payment).model_dump(mode="json") if billing_payment else None, capabilities=list(capabilities_for(company.vertical, store.preferences)), capability_defaults=list(default_capabilities(company.vertical)), plan_features=sorted(key for key, enabled in plan.capabilities.items() if enabled))


@router.get("/workspaces/current", response_model=WorkspaceRead, tags=["workspace"])
async def current_workspace(membership: Membership = Depends(get_current_membership), context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> WorkspaceRead:
    return await workspace_response(db, membership, context.store)


@router.patch("/company", response_model=CompanyRead, tags=["workspace"])
async def update_company(payload: CompanyUpdateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> CompanyRead:
    company = await get_company(db, membership.company_id)
    if payload.default_currency_code:
        await require_enabled_currency(db, company.id, payload.default_currency_code)
    for field in ("name", "country", "address", "email", "phone", "tax_id", "default_currency_code", "vertical"):
        value = getattr(payload, field)
        if value is not None:
            if isinstance(value, str) and field in {"name", "country"}:
                setattr(company, field, value.strip())
            elif isinstance(value, str):
                setattr(company, field, value.strip() or None)
            else:
                setattr(company, field, value)
    if "aba_payway_link" in payload.model_fields_set:
        await sync_aba_payway_link(db, company, payload.aba_payway_link, external_id=f"company:{company.id}", merchant_name=company.name)
    await db.commit()
    await db.refresh(company)
    return CompanyRead.model_validate(company)


_FIRST_STEP_TITLES = {
    "coffee": "Add your menu items",
    "restaurant": "Add your menu items",
    "mart": "Add products with barcodes",
    "electronics": "Add products with serial numbers",
    "shop": "Add your first product",
    "general": "Add your first product",
}

# Onboarding bands that imply the merchant runs more than one store.
_MULTI_STORE_BANDS = {"2-5", "6-50", "50+"}


async def _build_setup_steps(db: AsyncSession, company: Company, store: Store) -> list[SetupChecklistStepRead]:
    """The merchant's ordered setup journey, computed from real rows and their
    onboarding answers. Shared by the checklist endpoint and the support
    assistant so the coach and the AI agree on what comes next."""
    product_count = await db.scalar(select(func.count(Product.id)).where(Product.company_id == company.id, Product.is_active.is_(True), Product.is_sample.is_(False))) or 0
    paid_orders = await db.scalar(select(func.count(Order.id)).where(Order.store_id == store.id, Order.status == "paid")) or 0
    shifts = await db.scalar(select(func.count(Shift.id)).where(Shift.store_id == store.id)) or 0
    members = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company.id, Membership.status == "active")) or 0
    payment_ready = bool(company.aba_payway_link)
    store_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company.id)) or 0
    profile = store.preferences.get("onboarding_profile") if isinstance(store.preferences, dict) else None
    store_band = str(profile.get("store_count_band") or "") if isinstance(profile, dict) else ""
    team_band = str(profile.get("team_size_band") or "") if isinstance(profile, dict) else ""

    steps = [
        SetupChecklistStepRead(
            id="first-sale",
            title="Ring up your first sale",
            description="Try the register with a sample item - it takes about 30 seconds.",
            done=paid_orders > 0,
            href="pos",
            anchor="pos-new-sale",
            article_id="getting-started.first-sale",
        ),
        SetupChecklistStepRead(
            id="add-product",
            title=_FIRST_STEP_TITLES.get(company.vertical, _FIRST_STEP_TITLES["general"]),
            description="Add your own item to replace the samples.",
            done=product_count > 0,
            href="products",
            anchor="catalog-add-product",
            article_id="getting-started.add-products",
        ),
        SetupChecklistStepRead(
            id="open-shift",
            title="Open a shift",
            description="Start a register session for accurate cash tracking.",
            done=shifts > 0,
            href="dashboard",
            anchor="pos-open-shift",
        ),
        SetupChecklistStepRead(
            id="payments",
            title="Set up KHQR payments",
            description="Add a payment link to accept QR payments.",
            done=payment_ready,
            href="settings",
            anchor="settings-khqr",
        ),
    ]
    # Branch on the onboarding answers: only a merchant who told us they run more
    # than one store sees the multi-store step.
    if store_band in _MULTI_STORE_BANDS:
        steps.append(
            SetupChecklistStepRead(
                id="add-store",
                title="Add your second store",
                description="Run another location from the same workspace.",
                done=store_count > 1,
                href="settings",
                anchor="settings-add-store",
            )
        )
    # Solo merchants are never nudged to invite anyone. Workspaces created before
    # the onboarding questions have no profile, so they keep the step as before.
    if not isinstance(profile, dict) or team_band != "1":
        steps.append(
            SetupChecklistStepRead(
                id="team",
                title="Invite a team member",
                description="Give a colleague owner, manager or cashier access.",
                done=members > 1,
                href="team",
                anchor="team-invite",
            )
        )
    return steps


@router.get("/setup/checklist", response_model=SetupChecklistRead, tags=["workspace"])
async def setup_checklist(
    context: StoreContext = Depends(get_store_context_read),
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> SetupChecklistRead:
    """A short, data-driven setup checklist for a new workspace.

    Progress is computed from real rows (products, shifts, paid orders, team,
    payment link) so it never claims a step is done when it is not. The first
    step's wording adapts to the company's business type.
    """
    company = await get_company(db, membership.company_id)
    steps = await _build_setup_steps(db, company, context.store)
    completed = sum(1 for step in steps if step.done)
    next_step_id = next((step.id for step in steps if not step.done), None)
    return SetupChecklistRead(steps=steps, completed=completed, total=len(steps), goal="first_sale", next_step_id=next_step_id)


@router.get("/support/articles", response_model=list[SupportSectionRead], tags=["support"])
async def support_articles(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
    query: str | None = Query(default=None, max_length=120),
    language: Literal["en", "km"] = Query(default="en"),
) -> list[SupportSectionRead]:
    """Help articles for the caller's business type and role, optionally searched.

    The vertical comes from the company row (never the client) so a workspace can
    only ever read guidance meant for its own business type.
    """
    company = await get_company(db, membership.company_id)
    sections = await help_repo.load_sections(db)
    if sections is None:
        # Empty table or migration not yet run: use the static fallback corpus.
        sections = support_content.SUPPORT_SECTIONS
    filtered = support_content.filter_sections(sections, vertical=company.vertical, role=membership.role, query=query, language=language)
    return [SupportSectionRead.model_validate(section) for section in filtered]


@router.get("/support/starter-prompts", response_model=SupportStarterPromptsRead, tags=["support"])
async def support_starter_prompts(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
    language: Literal["en", "km"] = Query(default="en"),
) -> SupportStarterPromptsRead:
    """Suggested questions for the caller's business type and role."""
    company = await get_company(db, membership.company_id)
    prompts = support_content.starter_prompts_for(vertical=company.vertical, role=membership.role, language=language)
    return SupportStarterPromptsRead(prompts=prompts)


@router.post("/support/chat", response_model=SupportChatRead, tags=["support"])
async def support_chat(
    payload: SupportChatRequest,
    membership: Membership = Depends(get_current_membership),
    context: StoreContext = Depends(get_store_context_read),
    db: AsyncSession = Depends(get_db),
) -> SupportChatRead:
    """Answer a how-to question, grounded in the caller's help corpus.

    The company vertical and membership role come from the database, never the
    request body, so the assistant can only be grounded in guidance the caller
    is allowed to see.
    """
    company = await get_company(db, membership.company_id)
    if not support_service.check_rate_limit(str(membership.user_id), limit=settings.support_rate_limit_per_hour):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached the support chat limit for now. Please try again later.",
        )
    try:
        conversation = await support_service.resolve_conversation(
            db,
            company_id=membership.company_id,
            user_id=membership.user_id,
            conversation_id=payload.conversation_id,
            question=payload.message,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    steps = await _build_setup_steps(db, company, context.store)
    current_step = next((step for step in steps if not step.done), None)
    journey = f"{current_step.title} - {current_step.description}" if current_step is not None else None
    try:
        result = await support_service.answer(
            db,
            question=payload.message,
            history=[turn.model_dump() for turn in payload.history],
            vertical=company.vertical,
            role=membership.role,
            store_id=context.store.id,
            company_id=membership.company_id,
            language=payload.language,
            journey=journey,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AINotConfiguredError as exc:
        # A setup problem the platform admin can fix, not an upstream failure.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await support_service.add_message(db, conversation_id=conversation.id, role="user", content=payload.message.strip())
    await support_service.add_message(db, conversation_id=conversation.id, role="assistant", content=result["answer"], guide_ids=result["guide_ids"])
    await db.commit()
    result["conversation_id"] = conversation.id
    return SupportChatRead(**result)


@router.get("/support/conversations", response_model=list[SupportConversationRead], tags=["support"])
async def support_conversations(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> list[SupportConversationRead]:
    """List the caller's support conversations, most recently active first."""
    rows = await support_service.list_conversations(db, company_id=membership.company_id, user_id=membership.user_id)
    return [SupportConversationRead.model_validate(row) for row in rows]


@router.get("/support/conversations/{conversation_id}", response_model=SupportConversationDetailRead, tags=["support"])
async def support_conversation(
    conversation_id: UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> SupportConversationDetailRead:
    """Return one conversation and its transcript, scoped to the caller."""
    found = await support_service.conversation_with_messages(
        db,
        conversation_id=conversation_id,
        company_id=membership.company_id,
        user_id=membership.user_id,
    )
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    conversation, messages = found
    return SupportConversationDetailRead(
        id=conversation.id,
        title=conversation.title,
        messages=[SupportMessageRead.model_validate(message) for message in messages],
    )


@router.delete("/support/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["support"])
async def support_conversation_delete(
    conversation_id: UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete one of the caller's conversations and its transcript."""
    deleted = await support_service.delete_conversation(
        db,
        conversation_id=conversation_id,
        company_id=membership.company_id,
        user_id=membership.user_id,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/support/chat/stream", tags=["support"])
async def support_chat_stream(
    payload: SupportChatRequest,
    membership: Membership = Depends(get_current_membership),
    context: StoreContext = Depends(get_store_context_read),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream an answer as server-sent events.

    Each event is ``data: {"delta": "..."}``; the stream ends with ``data: [DONE]``.
    Configuration, input and rate-limit checks run before streaming starts, so a
    problem is a normal JSON error rather than a truncated stream.
    """
    company = await get_company(db, membership.company_id)
    if not support_service.check_rate_limit(str(membership.user_id), limit=settings.support_rate_limit_per_hour):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached the support chat limit for now. Please try again later.",
        )
    history = [turn.model_dump() for turn in payload.history]
    steps = await _build_setup_steps(db, company, context.store)
    current_step = next((step for step in steps if not step.done), None)
    journey = f"{current_step.title} - {current_step.description}" if current_step is not None else None
    try:
        await ai_service.require_chat_config(db)
        _system, _messages, guides = support_service.build_prompt(question=payload.message, history=history, vertical=company.vertical, role=membership.role, language=payload.language, corpus=await help_repo.load_sections(db), journey=journey)
        conversation = await support_service.resolve_conversation(
            db,
            company_id=membership.company_id,
            user_id=membership.user_id,
            conversation_id=payload.conversation_id,
            question=payload.message,
        )
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    conversation_id = conversation.id
    guide_ids = [guide["id"] for guide in guides]
    # Persist the question before the answer streams, so a dropped stream still
    # leaves the user turn on record.
    await support_service.add_message(db, conversation_id=conversation_id, role="user", content=payload.message.strip())
    await db.commit()

    async def event_stream():
        yield f"data: {json.dumps({'conversation_id': str(conversation_id)})}\n\n"
        # Cite the guides so the client can show sources under the answer.
        yield f"data: {json.dumps({'guides': guides})}\n\n"
        answer = ""
        try:
            async for chunk in support_service.stream_answer(
                db,
                question=payload.message,
                history=history,
                vertical=company.vertical,
                role=membership.role,
                store_id=context.store.id,
                company_id=membership.company_id,
                language=payload.language,
                journey=journey,
            ):
                answer += chunk
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
        except ai_service.AIError as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"
        if answer:
            # A fresh session: the request's session may already be closing as
            # the streaming response finishes.
            await support_service.add_message_standalone(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                guide_ids=guide_ids,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/support/escalate", response_model=SupportEscalationRead, tags=["support"])
async def support_escalate(
    payload: SupportEscalationRequest,
    user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    context: StoreContext = Depends(get_store_context_read),
    db: AsyncSession = Depends(get_db),
) -> SupportEscalationRead:
    """Send a question to the human support team.

    Recorded as a platform activity, which the internal ops group receives, with
    enough context (store, role, transcript, and the guides that were shown) for
    the team to pick it up without asking the merchant to repeat themselves. When
    the workspace's plan includes ``priority_support`` the escalation is flagged.
    """
    company = await get_company(db, membership.company_id)
    entitlement = await load_entitlement(db, membership.company_id)
    priority = bool(entitlement.plan.capabilities.get("priority_support"))
    transcript = "\n".join(
        f"{turn.role}: {turn.content.strip()[:500]}"
        for turn in payload.history[-8:]
        if turn.content.strip()
    )
    reference = f"SUP-{uuid.uuid4().hex[:6].upper()}"
    await activity_service.record_activity(
        db,
        "support.escalated",
        user=user,
        company_id=membership.company_id,
        details={
            "company": company.name,
            "store": context.store.name,
            "role": membership.role,
            "question": payload.message.strip(),
            "topic": payload.topic.strip() if payload.topic else None,
            "priority": "yes" if priority else "no",
            "reference": reference,
            "conversation_id": str(payload.conversation_id) if payload.conversation_id else None,
            "guide_ids": ", ".join(payload.guide_ids) or None,
            "transcript": transcript or None,
        },
    )
    ticket = SupportTicket(
        reference=reference,
        company_id=membership.company_id,
        user_id=user.id,
        store_id=context.store.id,
        question=payload.message.strip()[:1000],
        status="open",
    )
    db.add(ticket)
    await db.flush()
    if transcript:
        db.add(SupportTicketMessage(ticket_id=ticket.id, author_type="system", body=transcript[:4000]))
    await db.commit()

    # Best-effort confirmation to the merchant: their request must never fail
    # because the email could not be sent.
    try:
        await send_email(
            payload.contact_email or user.email,
            f"We received your support request ({reference})",
            (
                "Thanks for contacting Chmaba support.\n\n"
                f"Reference: {reference}\n"
                + (f"Topic: {payload.topic.strip()}\n" if payload.topic else "")
                + f"Your message: {payload.message.strip()}\n\n"
                "Our team has been notified and will follow up by email. "
                "You can keep using the in-app help and assistant in the meantime."
            ),
        )
    except Exception:
        pass

    base_detail = (
        "Our priority support team has been notified and will follow up shortly."
        if priority
        else "Our support team has been notified and will follow up by email."
    )
    detail = f"{base_detail} Reference: {reference}."
    return SupportEscalationRead(received=True, priority=priority, detail=detail)


@router.get("/support/tickets", response_model=list[SupportTicketRead], tags=["support"])
async def support_tickets(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> list[SupportTicketRead]:
    """The caller's workspace support requests and their current status."""
    rows = (
        await db.execute(
            select(SupportTicket)
            .where(SupportTicket.company_id == membership.company_id)
            .order_by(SupportTicket.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [SupportTicketRead.model_validate(row) for row in rows]


@router.get("/support/tickets/{ticket_id}", response_model=SupportTicketDetailRead, tags=["support"])
async def support_ticket_detail(
    ticket_id: UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailRead:
    """One of the caller's tickets with its thread (system context hidden)."""
    row = (
        await db.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.company_id == membership.company_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    messages = (
        await db.execute(
            select(SupportTicketMessage)
            .where(SupportTicketMessage.ticket_id == ticket_id)
            .order_by(SupportTicketMessage.created_at)
        )
    ).scalars().all()
    return SupportTicketDetailRead(
        **SupportTicketRead.model_validate(row).model_dump(),
        messages=[SupportTicketMessageRead.model_validate(message) for message in messages if message.author_type != "system"],
    )


@router.post("/support/tickets/{ticket_id}/reply", response_model=SupportTicketDetailRead, tags=["support"], status_code=status.HTTP_201_CREATED)
async def support_ticket_reply(
    ticket_id: UUID,
    payload: SupportTicketReplyRequest,
    user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailRead:
    """Reply to the caller's ticket; this reopens it and notifies the team."""
    row = (
        await db.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.company_id == membership.company_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    body = payload.body.strip()
    db.add(SupportTicketMessage(ticket_id=ticket_id, author_type="merchant", author_user_id=user.id, body=body))
    row.status = "open"
    await db.commit()
    await activity_service.record_activity(db, "support.ticket_replied", user=user, company_id=membership.company_id, details={"reference": row.reference, "message": body[:300]})
    await db.commit()
    messages = (
        await db.execute(
            select(SupportTicketMessage)
            .where(SupportTicketMessage.ticket_id == ticket_id)
            .order_by(SupportTicketMessage.created_at)
        )
    ).scalars().all()
    await db.refresh(row)
    return SupportTicketDetailRead(
        **SupportTicketRead.model_validate(row).model_dump(),
        messages=[SupportTicketMessageRead.model_validate(message) for message in messages if message.author_type != "system"],
    )


@router.post("/support/feedback", response_model=SupportFeedbackRead, tags=["support"])
async def support_feedback(
    payload: SupportFeedbackRequest,
    user: User = Depends(get_current_user),
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
) -> SupportFeedbackRead:
    """Record whether an assistant answer was helpful.

    Stored as a platform activity (not forwarded to Telegram) so the team can
    find content gaps: a run of down-votes on the same question is a signal to
    improve the guide that should have answered it.
    """
    await activity_service.record_activity(
        db,
        "support.feedback",
        user=user,
        company_id=membership.company_id,
        notify=False,
        details={
            "rating": payload.rating,
            "question": payload.question.strip(),
            "guide_ids": payload.guide_ids,
        },
    )
    await db.commit()
    return SupportFeedbackRead(received=True)


async def approval_availability(db: AsyncSession, company_id: UUID) -> tuple[bool, int, bool, bool]:
    roles = (await db.execute(select(Membership.role).where(Membership.company_id == company_id, Membership.status == "active"))).scalars().all()
    team_size = len(roles)
    has_manager = any(role in ("manager", "inventory_manager") for role in roles)
    has_cashier = any(role == "cashier" for role in roles)
    # The matrix is only useful once there is someone besides the owner to watch.
    available = team_size >= 2 and any(role != "owner" for role in roles)
    return available, team_size, has_manager, has_cashier


@router.get("/approval-policy", response_model=ApprovalPolicyRead, tags=["workspace"])
async def get_approval_policy(membership: Membership = Depends(require_roles("owner", "manager")), db: AsyncSession = Depends(get_db)) -> ApprovalPolicyRead:
    company = await get_company(db, membership.company_id)
    stored = (company.settings or {}).get("approval_policy") or default_approval_policy()
    available, team_size, has_manager, has_cashier = await approval_availability(db, company.id)
    return ApprovalPolicyRead(policy=ApprovalPolicy.model_validate(stored), available=available, team_size=team_size, has_manager=has_manager, has_cashier=has_cashier)


@router.put("/approval-policy", response_model=ApprovalPolicyRead, tags=["workspace"])
async def update_approval_policy(payload: ApprovalPolicy, membership: Membership = owner_roles, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ApprovalPolicyRead:
    unknown = sorted(set(payload.rules) - set(APPROVAL_ACTIONS))
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown approval actions: {', '.join(unknown)}")
    for action, rule in payload.rules.items():
        if rule.mode != "off" and not rule.approvers:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Choose at least one approver for {action}")
    company = await get_company(db, membership.company_id)
    settings = dict(company.settings or {})
    settings["approval_policy"] = payload.model_dump(mode="json")
    company.settings = settings
    await log_audit(db, membership, None, "approval_policy_updated", "settings", entity_id=company.id, details={"enabled": payload.enabled, "rules": {action: rule.mode for action, rule in payload.rules.items()}}, user=user)
    await db.commit()
    available, team_size, has_manager, has_cashier = await approval_availability(db, company.id)
    return ApprovalPolicyRead(policy=payload, available=available, team_size=team_size, has_manager=has_manager, has_cashier=has_cashier)


@router.get("/stores", response_model=list[StoreRead], tags=["workspace"])
async def list_stores(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db), include_inactive: bool = False) -> list[StoreRead]:
    if include_inactive and membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the workspace owner can view deactivated stores")
    query = select(Store).where(Store.company_id == membership.company_id)
    if not include_inactive:
        query = query.where(Store.is_active.is_(True))
    if membership.role != "owner":
        query = query.join(MembershipStore, MembershipStore.store_id == Store.id).where(MembershipStore.membership_id == membership.id)
    query = query.order_by(Store.created_at)
    result = await db.execute(query)
    return [StoreRead.model_validate(store) for store in result.scalars().unique().all()]


@router.post("/stores", response_model=StoreRead, status_code=status.HTTP_201_CREATED, tags=["workspace"])
async def create_store(payload: StoreCreateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> StoreRead:
    company = await get_company(db, membership.company_id)
    block_detail = await store_limit_block_detail(db, company.id)
    if block_detail:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=block_detail)
    currency_result = await db.execute(select(Currency).where(Currency.code == payload.currency_code, Currency.is_active.is_(True)))
    if not currency_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Currency is not supported")
    store = Store(company_id=company.id, name=payload.name.strip(), address=payload.address, phone=payload.phone, timezone=payload.timezone, currency_code=payload.currency_code)
    db.add(store)
    await db.flush()
    db.add(MembershipStore(membership_id=membership.id, store_id=store.id))
    await db.commit()
    await db.refresh(store)
    return StoreRead.model_validate(store)


@router.patch("/stores/{store_id}", response_model=StoreRead, tags=["workspace"])
async def update_store(store_id: UUID, payload: StoreUpdateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> StoreRead:
    result = await db.execute(select(Store).where(Store.id == store_id, Store.company_id == membership.company_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    if payload.is_active is False and store.is_active:
        active_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == membership.company_id, Store.is_active.is_(True)))
        if active_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your last active store")
        open_shifts = await db.scalar(select(func.count(Shift.id)).where(Shift.store_id == store.id, Shift.status == "open"))
        if open_shifts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Close open shifts for this store before deactivating it")
    if payload.is_active is True and not store.is_active:
        ent = await load_entitlement(db, membership.company_id)
        active_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == membership.company_id, Store.is_active.is_(True)))
        if ent.plan and active_count >= ent.plan.max_stores:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{ent.plan.name} plan allows {ent.plan.max_stores} active store(s). Upgrade your plan to run more.")
    if payload.currency_code:
        await require_enabled_currency(db, membership.company_id, payload.currency_code)
    for field in ("name", "address", "phone", "timezone", "currency_code", "service_tax_rate"):
        value = getattr(payload, field)
        if value is not None:
            setattr(store, field, value.strip() if isinstance(value, str) and field == "name" else value)
    if payload.is_active is not None:
        store.is_active = payload.is_active
    if payload.preferences is not None:
        current_prefs = dict(store.preferences or {})
        current_prefs.update(payload.preferences)
        store.preferences = current_prefs
    if "aba_payway_link" in payload.model_fields_set:
        await sync_aba_payway_link(db, store, payload.aba_payway_link, external_id=f"store:{store.id}", merchant_name=store.name)
    await db.commit()
    await db.refresh(store)
    return StoreRead.model_validate(store)


@router.post("/company/payment-link/verify", response_model=PaymentLinkVerificationRead, tags=["workspace"])
async def verify_company_payment_link(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> PaymentLinkVerificationRead:
    company = await get_company(db, membership.company_id)
    status = await sync_aba_payway_link(db, company, company.aba_payway_link, external_id=f"company:{company.id}", merchant_name=company.name, force=True)
    await db.commit()
    await db.refresh(company)
    ok, message = aba_payway_status_message(status)
    return PaymentLinkVerificationRead(scope="company", id=company.id, aba_payway_link=company.aba_payway_link, aba_payway_status=status, ok=ok, message=message)


@router.post("/stores/{store_id}/payment-link/verify", response_model=PaymentLinkVerificationRead, tags=["workspace"])
async def verify_store_payment_link(store_id: UUID, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> PaymentLinkVerificationRead:
    result = await db.execute(select(Store).where(Store.id == store_id, Store.company_id == membership.company_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    status = await sync_aba_payway_link(db, store, store.aba_payway_link, external_id=f"store:{store.id}", merchant_name=store.name, force=True)
    await db.commit()
    await db.refresh(store)
    ok, message = aba_payway_status_message(status)
    return PaymentLinkVerificationRead(scope="store", id=store.id, aba_payway_link=store.aba_payway_link, aba_payway_status=status, ok=ok, message=message)


TEST_SCAN_AMOUNT = Decimal("0.10")
TEST_SCAN_REFERENCE_PREFIX = "test-scan:"


def _test_scan_reference(scope: str, entity_id: UUID) -> str:
    """Reference id that lets the async webhook find the link's owner.

    ChmabaPay echoes ``reference_id`` back on its events but not the payment
    metadata, so the scope and entity id travel inside the reference itself.
    """
    return f"{TEST_SCAN_REFERENCE_PREFIX}{scope}:{entity_id}:{uuid.uuid4().hex}"


def _parse_test_scan_reference(reference_id: str) -> tuple[str, UUID] | None:
    parts = reference_id.split(":")
    if len(parts) != 4 or parts[0] != "test-scan" or parts[1] not in {"company", "store"}:
        return None
    try:
        return parts[1], UUID(parts[2])
    except ValueError:
        return None


async def _generate_test_scan(db: AsyncSession, obj: Company | Store, link: str, scope: str, *, external_id: str, merchant_name: str | None) -> PaymentLinkTestScanRead:
    await sync_aba_payway_link(db, obj, link, external_id=external_id, merchant_name=merchant_name, force=True)
    await db.commit()
    await db.refresh(obj)
    store_ref = getattr(obj, "chamabapay_store_id", None)
    if not store_ref:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your ABA PayWay link is not active yet — verify it first")
    provider = await active_payment_provider(db)
    reference_id = _test_scan_reference(scope, obj.id)
    try:
        payment = await provider.create_payment(
            TEST_SCAN_AMOUNT,
            reference_id,
            idempotency_key=reference_id,
            store_ref=store_ref,
            metadata={"type": "test_scan", "scope": scope},
        )
    except PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return PaymentLinkTestScanRead(
        scope=scope,
        qr_string=payment.qr_string or payment.checkout_url or "",
        checkout_url=payment.checkout_url,
        payment_public_id=payment.id,
        amount=str(payment.amount),
        currency=payment.currency,
        expires_at=payment.expires_at,
    )


async def _test_scan_status(
    db: AsyncSession,
    scope: str,
    payload: PaymentLinkTestScanStatusRequest,
    *,
    obj: Company | Store | None = None,
    membership: Membership | None = None,
) -> PaymentLinkTestScanStatusRead:
    provider = await active_payment_provider(db)
    try:
        data = await provider.reconcile(payload.payment_public_id)
    except PaymentProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    status = str(data.get("status") or "UNKNOWN").upper()
    paid = status == "PAID"
    if paid and await _activate_link_from_test_scan(db, scope, obj, membership, payload.payment_public_id):
        await db.commit()
    return PaymentLinkTestScanStatusRead(scope=scope, status=status, paid=paid, aba_payway_status=getattr(obj, "aba_payway_status", None))


async def _activate_link_from_test_scan(
    db: AsyncSession,
    scope: str,
    obj: Company | Store | None,
    membership: Membership | None,
    payment_public_id: str,
) -> bool:
    """Activate a link from the synchronous poll while the merchant watches."""
    actor = await db.get(User, membership.user_id) if membership is not None else None
    return await _activate_pending_link(db, scope, obj, membership=membership, actor=actor, via="test_scan", payment_public_id=payment_public_id)


async def _activate_link_from_test_scan_reference(db: AsyncSession, reference_id: str, payment_public_id: str) -> bool:
    """Activate a link from a settled test-scan webhook (the merchant may be gone).

    Runs for events whose ``reference_id`` carries a test-scan scope and entity
    (see ``_test_scan_reference``). Attribution falls back to the workspace owner
    because a webhook has no acting user.
    """
    parsed = _parse_test_scan_reference(reference_id)
    if parsed is None:
        return False
    scope, entity_id = parsed
    obj: Company | Store | None = await db.get(Company, entity_id) if scope == "company" else await db.get(Store, entity_id)
    if obj is None:
        return False
    company_id = obj.id if scope == "company" else obj.company_id
    membership, actor = await _owner_actor(db, company_id)
    return await _activate_pending_link(db, scope, obj, membership=membership, actor=actor, via="test_scan_webhook", payment_public_id=payment_public_id)


async def _owner_actor(db: AsyncSession, company_id: UUID) -> tuple[Membership | None, User | None]:
    """The acting owner for an automatic (no-user) activation, if one exists."""
    result = await db.execute(select(Membership).where(Membership.company_id == company_id, Membership.role == "owner", Membership.status == "active").order_by(Membership.created_at))
    membership = result.scalars().first()
    if membership is None:
        membership = (await db.execute(select(Membership).where(Membership.company_id == company_id).order_by(Membership.created_at))).scalars().first()
    if membership is None:
        return None, None
    return membership, await db.get(User, membership.user_id)


async def _activate_pending_link(
    db: AsyncSession,
    scope: str,
    obj: Company | Store | None,
    *,
    membership: Membership | None,
    actor: User | None,
    via: str,
    payment_public_id: str | None,
) -> bool:
    """Promote a merchant link to ``active`` once a $0.10 test payment settles.

    A settled test scan proves the ABA PayWay link works end to end, so it no
    longer needs platform review: the link becomes ``active`` and the POS can
    start generating KHQR payments for it. Idempotent — an already-active link,
    or one with no saved ABA URL, is left untouched. Returns whether a change
    was staged for commit.
    """
    if obj is None or not getattr(obj, "aba_payway_link", None) or getattr(obj, "aba_payway_status", None) == "active":
        return False
    obj.aba_payway_status = "active"
    if membership is not None and actor is not None:
        await log_audit(
            db,
            membership,
            obj.id if scope == "store" else None,
            "payment_link_activated",
            scope,
            obj.id,
            {"via": via, "payment_public_id": payment_public_id},
            actor,
        )
    return True


@router.post("/company/payment-link/test-scan", response_model=PaymentLinkTestScanRead, tags=["workspace"])
async def test_scan_company_payment_link(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> PaymentLinkTestScanRead:
    company = await get_company(db, membership.company_id)
    if not company.aba_payway_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a company ABA PayWay link before running a test payment")
    return await _generate_test_scan(db, company, company.aba_payway_link, "company", external_id=f"company:{company.id}", merchant_name=company.name)


@router.post("/company/payment-link/test-scan/status", response_model=PaymentLinkTestScanStatusRead, tags=["workspace"])
async def test_scan_company_payment_link_status(payload: PaymentLinkTestScanStatusRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> PaymentLinkTestScanStatusRead:
    company = await get_company(db, membership.company_id)
    return await _test_scan_status(db, "company", payload, obj=company, membership=membership)


@router.post("/stores/{store_id}/payment-link/test-scan", response_model=PaymentLinkTestScanRead, tags=["workspace"])
async def test_scan_store_payment_link(store_id: UUID, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> PaymentLinkTestScanRead:
    result = await db.execute(select(Store).where(Store.id == store_id, Store.company_id == membership.company_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    if not store.aba_payway_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Save a store ABA PayWay link before running a test payment")
    return await _generate_test_scan(db, store, store.aba_payway_link, "store", external_id=f"store:{store.id}", merchant_name=store.name)


@router.post("/stores/{store_id}/payment-link/test-scan/status", response_model=PaymentLinkTestScanStatusRead, tags=["workspace"])
async def test_scan_store_payment_link_status(store_id: UUID, payload: PaymentLinkTestScanStatusRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> PaymentLinkTestScanStatusRead:
    result = await db.execute(select(Store).where(Store.id == store_id, Store.company_id == membership.company_id))
    store = result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return await _test_scan_status(db, "store", payload, obj=store, membership=membership)


@router.get("/plans", response_model=list[PlanRead], tags=["billing"])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanRead]:
    result = await db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.monthly_price))
    return [PlanRead.model_validate(plan) for plan in result.scalars().all()]


@router.get("/plans/recommended", response_model=PlanRead, tags=["billing"])
async def recommended_plan(
    stores: str = Query(default="1"),
    team: str = Query(default="1"),
    db: AsyncSession = Depends(get_db),
) -> PlanRead:
    """The cheapest active plan whose limits cover the onboarding answers.

    ``stores`` and ``team`` are band keys (``1``, ``2-5``, ``6-50``, ``50+`` and
    ``1``, ``2-10``, ``11-99``, ``100+``); unknown values fall back to ``1``.
    Public, so the signup plan picker can call it before an account exists.
    """
    result = await db.execute(select(Plan).where(Plan.is_active.is_(True)))
    chosen = recommend_plan(list(result.scalars().all()), stores, team)
    if chosen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No plans are available")
    return PlanRead.model_validate(chosen)


@router.get("/public/stats", response_model=PublicStatsRead, tags=["public"])
async def public_stats(response: Response, db: AsyncSession = Depends(get_db)) -> PublicStatsRead:
    """Unauthenticated aggregate figures for the marketing homepage.

    Served without caching so the numbers are always current; the frontend
    reads it once per visit. ``value_processed`` is net of refunds and reported
    for the single busiest currency so amounts in different currencies are never
    added together.
    """
    active_stores = await db.scalar(select(func.count(Store.id)).where(Store.is_active.is_(True))) or 0
    active_products = await db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True), Product.is_sample.is_(False))) or 0
    completed_sales = await db.scalar(select(func.count(Order.id)).where(Order.status == "paid")) or 0

    gross_rows = (await db.execute(select(Order.currency_code, func.coalesce(func.sum(Order.total), 0)).where(Order.status == "paid").group_by(Order.currency_code))).all()
    currency_code = "USD"
    gross = Decimal("0")
    for code, amount in gross_rows:
        amount = Decimal(amount or 0)
        if amount > gross:
            gross = amount
            currency_code = code
    refunds = await db.scalar(select(func.coalesce(func.sum(Refund.total), 0)).where(Refund.currency_code == currency_code)) or Decimal("0")
    value_processed = (gross - Decimal(refunds)).quantize(Decimal("0.01"))

    response.headers["Cache-Control"] = "no-store"
    return PublicStatsRead(
        active_stores=int(active_stores),
        completed_sales=int(completed_sales),
        value_processed=value_processed,
        currency_code=currency_code,
        active_products=int(active_products),
    )



@router.get("/currencies", response_model=list[CurrencyRead], tags=["settings"])
async def list_currencies(db: AsyncSession = Depends(get_db)) -> list[CurrencyRead]:
    result = await db.execute(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.code))
    return [CurrencyRead.model_validate(currency) for currency in result.scalars().all()]


@router.get("/settings/currencies", response_model=list[CompanyCurrencyRead], tags=["settings"])
async def company_currencies(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[CompanyCurrencyRead]:
    result = await db.execute(select(CompanyCurrency, Currency).join(Currency, Currency.code == CompanyCurrency.currency_code).where(CompanyCurrency.company_id == membership.company_id).order_by(CompanyCurrency.is_primary.desc(), Currency.code))
    return [CompanyCurrencyRead(currency=CurrencyRead.model_validate(currency), is_enabled=link.is_enabled, is_primary=link.is_primary) for link, currency in result.all()]


@router.put("/settings/currencies", response_model=list[CompanyCurrencyRead], tags=["settings"])
async def update_company_currencies(payload: CurrencySettingsRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> list[CompanyCurrencyRead]:
    if payload.primary_code not in payload.enabled_codes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary currency must be enabled")
    if len(payload.enabled_codes) > 1:
        await require_plan_feature(db, membership.company_id, "multi_currency")
    result = await db.execute(select(Currency).where(Currency.code.in_(payload.enabled_codes), Currency.is_active.is_(True)))
    currencies = result.scalars().all()
    if len(currencies) != len(payload.enabled_codes):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more currencies are not supported")
    links_result = await db.execute(select(CompanyCurrency).where(CompanyCurrency.company_id == membership.company_id))
    links = {link.currency_code: link for link in links_result.scalars().all()}
    for code in payload.enabled_codes:
        link = links.get(code)
        if not link:
            link = CompanyCurrency(company_id=membership.company_id, currency_code=code)
            db.add(link)
        link.is_enabled = True
        link.is_primary = code == payload.primary_code
    for code, link in links.items():
        if code not in payload.enabled_codes:
            link.is_enabled = False
            link.is_primary = False
    company = await get_company(db, membership.company_id)
    company.default_currency_code = payload.primary_code
    await db.commit()
    return await company_currencies(membership, db)


def _company_session_override(company: Company, max_ttl_minutes: int) -> int | None:
    """The company's configured session length, clamped to the platform max."""
    raw = dict(company.settings or {}).get("session_ttl_minutes")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return min(value, max_ttl_minutes)


@router.get("/settings/session", response_model=SessionPolicyRead, tags=["settings"])
async def get_session_policy(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> SessionPolicyRead:
    """The company's sign-in session length plus the platform default and cap."""
    default_ttl, max_ttl = await load_platform_session_policy(db)
    company = await get_company(db, membership.company_id)
    return SessionPolicyRead(
        company_ttl_minutes=_company_session_override(company, max_ttl),
        default_ttl_minutes=default_ttl,
        max_ttl_minutes=max_ttl,
    )


@router.put("/settings/session", response_model=SessionPolicyRead, tags=["settings"])
async def update_session_policy(payload: SessionPolicyUpdateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> SessionPolicyRead:
    """Set (or clear) how long a normal sign-in lasts for this company's team.

    The value lives in ``Company.settings`` and is bounded by the platform
    maximum; clearing it falls back to the platform default.
    """
    default_ttl, max_ttl = await load_platform_session_policy(db)
    company = await get_company(db, membership.company_id)
    settings_bag = dict(company.settings or {})
    if payload.ttl_minutes is None:
        settings_bag.pop("session_ttl_minutes", None)
    else:
        if payload.ttl_minutes > max_ttl:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Session length cannot exceed {max_ttl} minutes")
        settings_bag["session_ttl_minutes"] = payload.ttl_minutes
    company.settings = settings_bag
    await db.commit()
    return SessionPolicyRead(
        company_ttl_minutes=_company_session_override(company, max_ttl),
        default_ttl_minutes=default_ttl,
        max_ttl_minutes=max_ttl,
    )


@router.get("/exchange-rates", response_model=list[ExchangeRateRead], tags=["settings"])
async def list_exchange_rates(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
    base_currency_code: str | None = Query(default=None, min_length=3, max_length=3),
    quote_currency_code: str | None = Query(default=None, min_length=3, max_length=3),
    active_only: bool = True,
) -> list[ExchangeRateRead]:
    query = select(ExchangeRate).where(ExchangeRate.company_id == membership.company_id)
    if active_only:
        query = query.where(ExchangeRate.is_active.is_(True))
    if base_currency_code:
        query = query.where(ExchangeRate.base_currency_code == base_currency_code.upper())
    if quote_currency_code:
        query = query.where(ExchangeRate.quote_currency_code == quote_currency_code.upper())
    result = await db.execute(query.order_by(ExchangeRate.base_currency_code, ExchangeRate.quote_currency_code, ExchangeRate.effective_from.desc()))
    return [ExchangeRateRead.model_validate(rate) for rate in result.scalars().all()]


@router.get("/exchange-rates/quote", response_model=ExchangeQuoteRead, tags=["settings"])
async def quote_exchange_rate(
    base_currency_code: str = Query(min_length=3, max_length=3),
    quote_currency_code: str = Query(min_length=3, max_length=3),
    amount: Decimal = Query(gt=0, max_digits=20, decimal_places=8),
    effective_at: datetime | None = None,
    context: StoreContext = Depends(get_store_context),
    db: AsyncSession = Depends(get_db),
) -> ExchangeQuoteRead:
    base_currency = await require_enabled_currency(db, context.membership.company_id, base_currency_code)
    quote_currency = await require_enabled_currency(db, context.membership.company_id, quote_currency_code)
    if amount != round_currency(amount, base_currency.decimal_places):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Amount must use {base_currency.decimal_places} decimal place(s) for {base_currency.code}")
    rate = await get_exchange_rate(db, context.membership.company_id, base_currency.code, quote_currency.code, effective_at)
    return ExchangeQuoteRead(
        base_currency_code=base_currency.code,
        quote_currency_code=quote_currency.code,
        rate=rate,
        amount=amount,
        converted_amount=round_currency(amount * rate, quote_currency.decimal_places),
        quote_decimal_places=quote_currency.decimal_places,
    )


@router.post("/exchange-rates", response_model=ExchangeRateRead, status_code=status.HTTP_201_CREATED, tags=["settings"])
async def create_exchange_rate(payload: ExchangeRateCreateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> ExchangeRateRead:
    await require_plan_feature(db, membership.company_id, "multi_currency")
    if payload.base_currency_code == payload.quote_currency_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Base and quote currencies must be different")
    await require_enabled_currency(db, membership.company_id, payload.base_currency_code)
    await require_enabled_currency(db, membership.company_id, payload.quote_currency_code)
    exchange_rate = ExchangeRate(
        company_id=membership.company_id,
        base_currency_code=payload.base_currency_code,
        quote_currency_code=payload.quote_currency_code,
        rate=payload.rate,
        effective_from=as_utc(payload.effective_from),
        created_by=membership.user_id,
    )
    db.add(exchange_rate)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An exchange rate already exists for this pair and effective time")
    await db.refresh(exchange_rate)
    return ExchangeRateRead.model_validate(exchange_rate)


@router.patch("/exchange-rates/{exchange_rate_id}", response_model=ExchangeRateRead, tags=["settings"])
async def update_exchange_rate(exchange_rate_id: UUID, payload: ExchangeRateUpdateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> ExchangeRateRead:
    await require_plan_feature(db, membership.company_id, "multi_currency")
    result = await db.execute(select(ExchangeRate).where(ExchangeRate.id == exchange_rate_id, ExchangeRate.company_id == membership.company_id))
    exchange_rate = result.scalar_one_or_none()
    if not exchange_rate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exchange rate not found")
    exchange_rate.is_active = payload.is_active
    await db.commit()
    await db.refresh(exchange_rate)
    return ExchangeRateRead.model_validate(exchange_rate)


# ---------------------------------------------------------------------------
# Dining floor (restaurant / table management)
# ---------------------------------------------------------------------------


@router.get("/dining/areas", response_model=list[DiningAreaRead], tags=["dining"])
async def list_dining_areas(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db)) -> list[DiningAreaRead]:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    result = await db.execute(select(DiningArea).where(DiningArea.store_id == context.store.id).order_by(DiningArea.position, DiningArea.name))
    return [DiningAreaRead.model_validate(area) for area in result.scalars().all()]


@router.post("/dining/areas", response_model=DiningAreaRead, status_code=status.HTTP_201_CREATED, tags=["dining"])
async def create_dining_area(payload: DiningAreaCreateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> DiningAreaRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    area = DiningArea(store_id=context.store.id, name=payload.name.strip(), position=payload.position)
    db.add(area)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An area with that name already exists")
    await db.refresh(area)
    return DiningAreaRead.model_validate(area)


@router.patch("/dining/areas/{area_id}", response_model=DiningAreaRead, tags=["dining"])
async def update_dining_area(area_id: UUID, payload: DiningAreaUpdateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> DiningAreaRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    area = (await db.execute(select(DiningArea).where(DiningArea.id == area_id, DiningArea.store_id == context.store.id))).scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    if payload.name is not None:
        area.name = payload.name.strip()
    if payload.position is not None:
        area.position = payload.position
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An area with that name already exists")
    await db.refresh(area)
    return DiningAreaRead.model_validate(area)


@router.delete("/dining/areas/{area_id}", tags=["dining"])
async def delete_dining_area(area_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    area = (await db.execute(select(DiningArea).where(DiningArea.id == area_id, DiningArea.store_id == context.store.id))).scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Area not found")
    # Tables survive: the FK is ON DELETE SET NULL, so they fall into the
    # implicit "Main" group rather than being deleted with the area.
    await db.delete(area)
    await db.commit()
    return {"ok": True}


async def _dining_area_for_store(db: AsyncSession, area_id: UUID | None, store_id: UUID) -> None:
    if not area_id:
        return
    area = (await db.execute(select(DiningArea).where(DiningArea.id == area_id, DiningArea.store_id == store_id))).scalar_one_or_none()
    if not area:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Area not found")


@router.get("/dining/tables", response_model=list[DiningTableRead], tags=["dining"])
async def list_dining_tables(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db)) -> list[DiningTableRead]:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    result = await db.execute(select(DiningTable).where(DiningTable.store_id == context.store.id).order_by(DiningTable.position, DiningTable.name))
    return [DiningTableRead.model_validate(table) for table in result.scalars().all()]


@router.post("/dining/tables", response_model=DiningTableRead, status_code=status.HTTP_201_CREATED, tags=["dining"])
async def create_dining_table(payload: DiningTableCreateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> DiningTableRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    await _dining_area_for_store(db, payload.area_id, context.store.id)
    table = DiningTable(store_id=context.store.id, area_id=payload.area_id, name=payload.name.strip(), seats=payload.seats, status=payload.status, position=payload.position, qr_token=uuid.uuid4().hex)
    db.add(table)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A table with that name already exists")
    await db.refresh(table)
    return DiningTableRead.model_validate(table)


@router.patch("/dining/tables/{table_id}", response_model=DiningTableRead, tags=["dining"])
async def update_dining_table(table_id: UUID, payload: DiningTableUpdateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> DiningTableRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    table = (await db.execute(select(DiningTable).where(DiningTable.id == table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    if payload.name is not None:
        table.name = payload.name.strip()
    if "area_id" in payload.model_fields_set:
        await _dining_area_for_store(db, payload.area_id, context.store.id)
        table.area_id = payload.area_id
    if payload.seats is not None:
        table.seats = payload.seats
    if payload.status is not None:
        table.status = payload.status
    if payload.position is not None:
        table.position = payload.position
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A table with that name already exists")
    await db.refresh(table)
    return DiningTableRead.model_validate(table)


@router.delete("/dining/tables/{table_id}", tags=["dining"])
async def delete_dining_table(table_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    table = (await db.execute(select(DiningTable).where(DiningTable.id == table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    await db.delete(table)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Reservations & waitlist (restaurant)
# ---------------------------------------------------------------------------


def reservation_read(reservation: Reservation, table_name: str | None = None) -> ReservationRead:
    return ReservationRead(
        id=reservation.id,
        store_id=reservation.store_id,
        kind=reservation.kind,
        customer_name=reservation.customer_name,
        phone=reservation.phone,
        party_size=reservation.party_size,
        reserved_at=reservation.reserved_at,
        duration_minutes=reservation.duration_minutes,
        table_id=reservation.table_id,
        table_name=table_name,
        status=reservation.status,
        notes=reservation.notes,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
    )


async def _table_name_map(db: AsyncSession, store_id: UUID, table_ids: set[UUID]) -> dict[UUID, str]:
    if not table_ids:
        return {}
    rows = (await db.execute(select(DiningTable.id, DiningTable.name).where(DiningTable.store_id == store_id, DiningTable.id.in_(table_ids)))).all()
    return {row[0]: row[1] for row in rows}


async def _require_store_table(db: AsyncSession, store_id: UUID, table_id: UUID | None) -> None:
    if table_id is None:
        return
    table = (await db.execute(select(DiningTable).where(DiningTable.id == table_id, DiningTable.store_id == store_id))).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")


async def _set_table_status(db: AsyncSession, store_id: UUID, table_id: UUID | None, new_status: str, *, only_if: str | None = None) -> None:
    if table_id is None:
        return
    table = (await db.execute(select(DiningTable).where(DiningTable.id == table_id, DiningTable.store_id == store_id))).scalar_one_or_none()
    if table and (only_if is None or table.status == only_if):
        table.status = new_status


@router.get("/dining/reservations", response_model=list[ReservationRead], tags=["dining"])
async def list_reservations(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db), day: date | None = Query(default=None, alias="date"), status_filter: str | None = Query(default=None, alias="status")) -> list[ReservationRead]:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    statement = select(Reservation).where(Reservation.store_id == context.store.id)
    if day is not None:
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        statement = statement.where(Reservation.reserved_at >= start, Reservation.reserved_at < start + timedelta(days=1))
    if status_filter:
        statement = statement.where(Reservation.status == status_filter)
    statement = statement.order_by(Reservation.reserved_at.asc().nulls_last(), Reservation.created_at.asc())
    rows = (await db.execute(statement)).scalars().all()
    names = await _table_name_map(db, context.store.id, {row.table_id for row in rows if row.table_id})
    return [reservation_read(row, names.get(row.table_id)) for row in rows]


@router.post("/dining/reservations", response_model=ReservationRead, status_code=status.HTTP_201_CREATED, tags=["dining"])
async def create_reservation(payload: ReservationCreateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> ReservationRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    await _require_store_table(db, context.store.id, payload.table_id)
    reservation = Reservation(
        store_id=context.store.id,
        kind=payload.kind,
        customer_name=payload.customer_name.strip(),
        phone=(payload.phone or "").strip() or None,
        party_size=payload.party_size,
        reserved_at=payload.reserved_at,
        duration_minutes=payload.duration_minutes,
        table_id=payload.table_id,
        status=payload.status or ("waiting" if payload.kind == "waitlist" else "booked"),
        notes=(payload.notes or "").strip() or None,
        created_by=context.user.id,
    )
    db.add(reservation)
    await db.commit()
    await db.refresh(reservation)
    names = await _table_name_map(db, context.store.id, {reservation.table_id} if reservation.table_id else set())
    return reservation_read(reservation, names.get(reservation.table_id))


@router.patch("/dining/reservations/{reservation_id}", response_model=ReservationRead, tags=["dining"])
async def update_reservation(reservation_id: UUID, payload: ReservationUpdateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> ReservationRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    reservation = (await db.execute(select(Reservation).where(Reservation.id == reservation_id, Reservation.store_id == context.store.id))).scalar_one_or_none()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    if payload.table_id is not None:
        await _require_store_table(db, context.store.id, payload.table_id)
        reservation.table_id = payload.table_id
    if payload.customer_name is not None:
        reservation.customer_name = payload.customer_name.strip()
    if payload.phone is not None:
        reservation.phone = payload.phone.strip() or None
    if payload.party_size is not None:
        reservation.party_size = payload.party_size
    if payload.reserved_at is not None:
        reservation.reserved_at = payload.reserved_at
    if payload.duration_minutes is not None:
        reservation.duration_minutes = payload.duration_minutes
    if payload.status is not None:
        reservation.status = payload.status
    if payload.notes is not None:
        reservation.notes = payload.notes.strip() or None
    # Seating a reservation occupies its table; cancelling or a no-show frees it.
    if payload.status == "seated":
        await _set_table_status(db, context.store.id, reservation.table_id, "occupied")
    elif payload.status in {"cancelled", "no_show"}:
        await _set_table_status(db, context.store.id, reservation.table_id, "available", only_if="occupied")
    await db.commit()
    await db.refresh(reservation)
    names = await _table_name_map(db, context.store.id, {reservation.table_id} if reservation.table_id else set())
    return reservation_read(reservation, names.get(reservation.table_id))


@router.delete("/dining/reservations/{reservation_id}", tags=["dining"])
async def delete_reservation(reservation_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    reservation = (await db.execute(select(Reservation).where(Reservation.id == reservation_id, Reservation.store_id == context.store.id))).scalar_one_or_none()
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    await db.delete(reservation)
    await db.commit()
    return {"ok": True}


@router.get("/categories", response_model=list[CategoryRead], tags=["catalog"])
async def list_categories(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[CategoryRead]:
    result = await db.execute(select(Category).where(Category.company_id == membership.company_id).order_by(Category.parent_id, Category.name))
    return [CategoryRead.model_validate(category) for category in result.scalars().all()]


@router.post("/categories", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_category(payload: CategoryCreateRequest, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> CategoryRead:
    if payload.parent_id:
        parent_result = await db.execute(select(Category).where(Category.id == payload.parent_id, Category.company_id == membership.company_id, Category.is_active.is_(True)))
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent category not found")
    category = Category(company_id=membership.company_id, name=payload.name.strip(), parent_id=payload.parent_id)
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category already exists")
    await db.refresh(category)
    return CategoryRead.model_validate(category)



@router.patch("/categories/{category_id}", response_model=CategoryRead, tags=["catalog"])
async def update_category(category_id: UUID, payload: CategoryUpdateRequest, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> CategoryRead:
    category = (await db.execute(select(Category).where(Category.id == category_id, Category.company_id == membership.company_id))).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if payload.name is not None:
        category.name = payload.name.strip()
    if payload.is_active is not None:
        category.is_active = payload.is_active
    await db.commit()
    await db.refresh(category)
    return CategoryRead.model_validate(category)


@router.delete("/categories/{category_id}", tags=["catalog"])
async def delete_category(category_id: UUID, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    category = (await db.execute(select(Category).where(Category.id == category_id, Category.company_id == membership.company_id))).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    await db.delete(category)
    await db.commit()
    return {"ok": True}
async def category_for_company(db: AsyncSession, category_id: UUID | None, company_id: UUID) -> Category | None:
    if not category_id:
        return None
    result = await db.execute(select(Category).where(Category.id == category_id, Category.company_id == company_id, Category.is_active.is_(True)))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")
    return category


@router.get("/products", response_model=list[ProductRead], tags=["catalog"])
async def list_products(
    context: StoreContext = Depends(get_store_context),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=100),
    category_id: UUID | None = None,
    active_only: bool = True,
) -> list[ProductRead]:
    query = select(Product).where(Product.company_id == context.membership.company_id).options(selectinload(Product.category)).order_by(Product.name)
    if active_only:
        query = query.where(Product.is_active.is_(True))
    if search:
        query = query.where(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%") | Product.barcode.ilike(f"%{search}%"))
    if category_id:
        query = query.where(Product.category_id == category_id)
    products = (await db.execute(query)).scalars().all()
    product_ids = [product.id for product in products]
    balances_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids))) if product_ids else None
    balances = {balance.product_id: balance for balance in balances_result.scalars().all()} if balances_result else {}
    variants_by_product: dict[UUID, list[ProductVariantRead]] = {}
    if product_ids:
        variants = (await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(product_ids)).order_by(ProductVariant.position, ProductVariant.name))).scalars().all()
        variant_ids = [variant.id for variant in variants]
        variant_balances = {balance.variant_id: balance for balance in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id.in_(variant_ids)))).scalars().all()} if variant_ids else {}
        for variant in variants:
            variants_by_product.setdefault(variant.product_id, []).append(variant_read(variant, variant_balances.get(variant.id)))
    return [product_read(product, balances.get(product.id), variants_by_product.get(product.id, [])) for product in products]


@router.get("/pos/search", response_model=POSSearchResult, tags=["catalog"])
async def pos_search(
    q: str = Query(min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
    context: StoreContext = Depends(get_store_context),
    db: AsyncSession = Depends(get_db),
) -> POSSearchResult:
    """Unified till search: catalogue lines plus the serial units behind them.

    Matches product name, SKU, barcode and brand, variant SKU/name/barcode, and
    serial number or IMEI. Serials are limited to this store (or the
    unattributed company pool) and to in-stock units, and the payload carries no
    cost, supplier or warranty data — a cashier only needs enough to sell.
    Exact barcode/SKU/serial hits rank first so a scanner wedge always wins.
    """
    term = q.strip()
    like = f"%{term}%"
    lowered = term.lower()

    variant_match = select(ProductVariant.product_id).where(
        ProductVariant.sku.ilike(like) | ProductVariant.barcode.ilike(like) | ProductVariant.name.ilike(like)
    )
    products = (
        await db.execute(
            select(Product)
            .where(
                Product.company_id == context.membership.company_id,
                Product.is_active.is_(True),
                Product.name.ilike(like)
                | Product.sku.ilike(like)
                | Product.barcode.ilike(like)
                | Product.brand.ilike(like)
                | Product.id.in_(variant_match),
            )
            .order_by(Product.name)
            .limit(200)
        )
    ).scalars().all()
    product_ids = [product.id for product in products]

    balances: dict[UUID, InventoryBalance] = {}
    variants_by_product: dict[UUID, list[ProductVariant]] = {}
    variant_balances: dict[UUID, VariantInventoryBalance] = {}
    if product_ids:
        balances = {balance.product_id: balance for balance in (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids)))).scalars().all()}
        variants = (await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(product_ids)).order_by(ProductVariant.position, ProductVariant.name))).scalars().all()
        variant_ids = [variant.id for variant in variants]
        if variant_ids:
            variant_balances = {balance.variant_id: balance for balance in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id.in_(variant_ids)))).scalars().all()}
        for variant in variants:
            variants_by_product.setdefault(variant.product_id, []).append(variant)

    product_hits: list[POSProductHit] = []
    for product in products:
        active_variants = [variant for variant in variants_by_product.get(product.id, []) if variant.is_active]
        if not active_variants:
            balance = balances.get(product.id)
            product_hits.append(POSProductHit(product_id=product.id, variant_id=None, name=product.name, variant_name=None, sku=product.sku, barcode=product.barcode, price=product.price, stock=float(balance.on_hand) if balance else 0, image=product.image, track_serials=product.track_serials))
            continue
        for variant in active_variants:
            balance = variant_balances.get(variant.id)
            product_hits.append(POSProductHit(product_id=product.id, variant_id=variant.id, name=product.name, variant_name=variant.name, sku=variant.sku or product.sku, barcode=variant.barcode or product.barcode, price=variant.price if variant.price is not None else product.price, stock=float(balance.on_hand) if balance else 0, image=variant.image or product.image, track_serials=product.track_serials))

    def product_rank(hit: POSProductHit) -> int:
        if lowered in {str(hit.sku).lower(), str(hit.barcode or "").lower()}:
            return 0
        if str(hit.name).lower().startswith(lowered):
            return 1
        return 2

    product_hits.sort(key=lambda hit: (product_rank(hit), hit.name.lower()))
    product_hits = product_hits[:limit]

    serial_rows = (
        await db.execute(
            select(ProductSerial, Product.name, ProductVariant.name, ProductVariant.sku, ProductVariant.price, ProductVariant.image, Product.sku, Product.price, Product.image)
            .join(Product, Product.id == ProductSerial.product_id)
            .outerjoin(ProductVariant, ProductVariant.id == ProductSerial.variant_id)
            .where(
                ProductSerial.company_id == context.membership.company_id,
                ProductSerial.status == "in_stock",
                (ProductSerial.store_id == context.store.id) | ProductSerial.store_id.is_(None),
                ProductSerial.serial_number.ilike(like) | ProductSerial.imei.ilike(like),
            )
            .order_by(ProductSerial.created_at.desc())
            .limit(max(limit * 5, 50))
        )
    ).all()

    def serial_rank(row: tuple) -> int:
        serial = row[0]
        return 0 if lowered in {str(serial.serial_number).lower(), str(serial.imei or "").lower()} else 1

    serial_rows = sorted(serial_rows, key=lambda row: (serial_rank(row), -row[0].created_at.timestamp()))[:limit]
    serial_hits = [
        POSSerialHit(
            id=serial.id,
            serial_number=serial.serial_number,
            imei=serial.imei,
            product_id=serial.product_id,
            variant_id=serial.variant_id,
            product_name=product_name,
            variant_name=variant_name,
            sku=variant_sku or product_sku,
            price=variant_price if variant_price is not None else product_price,
            image=variant_image or product_image,
            condition_grade=serial.condition_grade,
            battery_health=serial.battery_health,
            battery_cycle_count=serial.battery_cycle_count,
        )
        for serial, product_name, variant_name, variant_sku, variant_price, variant_image, product_sku, product_price, product_image in serial_rows
    ]
    return POSSearchResult(products=product_hits, serials=serial_hits)


BUILTIN_ATTRIBUTE_KEYS = ["Color", "Storage", "RAM", "Size", "Chip", "Screen", "Model", "Warranty"]


@router.get("/catalog/attribute-suggestions", response_model=AttributeSuggestions, tags=["catalog"])
async def attribute_suggestions(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> AttributeSuggestions:
    product_attrs = (await db.execute(select(Product.attributes).where(Product.company_id == membership.company_id, Product.attributes.isnot(None)))).scalars().all()
    variant_attrs = (await db.execute(select(ProductVariant.attributes).join(Product, Product.id == ProductVariant.product_id).where(Product.company_id == membership.company_id, ProductVariant.attributes.isnot(None)))).scalars().all()
    values: dict[str, set[str]] = {}
    for raw in [*product_attrs, *variant_attrs]:
        if not isinstance(raw, dict):
            continue
        for key, value in raw.items():
            clean_key = str(key).strip()
            clean_value = "" if value is None else str(value).strip()
            if clean_key and clean_value:
                values.setdefault(clean_key, set()).add(clean_value)
    brands = (await db.execute(select(Product.brand).where(Product.company_id == membership.company_id, Product.brand.isnot(None)).distinct())).scalars().all()
    names = (await db.execute(select(Product.name).where(Product.company_id == membership.company_id).distinct().limit(200))).scalars().all()
    skus = (await db.execute(select(Product.sku).where(Product.company_id == membership.company_id).distinct().limit(200))).scalars().all()
    variant_names = (await db.execute(select(ProductVariant.name).join(Product, Product.id == ProductVariant.product_id).where(Product.company_id == membership.company_id).distinct().limit(200))).scalars().all()
    variant_skus = (await db.execute(select(ProductVariant.sku).join(Product, Product.id == ProductVariant.product_id).where(Product.company_id == membership.company_id).distinct().limit(200))).scalars().all()
    keys = sorted(set(BUILTIN_ATTRIBUTE_KEYS) | set(values.keys()))
    return AttributeSuggestions(keys=keys, values={key: sorted(found) for key, found in values.items()}, brands=sorted({brand for brand in brands if brand}), names=sorted(names), skus=sorted(skus), variant_names=sorted(variant_names), variant_skus=sorted(variant_skus))


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_product(payload: ProductCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductRead:
    await category_for_company(db, payload.category_id, membership.company_id)
    duplicate = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.sku == payload.sku.strip()))
    if duplicate.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")
    barcode = payload.barcode.strip() if payload.barcode else None
    if barcode:
        barcode_duplicate = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.barcode == barcode))
        if barcode_duplicate.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Barcode already exists")
    product = Product(company_id=membership.company_id, category_id=payload.category_id, name=payload.name.strip(), sku=payload.sku.strip(), description=payload.description, image=payload.image, barcode=barcode, brand=payload.brand.strip() if payload.brand else None, unit=payload.unit, track_inventory=payload.track_inventory, track_serials=payload.track_serials, attributes=payload.attributes, modifier_group_id=payload.modifier_group_id, price=payload.price, cost_price=payload.cost_price, tax_rate=payload.tax_rate)
    db.add(product)
    await db.flush()
    balance = InventoryBalance(store_id=context.store.id, product_id=product.id, on_hand=payload.opening_stock, reorder_point=payload.reorder_point)
    db.add(balance)
    if payload.opening_stock:
        db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=payload.opening_stock, movement_type="opening_balance", reason="product_created", unit_cost=payload.cost_price, created_by=context.user.id))
    await db.commit()
    product_result = await db.execute(select(Product).where(Product.id == product.id).options(selectinload(Product.category)))
    return product_read(product_result.scalar_one(), balance)


@router.patch("/products/{product_id}", response_model=ProductRead, tags=["catalog"])
async def update_product(product_id: UUID, payload: ProductUpdateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductRead:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id).options(selectinload(Product.category)))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if payload.category_id is not None:
        await category_for_company(db, payload.category_id, membership.company_id)
    if payload.sku and payload.sku != product.sku:
        duplicate = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.sku == payload.sku, Product.id != product.id))
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")
    if payload.barcode and payload.barcode != product.barcode:
        barcode_duplicate = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.barcode == payload.barcode, Product.id != product.id))
        if barcode_duplicate.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Barcode already exists")
    price_changed = payload.price is not None and payload.price != product.price
    cost_changed = payload.cost_price is not None and payload.cost_price != product.cost_price
    gate = "allow"
    if price_changed or cost_changed:
        policy = await load_approval_policy(db, membership.company_id)
        rule = policy.rules.get("price_cost_edit")
        amount = payload.price if price_changed else payload.cost_price
        gate = approval_gate(rule, amount) if policy.enabled else "allow"
        if gate == "request":
            is_approver = rule is not None and membership.role in rule.approvers
            if not (is_approver and not (policy.maker_checker and membership.role != "owner")):
                return await _pending_approval_response(db, membership, store_id=context.store.id, action="price_cost_edit", amount=amount, payload={**payload.model_dump(mode="json"), "product_id": str(product.id)}, user=context.user)
    await _apply_product_update(db, store_id=context.store.id, membership=membership, product=product, payload=payload, user=context.user)
    if gate == "review":
        await log_audit(db, membership, context.store.id, "price_cost_edit_reviewed", "product", entity_id=product.id, details={"product": product.name, "price": str(product.price), "cost_price": str(product.cost_price) if product.cost_price is not None else None, "mode": "review"}, user=context.user)
        await notify_company_managers(db, membership.company_id, context.store.id, "price_cost_edit_review", f"Price change flagged: {product.name}", f"by {context.user.full_name}")
        await db.commit()
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))
    await db.refresh(product)
    return product_read(product, balance_result.scalar_one_or_none(), await load_product_variants(db, context.store.id, product))


@router.put("/products/{product_id}/variants", response_model=ProductRead, tags=["catalog"])
async def set_product_variants(product_id: UUID, payload: ProductVariantsSetRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductRead:
    result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id).options(selectinload(Product.category)))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    existing_list = (await db.execute(select(ProductVariant).where(ProductVariant.product_id == product.id))).scalars().all()
    existing_by_id = {variant.id: variant for variant in existing_list}
    existing_by_sku = {variant.sku: variant for variant in existing_list}
    # The payload is the authoritative set. Reject two rows that resolve to the
    # same SKU before touching the database so the client gets one clear 409
    # instead of a 500 from the unique constraint.
    seen_skus: set[str] = set()
    for item in payload.variants:
        sku = item.sku.strip()
        if sku in seen_skus:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Variant SKU already exists: {sku}")
        seen_skus.add(sku)
    kept: set[UUID] = set()
    for index, item in enumerate(payload.variants):
        sku = item.sku.strip()
        barcode = item.barcode.strip() if item.barcode else None
        # Prefer the row's id, but fall back to its SKU: a client that lost the
        # id, or that reuses a removed variant's SKU, still edits the intended
        # variant instead of colliding with it.
        variant = existing_by_id.get(item.id) if item.id else None
        if variant is None:
            variant = existing_by_sku.get(sku)
        if variant is not None:
            if variant.id in kept:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Variant SKU already exists: {sku}")
            variant.sku = sku
            variant.barcode = barcode
            variant.name = item.name.strip()
            variant.image = item.image
            variant.price = item.price
            variant.cost_price = item.cost_price
            variant.attributes = item.attributes
            variant.is_active = item.is_active
            variant.position = index
        else:
            variant = ProductVariant(product_id=product.id, sku=sku, barcode=barcode, name=item.name.strip(), image=item.image, price=item.price, cost_price=item.cost_price, attributes=item.attributes, is_active=item.is_active, position=index)
            db.add(variant)
            await db.flush()
            if item.opening_stock or item.reorder_point:
                db.add(VariantInventoryBalance(store_id=context.store.id, variant_id=variant.id, on_hand=item.opening_stock, reorder_point=item.reorder_point))
                if item.opening_stock:
                    db.add(StockMovement(store_id=context.store.id, product_id=product.id, variant_id=variant.id, quantity=item.opening_stock, movement_type="opening_balance", reason="variant_created", unit_cost=item.cost_price, created_by=context.user.id))
        kept.add(variant.id)
        existing_by_sku[sku] = variant
    # Remove variants the client dropped. This is safe now that a reused SKU
    # resolves to an update above rather than a fresh insert.
    for variant_id, variant in existing_by_id.items():
        if variant_id not in kept:
            await db.delete(variant)
    try:
        await db.commit()
    except IntegrityError:
        # e.g. two rows swapping SKUs at once; a 409 is clearer than a 500.
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Variant SKU already exists") from None
    refreshed = (await db.execute(select(Product).where(Product.id == product.id).options(selectinload(Product.category)))).scalar_one()
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))
    return product_read(refreshed, balance_result.scalar_one_or_none(), await load_product_variants(db, context.store.id, refreshed))


@router.get("/products/{product_id}/serials", response_model=list[ProductSerialRead], tags=["catalog"])
async def list_product_serials(product_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), status_filter: str | None = Query(default=None, alias="status"), variant_id: UUID | None = Query(default=None), store_id: UUID | None = Query(default=None)) -> list[ProductSerialRead]:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == context.membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if await release_stale_serial_reservations(db, context.membership.company_id):
        await db.commit()
    statement = select(ProductSerial).where(ProductSerial.product_id == product.id)
    if status_filter:
        statement = statement.where(ProductSerial.status == status_filter)
    if variant_id:
        statement = statement.where(ProductSerial.variant_id == variant_id)
    if store_id:
        statement = statement.where(ProductSerial.store_id == store_id)
    rows = (await db.execute(statement.order_by(ProductSerial.created_at.desc()))).scalars().all()
    return [ProductSerialRead.model_validate(row) for row in rows]


async def product_has_variants(db: AsyncSession, product_id: UUID) -> bool:
    return (await db.execute(select(ProductVariant.id).where(ProductVariant.product_id == product_id).limit(1))).scalar_one_or_none() is not None


def stage_serial_condition(db: AsyncSession, company_id: UUID, serial: ProductSerial, user_id: UUID) -> SerialConditionHistory:
    """Stamp the unit's current condition and append an audit history row."""
    now = utcnow()
    serial.graded_at = now
    serial.graded_by = user_id
    history = SerialConditionHistory(
        company_id=company_id,
        serial_id=serial.id,
        condition_grade=serial.condition_grade,
        battery_health=serial.battery_health,
        battery_cycle_count=serial.battery_cycle_count,
        condition_report=serial.condition_report,
        graded_by=user_id,
        graded_at=now,
    )
    db.add(history)
    return history


async def supplier_name_map(db: AsyncSession, supplier_ids: set[UUID]) -> dict[UUID, str]:
    ids = {supplier_id for supplier_id in supplier_ids if supplier_id}
    if not ids:
        return {}
    rows = (await db.execute(select(Supplier.id, Supplier.name).where(Supplier.id.in_(ids)))).all()
    return {row[0]: row[1] for row in rows}


def serial_read(serial: ProductSerial, supplier_name: str | None = None) -> ProductSerialRead:
    read = ProductSerialRead.model_validate(serial)
    if supplier_name is not None:
        read.supplier_name = supplier_name
    return read


async def adjust_serial_stock(db: AsyncSession, store_id: UUID, product: Product, variant_id: UUID | None, quantity: int, movement_type: str, reason: str, user_id: UUID, unit_cost: Decimal | None = None) -> None:
    """Keep inventory balances in step with serial units.

    Stock for a product with variants lives on the variants; for a product
    without variants it lives on the product. A serial with no variant on a
    product that has variants is unattributed until it is sold onto a variant,
    so it is intentionally left out of the balances here.
    """
    if quantity == 0:
        return
    if variant_id:
        balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store_id, VariantInventoryBalance.variant_id == variant_id).with_for_update())).scalar_one_or_none()
        if not balance:
            if quantity < 0:
                return
            balance = VariantInventoryBalance(store_id=store_id, variant_id=variant_id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
        balance.on_hand = max(Decimal("0"), balance.on_hand + quantity)
        db.add(StockMovement(store_id=store_id, product_id=product.id, variant_id=variant_id, quantity=quantity, movement_type=movement_type, reason=reason, unit_cost=unit_cost, created_by=user_id))
    elif not await product_has_variants(db, product.id):
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store_id, InventoryBalance.product_id == product.id).with_for_update())).scalar_one_or_none()
        if not balance:
            if quantity < 0:
                return
            balance = InventoryBalance(store_id=store_id, product_id=product.id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
        balance.on_hand = max(Decimal("0"), balance.on_hand + quantity)
        db.add(StockMovement(store_id=store_id, product_id=product.id, quantity=quantity, movement_type=movement_type, reason=reason, unit_cost=unit_cost, created_by=user_id))


@router.post("/products/{product_id}/serials", response_model=list[ProductSerialRead], status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def add_product_serials(product_id: UUID, payload: ProductSerialsSetRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> list[ProductSerialRead]:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    created: list[ProductSerial] = []
    for item in payload.serials:
        serial_number = item.serial_number.strip()
        if not serial_number:
            continue
        duplicate = await db.execute(select(ProductSerial).where(ProductSerial.company_id == membership.company_id, ProductSerial.serial_number == serial_number))
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial already exists: {serial_number}")
        if item.variant_id:
            variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == item.variant_id, ProductVariant.product_id == product.id))).scalar_one_or_none()
            if not variant:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant not found")
        supplier_until = utcnow() + timedelta(days=30 * item.supplier_warranty_months) if item.supplier_warranty_months else None
        customer_months = item.customer_warranty_months if item.customer_warranty_months is not None else item.supplier_warranty_months
        if item.supplier_id:
            supplier = (await db.execute(select(Supplier).where(Supplier.id == item.supplier_id, Supplier.company_id == membership.company_id))).scalar_one_or_none()
            if not supplier:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier not found")
        serial = ProductSerial(company_id=membership.company_id, product_id=product.id, variant_id=item.variant_id, store_id=context.store.id, serial_number=serial_number, imei=item.imei.strip() if item.imei else None, status="in_stock", cost_price=item.cost_price, supplier_warranty_months=item.supplier_warranty_months, supplier_warranty_until=supplier_until, customer_warranty_months=customer_months, condition_grade=item.condition_grade, battery_health=item.battery_health, battery_cycle_count=item.battery_cycle_count, condition_report=item.condition_report, supplier_id=item.supplier_id)
        db.add(serial)
        await db.flush()
        if item.condition_grade is not None or item.battery_health is not None or item.battery_cycle_count is not None or item.condition_report is not None:
            stage_serial_condition(db, membership.company_id, serial, context.user.id)
        # A new serial is a physical unit, so it adds stock to the matching balance.
        await adjust_serial_stock(db, context.store.id, product, item.variant_id, 1, "restock", "serial_added", context.user.id, unit_cost=item.cost_price)
        created.append(serial)
    await db.commit()
    for serial in created:
        await db.refresh(serial)
    names = await supplier_name_map(db, {serial.supplier_id for serial in created})
    return [serial_read(serial, names.get(serial.supplier_id)) for serial in created]


def trade_in_read(trade_in: TradeIn, product_name: str = "") -> TradeInRead:
    return TradeInRead(
        id=trade_in.id,
        store_id=trade_in.store_id,
        customer_id=trade_in.customer_id,
        product_id=trade_in.product_id,
        product_name=product_name,
        serial_id=trade_in.serial_id,
        order_id=trade_in.order_id,
        serial_number=trade_in.serial_number,
        imei=trade_in.imei,
        condition_grade=trade_in.condition_grade,
        battery_health=trade_in.battery_health,
        assessed_value=trade_in.assessed_value,
        kind=trade_in.kind,
        status=trade_in.status,
        notes=trade_in.notes,
        created_at=trade_in.created_at,
    )


@router.post("/trade-ins", response_model=TradeInRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_trade_in(payload: TradeInCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> TradeInRead:
    product = (await db.execute(select(Product).where(Product.id == payload.product_id, Product.company_id == membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    serial_number = payload.serial_number.strip()
    duplicate = (await db.execute(select(ProductSerial).where(ProductSerial.company_id == membership.company_id, ProductSerial.serial_number == serial_number))).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial already exists: {serial_number}")
    if payload.variant_id:
        variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == payload.variant_id, ProductVariant.product_id == product.id))).scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant not found")
    if payload.customer_id:
        customer = (await db.execute(select(Customer).where(Customer.id == payload.customer_id, Customer.company_id == membership.company_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer not found")
    # The device becomes stock at its assessed value, so resale margin is real.
    serial = ProductSerial(company_id=membership.company_id, product_id=product.id, variant_id=payload.variant_id, store_id=context.store.id, serial_number=serial_number, imei=payload.imei.strip() if payload.imei else None, status="in_stock", cost_price=payload.assessed_value, condition_grade=payload.condition_grade, battery_health=payload.battery_health, condition_report=payload.condition_report)
    db.add(serial)
    await db.flush()
    if payload.condition_grade is not None or payload.battery_health is not None or payload.condition_report is not None:
        stage_serial_condition(db, membership.company_id, serial, context.user.id)
    await adjust_serial_stock(db, context.store.id, product, payload.variant_id, 1, "restock", "trade_in", context.user.id, unit_cost=payload.assessed_value)
    trade_in = TradeIn(company_id=membership.company_id, store_id=context.store.id, customer_id=payload.customer_id, product_id=product.id, serial_id=serial.id, serial_number=serial_number, imei=serial.imei, condition_grade=payload.condition_grade, battery_health=payload.battery_health, condition_report=payload.condition_report, assessed_value=payload.assessed_value, kind=payload.kind, status="accepted", notes=(payload.notes or "").strip() or None, created_by=context.user.id)
    db.add(trade_in)
    await db.commit()
    await db.refresh(trade_in)
    return trade_in_read(trade_in, product.name)


@router.get("/trade-ins", response_model=list[TradeInRead], tags=["catalog"])
async def list_trade_ins(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[TradeInRead]:
    rows = (await db.execute(select(TradeIn, Product.name).join(Product, Product.id == TradeIn.product_id).where(TradeIn.store_id == context.store.id).order_by(TradeIn.created_at.desc()))).all()
    return [trade_in_read(trade_in, name) for trade_in, name in rows]


@router.get("/trade-ins/{trade_in_id}", response_model=TradeInRead, tags=["catalog"])
async def get_trade_in(trade_in_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> TradeInRead:
    row = (await db.execute(select(TradeIn, Product.name).join(Product, Product.id == TradeIn.product_id).where(TradeIn.id == trade_in_id, TradeIn.store_id == context.store.id))).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade-in not found")
    trade_in, name = row
    return trade_in_read(trade_in, name)


@router.post("/trade-ins/{trade_in_id}/void", response_model=TradeInRead, tags=["catalog"])
async def void_trade_in(trade_in_id: UUID, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> TradeInRead:
    trade_in = (await db.execute(select(TradeIn).where(TradeIn.id == trade_in_id, TradeIn.store_id == context.store.id))).scalar_one_or_none()
    if not trade_in:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade-in not found")
    if trade_in.status != "accepted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade-in is not open")
    if trade_in.order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade-in is already applied to a sale")
    serial = (await db.execute(select(ProductSerial).where(ProductSerial.id == trade_in.serial_id))).scalar_one_or_none() if trade_in.serial_id else None
    if serial is not None:
        if serial.status != "in_stock":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The traded unit is no longer in stock")
        product = (await db.execute(select(Product).where(Product.id == serial.product_id))).scalar_one_or_none()
        if product is not None:
            await adjust_serial_stock(db, context.store.id, product, serial.variant_id, -1, "manual_adjustment", "trade_in_void", context.user.id)
        await db.delete(serial)
        trade_in.serial_id = None
    trade_in.status = "void"
    await db.commit()
    await db.refresh(trade_in)
    product_name = (await db.execute(select(Product.name).where(Product.id == trade_in.product_id))).scalar_one_or_none()
    return trade_in_read(trade_in, product_name or "")


def warranty_claim_read(claim: WarrantyClaim, serial_number: str | None = None) -> WarrantyClaimRead:
    return WarrantyClaimRead(
        id=claim.id,
        store_id=claim.store_id,
        claim_number=claim.claim_number,
        serial_id=claim.serial_id,
        serial_number=serial_number,
        customer_id=claim.customer_id,
        order_id=claim.order_id,
        status=claim.status,
        resolution=claim.resolution,
        issue=claim.issue,
        description=claim.description,
        cost=claim.cost,
        replacement_serial_id=claim.replacement_serial_id,
        refund_id=claim.refund_id,
        service_ticket_id=claim.service_ticket_id,
        claimed_at=claim.claimed_at,
        decided_at=claim.decided_at,
        resolved_at=claim.resolved_at,
        events=[WarrantyClaimEventRead.model_validate(event) for event in sorted(claim.events, key=lambda row: row.created_at)],
    )


def _warranty_event(db: AsyncSession, claim: WarrantyClaim, from_status: str | None, to_status: str, note: str | None, actor_id: UUID | None) -> None:
    # Add through the session: touching ``claim.events`` on a just-flushed instance
    # would emit a lazy load, which is illegal in the async context.
    db.add(WarrantyClaimEvent(claim_id=claim.id, from_status=from_status, to_status=to_status, note=note, actor_id=actor_id))


async def _load_warranty_claim(db: AsyncSession, claim_id: UUID, store_id: UUID) -> WarrantyClaim:
    claim = (await db.execute(select(WarrantyClaim).where(WarrantyClaim.id == claim_id, WarrantyClaim.store_id == store_id).options(selectinload(WarrantyClaim.events)).execution_options(populate_existing=True))).scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warranty claim not found")
    return claim


@router.post("/warranty-claims", response_model=WarrantyClaimRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_warranty_claim(payload: WarrantyClaimCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> WarrantyClaimRead:
    serial = (await db.execute(select(ProductSerial).where(ProductSerial.id == payload.serial_id, ProductSerial.company_id == membership.company_id))).scalar_one_or_none()
    if not serial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serial not found")
    if serial.status != "sold":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a sold unit can be claimed")
    order_id = await db.scalar(select(OrderItem.order_id).where(OrderItem.id == serial.order_item_id)) if serial.order_item_id else None
    customer_id = payload.customer_id
    if customer_id is None and order_id:
        customer_id = await db.scalar(select(Order.customer_id).where(Order.id == order_id))
    claim = WarrantyClaim(company_id=membership.company_id, store_id=context.store.id, claim_number=await next_document_number(db, store_id=context.store.id, scope="warranty", prefix="WC"), serial_id=serial.id, customer_id=customer_id, order_id=order_id, order_item_id=serial.order_item_id, status="open", issue=payload.issue.strip(), description=(payload.description or "").strip() or None, created_by=context.user.id)
    db.add(claim)
    await db.flush()
    _warranty_event(db, claim, None, "open", "Claim filed", context.user.id)
    claim_id = claim.id
    serial_number = serial.serial_number
    await db.commit()
    return warranty_claim_read(await _load_warranty_claim(db, claim_id, context.store.id), serial_number)


@router.get("/warranty-claims", response_model=list[WarrantyClaimRead], tags=["catalog"])
async def list_warranty_claims(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[WarrantyClaimRead]:
    rows = (await db.execute(select(WarrantyClaim, ProductSerial.serial_number).join(ProductSerial, ProductSerial.id == WarrantyClaim.serial_id).where(WarrantyClaim.store_id == context.store.id).options(selectinload(WarrantyClaim.events)).order_by(WarrantyClaim.claimed_at.desc()))).all()
    return [warranty_claim_read(claim, serial_number) for claim, serial_number in rows]


@router.get("/warranty-claims/{claim_id}", response_model=WarrantyClaimRead, tags=["catalog"])
async def get_warranty_claim(claim_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> WarrantyClaimRead:
    claim = await _load_warranty_claim(db, claim_id, context.store.id)
    serial_number = await db.scalar(select(ProductSerial.serial_number).where(ProductSerial.id == claim.serial_id))
    return warranty_claim_read(claim, serial_number)


@router.post("/warranty-claims/{claim_id}/decide", response_model=WarrantyClaimRead, tags=["catalog"])
async def decide_warranty_claim(claim_id: UUID, payload: WarrantyClaimDecideRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> WarrantyClaimRead:
    claim = await _load_warranty_claim(db, claim_id, context.store.id)
    if claim.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Claim is not open")
    claim.decided_at = utcnow()
    claim.decided_by = context.user.id
    if payload.approve:
        claim.status = "approved"
        claim.resolution = payload.resolution or "repair"
        _warranty_event(db, claim, "open", "approved", payload.note or f"Approved ({claim.resolution})", context.user.id)
    else:
        claim.status = "denied"
        claim.resolution = "deny"
        claim.resolved_at = utcnow()
        _warranty_event(db, claim, "open", "denied", payload.note or "Denied", context.user.id)
    claim_id = claim.id
    serial_id = claim.serial_id
    await db.commit()
    serial_number = await db.scalar(select(ProductSerial.serial_number).where(ProductSerial.id == serial_id))
    return warranty_claim_read(await _load_warranty_claim(db, claim_id, context.store.id), serial_number)


@router.post("/warranty-claims/{claim_id}/resolve", response_model=WarrantyClaimRead, tags=["catalog"])
async def resolve_warranty_claim(claim_id: UUID, payload: WarrantyClaimResolveRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> WarrantyClaimRead:
    claim = await _load_warranty_claim(db, claim_id, context.store.id)
    if claim.status not in ("open", "approved"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Claim is not open for resolution")
    previous = claim.status
    if payload.resolution == "repair":
        ticket = SerialServiceTicket(company_id=claim.company_id, serial_id=claim.serial_id, store_id=context.store.id, ticket_type="repair", status="resolved", summary=claim.issue[:180], description=payload.note, cost=payload.cost, created_by=context.user.id, resolved_at=utcnow())
        db.add(ticket)
        await db.flush()
        claim.service_ticket_id = ticket.id
        claim.cost = payload.cost
    elif payload.resolution == "replace":
        serial = (await db.execute(select(ProductSerial).where(ProductSerial.id == claim.serial_id))).scalar_one_or_none()
        if not payload.replacement_serial_number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide the replacement serial number")
        replacement = ProductSerial(company_id=claim.company_id, product_id=serial.product_id, variant_id=serial.variant_id, store_id=context.store.id, serial_number=payload.replacement_serial_number.strip(), imei=(payload.replacement_imei or "").strip() or None, status="sold", cost_price=serial.cost_price, condition_grade=serial.condition_grade, customer_warranty_months=serial.customer_warranty_months, customer_warranty_until=serial.customer_warranty_until, sold_at=utcnow())
        db.add(replacement)
        await db.flush()
        claim.replacement_serial_id = replacement.id
        claim.cost = payload.cost
    elif payload.resolution == "refund":
        claim.refund_id = payload.refund_id
    claim.status = "denied" if payload.resolution == "deny" else "closed"
    claim.resolution = payload.resolution
    claim.resolved_at = utcnow()
    _warranty_event(db, claim, previous, claim.status, payload.note or f"Resolved: {payload.resolution}", context.user.id)
    claim_id = claim.id
    serial_id = claim.serial_id
    await db.commit()
    serial_number = await db.scalar(select(ProductSerial.serial_number).where(ProductSerial.id == serial_id))
    return warranty_claim_read(await _load_warranty_claim(db, claim_id, context.store.id), serial_number)


async def _public_merchant_payment_context(db: AsyncSession, store: Store) -> tuple[str | None, str | None, str]:
    """Resolve the ChmabaPay link/store a merchant online payment settles to, or (None, None, 'none')."""
    link = store.aba_payway_link if store.aba_payway_status == "active" else None
    store_ref = store.chamabapay_store_id if link else None
    scope = "store"
    if not link:
        company = await get_company(db, store.company_id)
        link = company.aba_payway_link if company.aba_payway_status == "active" else None
        store_ref = company.chamabapay_store_id if link else None
        scope = "company"
    if not link:
        return None, None, "none"
    return link, store_ref, scope


async def _resolve_public_store(db: AsyncSession, token: str) -> tuple[Store | None, DiningTable | None]:
    store = (await db.execute(select(Store).where(Store.public_order_token == token, Store.public_order_enabled.is_(True), Store.is_active.is_(True)))).scalar_one_or_none()
    if store is not None:
        return store, None
    table = (await db.execute(select(DiningTable).where(DiningTable.qr_token == token))).scalar_one_or_none()
    if table is None:
        return None, None
    store = (await db.execute(select(Store).where(Store.id == table.store_id, Store.public_order_enabled.is_(True), Store.is_active.is_(True)))).scalar_one_or_none()
    return store, table


@router.get("/public/order/{token}", response_model=PublicMenuRead, tags=["public"])
async def public_menu(token: str, db: AsyncSession = Depends(get_db)) -> PublicMenuRead:
    store, table = await _resolve_public_store(db, token)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Online ordering is not available")
    rows = (await db.execute(select(Product, Category.name).outerjoin(Category, Category.id == Product.category_id).where(Product.company_id == store.company_id, Product.is_active.is_(True)).order_by(Product.name))).all()
    balances = {balance.product_id: balance.on_hand for balance in (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store.id))).scalars().all()}
    variants_by_product: dict = {}
    variant_balances: dict = {}
    product_ids = [product.id for product, _ in rows]
    if product_ids:
        active_variants = (await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(product_ids), ProductVariant.is_active.is_(True)).order_by(ProductVariant.name))).scalars().all()
        variant_ids = [variant.id for variant in active_variants]
        for variant in active_variants:
            variants_by_product.setdefault(variant.product_id, []).append(variant)
        if variant_ids:
            variant_balances = {balance.variant_id: balance.on_hand for balance in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store.id, VariantInventoryBalance.variant_id.in_(variant_ids)))).scalars().all()}
    items = []
    for product, category_name in rows:
        # Public menu shows a simple availability flag, never live counts or costs.
        product_variants = variants_by_product.get(product.id, [])
        public_variants = [
            PublicMenuVariant(
                id=variant.id,
                name=variant.name,
                price=variant.price if variant.price is not None else product.price,
                available=(variant_balances.get(variant.id, Decimal("0")) > 0) if product.track_inventory else True,
            )
            for variant in product_variants
        ]
        # With sizes/options, availability is per variant; otherwise it is the product balance.
        available = any(variant.available for variant in public_variants) if public_variants else ((balances.get(product.id, Decimal("0")) > 0) if product.track_inventory else True)
        items.append(PublicMenuItem(id=product.id, name=product.name, description=product.description, image=product.image, price=product.price, category=category_name, available=available, variants=public_variants))
    return PublicMenuRead(store_name=store.name, table_name=table.name if table else None, currency_code=store.currency_code, require_online_payment=bool(dict(store.preferences or {}).get("public_order_require_payment", False)), items=items)


@router.post("/public/order/{token}", response_model=HeldOrderRead, status_code=status.HTTP_201_CREATED, tags=["public"])
async def public_submit_order(token: str, payload: PublicOrderSubmitRequest, db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    store, table = await _resolve_public_store(db, token)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Online ordering is not available")
    product_ids = [item.product_id for item in payload.items]
    products = {product.id: product for product in (await db.execute(select(Product).where(Product.company_id == store.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))).scalars().all()}
    if len(products) != len(set(product_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    variant_ids = [item.variant_id for item in payload.items if item.variant_id]
    variants = {variant.id: variant for variant in (await db.execute(select(ProductVariant).where(ProductVariant.id.in_(variant_ids), ProductVariant.is_active.is_(True)))).scalars().all()} if variant_ids else {}
    balances = {balance.product_id: balance for balance in (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store.id, InventoryBalance.product_id.in_(product_ids)))).scalars().all()}
    variant_balances = {balance.variant_id: balance for balance in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store.id, VariantInventoryBalance.variant_id.in_(variant_ids)))).scalars().all()} if variant_ids else {}
    snapshot: list[dict] = []
    for requested in payload.items:
        product = products[requested.product_id]
        variant = variants.get(requested.variant_id) if requested.variant_id else None
        if requested.variant_id and (not variant or variant.product_id != product.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Variant not available for {product.name}")
        balance = variant_balances.get(variant.id) if variant is not None else balances.get(product.id)
        if product.track_inventory and (not balance or balance.on_hand < requested.quantity):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name}")
        base_price = variant.price if (variant and variant.price is not None) else product.price
        modifier_delta = sum((entry.price_delta for entry in requested.modifiers), Decimal("0.00"))
        unit_price = base_price + modifier_delta
        line_total = (unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        snapshot.append({"line_key": held_line_key(product.id, variant.id if variant else None, requested.modifiers), "product_id": str(product.id), "product_name": product.name, "sku": variant.sku if variant else product.sku, "variant_id": str(variant.id) if variant else None, "variant_name": variant.name if variant else None, "attributes": None, "modifiers": [{"name": entry.name, "price_delta": str(entry.price_delta)} for entry in requested.modifiers] or None, "unit_price": str(unit_price), "quantity": str(requested.quantity), "line_total": str(line_total), "seat": None, "course": None, "fired_at": None})
    held = HeldOrder(store_id=store.id, created_by=None, label=table.name if table else "Online order", order_type="dine_in" if table else "takeaway", table_id=table.id if table else None, status="open", source="qr" if table else "online", customer_note=(payload.customer_note or "").strip() or None, items=snapshot)
    db.add(held)
    if table is not None:
        table.status = "occupied"
    await db.flush()
    if bool(dict(store.preferences or {}).get("public_order_require_payment", False)):
        line_total_sum = sum((Decimal(str(line["line_total"])) for line in snapshot), Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_rate = store.service_tax_rate or Decimal("10.00")
        tax_inclusive = bool(dict(store.preferences or {}).get("tax_inclusive", False))
        order_total = line_total_sum if tax_inclusive else line_total_sum + (line_total_sum * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        link, store_ref, scope = await _public_merchant_payment_context(db, store)
        if store_ref:
            provider = await active_payment_provider(db)
            reference = f"online-{held.id.hex[:12]}"
            metadata: dict = {"type": "online_order", "store_id": str(store.id), "merchant_connection": scope}
            if link:
                metadata["merchant_aba_link"] = link
            try:
                provider_payment = await provider.create_payment(order_total, reference, idempotency_key=reference, store_ref=store_ref, metadata=metadata)
            except PaymentProviderError as exc:
                await db.rollback()
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
            held.payment_status = provider_payment.status or "pending"
            held.payment_provider = provider.name
            held.payment_external_id = provider_payment.id
            held.payment_qr_string = provider_payment.qr_string
            held.payment_checkout_url = provider_payment.checkout_url
    await db.commit()
    await db.refresh(held)
    # Alert owners in a second transaction so a mail problem can never stop the
    # customer's order from landing on the board.
    try:
        if await queue_public_order_note(db, store, held):
            await db.commit()
    except Exception:
        await db.rollback()
        logging.getLogger(__name__).exception("Could not queue the online-order alert")
    # Optional acknowledgement to the customer, also best-effort.
    if payload.customer_email:
        try:
            if await queue_online_order_acknowledgement(
                db,
                store,
                recipient=str(payload.customer_email),
                customer_name=(payload.customer_name or "").strip() or None,
                label=held.label,
                lines=held.items or [],
            ):
                await db.commit()
        except Exception:
            await db.rollback()
            logging.getLogger(__name__).exception("Could not queue the online-order acknowledgement")
    return held_order_read(held, None, store.service_tax_rate, bool(dict(store.preferences or {}).get("tax_inclusive", False)))


@router.get("/public/order/{token}/payment/{held_id}", response_model=PublicOrderPaymentRead, tags=["public"])
async def public_order_payment_status(token: str, held_id: UUID, db: AsyncSession = Depends(get_db)) -> PublicOrderPaymentRead:
    """Poll the online-payment state for a submitted public order."""
    store, _table = await _resolve_public_store(db, token)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Online ordering is not available")
    held = (await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == store.id))).scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return PublicOrderPaymentRead(held_order_id=held.id, payment_status=held.payment_status or "unpaid", qr_string=held.payment_qr_string, checkout_url=held.payment_checkout_url, paid=(held.payment_status == "paid"))


@router.patch("/stores/{store_id}/public-order", response_model=StorePublicOrderSettings, tags=["workspace"])
async def set_store_public_order(store_id: UUID, payload: StorePublicOrderSettings, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> StorePublicOrderSettings:
    store = (await db.execute(select(Store).where(Store.id == store_id, Store.company_id == membership.company_id))).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    store.public_order_enabled = payload.enabled
    if payload.enabled and not store.public_order_token:
        store.public_order_token = uuid.uuid4().hex
    if payload.require_online_payment is not None:
        prefs = dict(store.preferences or {})
        prefs["public_order_require_payment"] = bool(payload.require_online_payment)
        store.preferences = prefs
    await db.commit()
    return StorePublicOrderSettings(enabled=store.public_order_enabled, token=store.public_order_token, require_online_payment=bool(dict(store.preferences or {}).get("public_order_require_payment", False)))


@router.patch("/serials/{serial_id}", response_model=ProductSerialRead, tags=["catalog"])
async def update_product_serial(serial_id: UUID, payload: ProductSerialUpdateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductSerialRead:
    serial = (await db.execute(select(ProductSerial).where(ProductSerial.id == serial_id, ProductSerial.company_id == membership.company_id))).scalar_one_or_none()
    if not serial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serial not found")
    if payload.serial_number is not None:
        new_number = payload.serial_number.strip()
        if not new_number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Serial number cannot be empty")
        if new_number != serial.serial_number:
            # Sold units keep their history: renaming one would rewrite the sale,
            # receipt and warranty trail, so only unsold stock can be corrected.
            if serial.status == "sold" or serial.order_item_id is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the serial number of a unit that has already been sold")
            duplicate = (await db.execute(select(ProductSerial).where(ProductSerial.company_id == membership.company_id, ProductSerial.serial_number == new_number, ProductSerial.id != serial.id))).scalar_one_or_none()
            if duplicate:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial already exists: {new_number}")
            serial.serial_number = new_number
    previous_status = serial.status
    if payload.status is not None:
        serial.status = payload.status
    if payload.imei is not None:
        serial.imei = payload.imei.strip() or None
    if payload.cost_price is not None:
        serial.cost_price = payload.cost_price
    if payload.supplier_id is not None:
        if payload.supplier_id:
            supplier = (await db.execute(select(Supplier).where(Supplier.id == payload.supplier_id, Supplier.company_id == membership.company_id))).scalar_one_or_none()
            if not supplier:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier not found")
        serial.supplier_id = payload.supplier_id or None
    if payload.supplier_warranty_months is not None:
        serial.supplier_warranty_months = payload.supplier_warranty_months
        # Anchor to when the unit was received, not to the edit date.
        anchor = serial.created_at or utcnow()
        serial.supplier_warranty_until = anchor + timedelta(days=30 * payload.supplier_warranty_months) if payload.supplier_warranty_months else None
    if payload.customer_warranty_months is not None:
        serial.customer_warranty_months = payload.customer_warranty_months
        if serial.sold_at and payload.customer_warranty_months:
            serial.customer_warranty_until = serial.sold_at + timedelta(days=30 * payload.customer_warranty_months)
        else:
            serial.customer_warranty_until = None
    condition_changed = False
    # Use the field set (not the value) so an explicit null clears a previously
    # recorded condition instead of being treated as "not provided".
    if "condition_grade" in payload.model_fields_set:
        serial.condition_grade = payload.condition_grade
        condition_changed = True
    if "battery_health" in payload.model_fields_set:
        serial.battery_health = payload.battery_health
        condition_changed = True
    if "battery_cycle_count" in payload.model_fields_set:
        serial.battery_cycle_count = payload.battery_cycle_count
        condition_changed = True
    if "condition_report" in payload.model_fields_set:
        serial.condition_report = payload.condition_report
        condition_changed = True
    if condition_changed:
        stage_serial_condition(db, membership.company_id, serial, context.user.id)
    # A unit is counted in exactly one stock bucket: a variant balance for variant
    # products, the product balance otherwise. Move it out of the old bucket and
    # into the new one in a single pass, so a request that changes both the
    # variant and the status can never adjust the same physical unit twice.
    variant_provided = "variant_id" in payload.model_fields_set
    new_variant_id = payload.variant_id if variant_provided else serial.variant_id
    if variant_provided and new_variant_id and new_variant_id != serial.variant_id:
        variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == new_variant_id, ProductVariant.product_id == serial.product_id))).scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant not found")
    old_variant_id = serial.variant_id
    was_in_stock = previous_status == "in_stock"
    is_in_stock = serial.status == "in_stock"
    if old_variant_id != new_variant_id or was_in_stock != is_in_stock:
        product = (await db.execute(select(Product).where(Product.id == serial.product_id))).scalar_one_or_none()
        if product:
            has_variants = await product_has_variants(db, product.id)
            # Release the old bucket if the unit was actually counted there. An
            # unattributed unit on a variant product never was, so leave it alone.
            if was_in_stock and (old_variant_id or not has_variants):
                await adjust_serial_stock(db, context.store.id, product, old_variant_id, -1, "variant_transfer_out" if old_variant_id else "manual_adjustment", "serial_reassigned" if old_variant_id else "serial_status", context.user.id)
            # Claim the new bucket if the unit is in stock now.
            if is_in_stock and (new_variant_id or not has_variants):
                await adjust_serial_stock(db, context.store.id, product, new_variant_id, 1, "variant_transfer_in" if new_variant_id else "manual_adjustment", "serial_reassigned" if new_variant_id else "serial_status", context.user.id)
    serial.variant_id = new_variant_id
    await db.commit()
    await db.refresh(serial)
    names = await supplier_name_map(db, {serial.supplier_id})
    return serial_read(serial, names.get(serial.supplier_id))


@router.delete("/serials/{serial_id}", tags=["catalog"])
async def delete_product_serial(serial_id: UUID, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    """Remove a mistakenly-entered unit from stock.

    Only units that were never sold can be deleted: a sold unit carries the sale,
    receipt, warranty and condition history, so deleting it would rewrite the
    audit trail. Its stock is released if it was actually counted.
    """
    serial = (await db.execute(select(ProductSerial).where(ProductSerial.id == serial_id, ProductSerial.company_id == membership.company_id))).scalar_one_or_none()
    if not serial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serial not found")
    if serial.status == "sold" or serial.order_item_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete a unit that has already been sold")
    serial_number = serial.serial_number
    # Unattributed units on a variant product were never counted, so
    # adjust_serial_stock leaves those balances untouched.
    if serial.status == "in_stock":
        product = (await db.execute(select(Product).where(Product.id == serial.product_id))).scalar_one_or_none()
        if product:
            await adjust_serial_stock(db, context.store.id, product, serial.variant_id, -1, "manual_adjustment", "serial_deleted", context.user.id)
    await db.delete(serial)
    await db.commit()
    return {"deleted": True, "serial_number": serial_number}


@router.get("/serials", response_model=list[SerialLookupRead], tags=["catalog"])
async def search_serials(query: str | None = Query(default=None, max_length=120), limit: int = Query(default=50, ge=1, le=200), membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[SerialLookupRead]:
    statement = (
        select(ProductSerial, Product.name, ProductVariant.name, Supplier.name, Order.order_number, Order.customer_name)
        .join(Product, Product.id == ProductSerial.product_id)
        .outerjoin(ProductVariant, ProductVariant.id == ProductSerial.variant_id)
        .outerjoin(Supplier, Supplier.id == ProductSerial.supplier_id)
        .outerjoin(OrderItem, OrderItem.id == ProductSerial.order_item_id)
        .outerjoin(Order, Order.id == OrderItem.order_id)
        .where(ProductSerial.company_id == membership.company_id)
        .order_by(ProductSerial.created_at.desc())
        .limit(limit)
    )
    term = (query or "").strip()
    if term:
        like = f"%{term}%"
        statement = statement.where(ProductSerial.serial_number.ilike(like) | ProductSerial.imei.ilike(like))
    rows = (await db.execute(statement)).all()
    return [
        SerialLookupRead(id=serial.id, serial_number=serial.serial_number, imei=serial.imei, status=serial.status, product_id=serial.product_id, product_name=product_name, variant_id=serial.variant_id, variant_name=variant_name, store_id=serial.store_id, cost_price=serial.cost_price, supplier_warranty_months=serial.supplier_warranty_months, supplier_warranty_until=serial.supplier_warranty_until, customer_warranty_months=serial.customer_warranty_months, customer_warranty_until=serial.customer_warranty_until, sold_at=serial.sold_at, condition_grade=serial.condition_grade, battery_health=serial.battery_health, battery_cycle_count=serial.battery_cycle_count, supplier_id=serial.supplier_id, supplier_name=supplier_name, order_number=order_number, customer_name=customer_name, photos=[SerialPhotoRead.model_validate(photo) for photo in serial.photos], created_at=serial.created_at, updated_at=serial.updated_at)
        for serial, product_name, variant_name, supplier_name, order_number, customer_name in rows
    ]


async def serial_for_company(db: AsyncSession, serial_id: UUID, company_id: UUID) -> ProductSerial:
    serial = (await db.execute(select(ProductSerial).where(ProductSerial.id == serial_id, ProductSerial.company_id == company_id))).scalar_one_or_none()
    if not serial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serial not found")
    return serial


@router.get("/serials/{serial_id}/conditions", response_model=list[SerialConditionHistoryRead], tags=["catalog"])
async def list_serial_conditions(serial_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[SerialConditionHistoryRead]:
    await serial_for_company(db, serial_id, membership.company_id)
    rows = (await db.execute(select(SerialConditionHistory).where(SerialConditionHistory.serial_id == serial_id).order_by(SerialConditionHistory.graded_at.desc()))).scalars().all()
    return [SerialConditionHistoryRead.model_validate(row) for row in rows]


@router.post("/serials/{serial_id}/conditions", response_model=SerialConditionHistoryRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def record_serial_condition_endpoint(serial_id: UUID, payload: SerialConditionRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> SerialConditionHistoryRead:
    serial = await serial_for_company(db, serial_id, membership.company_id)
    if payload.condition_grade is not None:
        serial.condition_grade = payload.condition_grade
    if payload.battery_health is not None:
        serial.battery_health = payload.battery_health
    if payload.battery_cycle_count is not None:
        serial.battery_cycle_count = payload.battery_cycle_count
    if payload.condition_report is not None:
        serial.condition_report = payload.condition_report
    history = stage_serial_condition(db, membership.company_id, serial, context.user.id)
    await db.commit()
    await db.refresh(history)
    return SerialConditionHistoryRead.model_validate(history)


@router.get("/serials/{serial_id}/photos", response_model=list[SerialPhotoRead], tags=["catalog"])
async def list_serial_photos(serial_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[SerialPhotoRead]:
    await serial_for_company(db, serial_id, membership.company_id)
    rows = (await db.execute(select(ProductSerialPhoto).where(ProductSerialPhoto.serial_id == serial_id).order_by(ProductSerialPhoto.position, ProductSerialPhoto.created_at))).scalars().all()
    return [SerialPhotoRead.model_validate(row) for row in rows]


@router.post("/serials/{serial_id}/photos", response_model=list[SerialPhotoRead], status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def add_serial_photo(serial_id: UUID, file: UploadFile = File(...), context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> list[SerialPhotoRead]:
    """Attach a photo of this exact unit. Many photos per serial are allowed."""
    serial = await serial_for_company(db, serial_id, membership.company_id)
    suffix, content = await read_image_upload(file)
    asset = await upsert_media_asset(db, company_id=membership.company_id, created_by=membership.user_id, content=content, suffix=suffix, filename=file.filename, content_type=file.content_type)
    next_position = (await db.execute(select(func.count()).select_from(ProductSerialPhoto).where(ProductSerialPhoto.serial_id == serial.id))).scalar_one()
    db.add(ProductSerialPhoto(company_id=membership.company_id, serial_id=serial.id, url=asset.url, position=next_position))
    await db.commit()
    rows = (await db.execute(select(ProductSerialPhoto).where(ProductSerialPhoto.serial_id == serial.id).order_by(ProductSerialPhoto.position, ProductSerialPhoto.created_at))).scalars().all()
    return [SerialPhotoRead.model_validate(row) for row in rows]


@router.delete("/serial-photos/{photo_id}", status_code=status.HTTP_200_OK, tags=["catalog"])
async def delete_serial_photo(photo_id: UUID, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    photo = (await db.execute(select(ProductSerialPhoto).where(ProductSerialPhoto.id == photo_id, ProductSerialPhoto.company_id == membership.company_id))).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    await db.delete(photo)
    await db.commit()
    return {"deleted": str(photo_id)}


@router.get("/serials/{serial_id}/tickets", response_model=list[SerialServiceTicketRead], tags=["catalog"])
async def list_serial_tickets(serial_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[SerialServiceTicketRead]:
    await serial_for_company(db, serial_id, membership.company_id)
    rows = (await db.execute(select(SerialServiceTicket).where(SerialServiceTicket.serial_id == serial_id).order_by(SerialServiceTicket.created_at.desc()))).scalars().all()
    return [SerialServiceTicketRead.model_validate(row) for row in rows]


@router.post("/serials/{serial_id}/tickets", response_model=SerialServiceTicketRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_serial_ticket(serial_id: UUID, payload: SerialServiceTicketCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> SerialServiceTicketRead:
    await serial_for_company(db, serial_id, membership.company_id)
    ticket = SerialServiceTicket(company_id=membership.company_id, serial_id=serial_id, store_id=context.store.id, ticket_type=payload.ticket_type, status="open", summary=payload.summary.strip(), description=(payload.description.strip() if payload.description else None), cost=payload.cost, created_by=context.user.id)
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return SerialServiceTicketRead.model_validate(ticket)


@router.patch("/tickets/{ticket_id}", response_model=SerialServiceTicketRead, tags=["catalog"])
async def update_serial_ticket(ticket_id: UUID, payload: SerialServiceTicketUpdateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> SerialServiceTicketRead:
    ticket = (await db.execute(select(SerialServiceTicket).where(SerialServiceTicket.id == ticket_id, SerialServiceTicket.company_id == membership.company_id))).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if payload.summary is not None:
        ticket.summary = payload.summary.strip()
    if payload.description is not None:
        ticket.description = payload.description.strip() or None
    if payload.cost is not None:
        ticket.cost = payload.cost
    previous_status = ticket.status
    if payload.status is not None:
        ticket.status = payload.status
        ticket.resolved_at = utcnow() if payload.status == "resolved" else None
    await db.commit()
    await db.refresh(ticket)
    # Best-effort customer notice when a repair/inspection is resolved.
    if ticket.status == "resolved" and previous_status != "resolved":
        try:
            serial = await db.get(ProductSerial, ticket.serial_id)
            item = await db.get(OrderItem, serial.order_item_id) if serial and serial.order_item_id else None
            order = await db.get(Order, item.order_id) if item else None
            customer = await db.get(Customer, order.customer_id) if order and order.customer_id else None
            if serial and item and customer and customer.email:
                if await queue_service_ticket_email(
                    db,
                    context.store,
                    recipient=customer.email,
                    customer_name=customer.name,
                    product_name=item.product_name,
                    serial_number=serial.serial_number,
                    ticket_type=ticket.ticket_type,
                    summary=ticket.summary,
                ):
                    await db.commit()
        except Exception:
            await db.rollback()
            logging.getLogger(__name__).exception("Could not queue the service-ticket email")
    return SerialServiceTicketRead.model_validate(ticket)


def modifier_group_read(group: ModifierGroup) -> ModifierGroupRead:
    return ModifierGroupRead(
        id=group.id,
        name=group.name,
        min_select=group.min_select,
        max_select=group.max_select,
        is_required=group.is_required,
        position=group.position,
        modifiers=[ModifierRead.model_validate(modifier) for modifier in group.modifiers],
    )


@router.get("/modifier-groups", response_model=list[ModifierGroupRead], tags=["catalog"])
async def list_modifier_groups(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[ModifierGroupRead]:
    groups = (await db.execute(select(ModifierGroup).where(ModifierGroup.company_id == membership.company_id).options(selectinload(ModifierGroup.modifiers)).order_by(ModifierGroup.position, ModifierGroup.name))).scalars().all()
    return [modifier_group_read(group) for group in groups]


@router.post("/modifier-groups", response_model=ModifierGroupRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_modifier_group(payload: ModifierGroupInput, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ModifierGroupRead:
    group = ModifierGroup(company_id=membership.company_id, name=payload.name.strip(), min_select=payload.min_select, max_select=payload.max_select, is_required=payload.is_required)
    db.add(group)
    await db.flush()
    for index, item in enumerate(payload.modifiers):
        db.add(Modifier(group_id=group.id, name=item.name.strip(), price_delta=item.price_delta, ingredient_product_id=item.ingredient_product_id, quantity=item.quantity, is_default=item.is_default, position=index))
    await db.commit()
    result = await db.execute(select(ModifierGroup).where(ModifierGroup.id == group.id).options(selectinload(ModifierGroup.modifiers)))
    return modifier_group_read(result.scalar_one())


@router.patch("/modifier-groups/{group_id}", response_model=ModifierGroupRead, tags=["catalog"])
async def update_modifier_group(group_id: UUID, payload: ModifierGroupInput, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ModifierGroupRead:
    group = (await db.execute(select(ModifierGroup).where(ModifierGroup.id == group_id, ModifierGroup.company_id == membership.company_id).options(selectinload(ModifierGroup.modifiers)))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modifier group not found")
    group.name = payload.name.strip()
    group.min_select = payload.min_select
    group.max_select = payload.max_select
    group.is_required = payload.is_required
    for modifier in list(group.modifiers):
        await db.delete(modifier)
    await db.flush()
    for index, item in enumerate(payload.modifiers):
        db.add(Modifier(group_id=group.id, name=item.name.strip(), price_delta=item.price_delta, ingredient_product_id=item.ingredient_product_id, quantity=item.quantity, is_default=item.is_default, position=index))
    await db.commit()
    result = await db.execute(select(ModifierGroup).where(ModifierGroup.id == group.id).options(selectinload(ModifierGroup.modifiers)))
    return modifier_group_read(result.scalar_one())


@router.delete("/modifier-groups/{group_id}", tags=["catalog"])
async def delete_modifier_group(group_id: UUID, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    group = (await db.execute(select(ModifierGroup).where(ModifierGroup.id == group_id, ModifierGroup.company_id == membership.company_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modifier group not found")
    await db.delete(group)
    await db.commit()
    return {"ok": True}


def combo_read(combo: Combo) -> ComboRead:
    items: list[ComboItemRead] = []
    for item in sorted(combo.items, key=lambda row: (row.position, str(row.id))):
        unit_price = item.variant.price if item.variant is not None and item.variant.price is not None else item.product.price
        items.append(
            ComboItemRead(
                id=item.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                product_name=item.product.name,
                variant_name=item.variant.name if item.variant else None,
                sku=item.variant.sku if item.variant else item.product.sku,
                quantity=float(item.quantity),
                unit_price=unit_price,
                position=item.position,
            )
        )
    groups: list[ComboGroupRead] = []
    for group in sorted(combo.groups, key=lambda row: (row.position, str(row.id))):
        options: list[ComboGroupOptionRead] = []
        for option in sorted(group.options, key=lambda row: (row.position, str(row.id))):
            options.append(
                ComboGroupOptionRead(
                    id=option.id,
                    product_id=option.product_id,
                    variant_id=option.variant_id,
                    product_name=option.product.name,
                    variant_name=option.variant.name if option.variant else None,
                    sku=option.variant.sku if option.variant else option.product.sku,
                    price_delta=option.price_delta,
                    position=option.position,
                )
            )
        groups.append(
            ComboGroupRead(
                id=group.id,
                name=group.name,
                min_select=group.min_select,
                max_select=group.max_select,
                is_required=group.is_required,
                position=group.position,
                options=options,
            )
        )
    return ComboRead(
        id=combo.id,
        company_id=combo.company_id,
        name=combo.name,
        sku=combo.sku,
        description=combo.description,
        image=combo.image,
        price=combo.price,
        is_active=combo.is_active,
        position=combo.position,
        created_at=combo.created_at,
        updated_at=combo.updated_at,
        items=items,
        groups=groups,
    )


def _combo_options() -> tuple:
    return (
        selectinload(Combo.items).selectinload(ComboItem.product),
        selectinload(Combo.items).selectinload(ComboItem.variant),
        selectinload(Combo.groups).selectinload(ComboGroup.options).selectinload(ComboGroupOption.product),
        selectinload(Combo.groups).selectinload(ComboGroup.options).selectinload(ComboGroupOption.variant),
    )


async def _validate_combo_components(db: AsyncSession, company_id: UUID, items: list, groups: list) -> None:
    """Every item and every group option must be an active product of this company (and a matching variant)."""
    pairs: list[tuple[UUID, UUID | None]] = [(item.product_id, item.variant_id) for item in items]
    for group in groups:
        if group.min_select < 0 or group.max_select < 1 or group.min_select > group.max_select:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Group {group.name} has an invalid selection range")
        pairs += [(option.product_id, option.variant_id) for option in group.options]
    product_ids = {product_id for product_id, _ in pairs}
    products = {product.id: product for product in (await db.execute(select(Product).where(Product.id.in_(product_ids), Product.company_id == company_id, Product.is_active.is_(True)))).scalars().all()}
    if len(products) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more combo products are not available")
    variant_ids = {variant_id for _, variant_id in pairs if variant_id}
    variants: dict[UUID, ProductVariant] = {}
    if variant_ids:
        variants = {variant.id: variant for variant in (await db.execute(select(ProductVariant).where(ProductVariant.id.in_(variant_ids), ProductVariant.is_active.is_(True)))).scalars().all()}
        if len(variants) != len(variant_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more combo variants are not available")
    for product_id, variant_id in pairs:
        if variant_id and (variant_id not in variants or variants[variant_id].product_id != product_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Combo variant does not belong to its product")


@router.get("/combos", response_model=list[ComboRead], tags=["catalog"])
async def list_combos(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[ComboRead]:
    combos = (await db.execute(select(Combo).where(Combo.company_id == membership.company_id).options(*_combo_options()).order_by(Combo.position, Combo.name))).scalars().all()
    return [combo_read(combo) for combo in combos]


@router.post("/combos", response_model=ComboRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_combo(payload: ComboInput, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ComboRead:
    await _validate_combo_components(db, membership.company_id, payload.items, payload.groups)
    combo = Combo(company_id=membership.company_id, name=payload.name.strip(), sku=(payload.sku.strip() if payload.sku else None), description=payload.description, image=payload.image, price=payload.price, is_active=payload.is_active)
    db.add(combo)
    await db.flush()
    for index, item in enumerate(payload.items):
        db.add(ComboItem(combo_id=combo.id, product_id=item.product_id, variant_id=item.variant_id, quantity=item.quantity, position=index))
    for group_index, group in enumerate(payload.groups):
        group_row = ComboGroup(combo_id=combo.id, name=group.name.strip(), min_select=group.min_select, max_select=group.max_select, is_required=group.is_required, position=group_index)
        db.add(group_row)
        await db.flush()
        for option_index, option in enumerate(group.options):
            db.add(ComboGroupOption(group_id=group_row.id, product_id=option.product_id, variant_id=option.variant_id, price_delta=option.price_delta, position=option_index))
    await db.commit()
    result = await db.execute(select(Combo).where(Combo.id == combo.id).options(*_combo_options()))
    return combo_read(result.scalar_one())


@router.patch("/combos/{combo_id}", response_model=ComboRead, tags=["catalog"])
async def update_combo(combo_id: UUID, payload: ComboInput, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ComboRead:
    combo = (await db.execute(select(Combo).where(Combo.id == combo_id, Combo.company_id == membership.company_id).options(selectinload(Combo.items), selectinload(Combo.groups)))).scalar_one_or_none()
    if not combo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combo not found")
    await _validate_combo_components(db, membership.company_id, payload.items, payload.groups)
    combo.name = payload.name.strip()
    combo.sku = payload.sku.strip() if payload.sku else None
    combo.description = payload.description
    combo.image = payload.image
    combo.price = payload.price
    combo.is_active = payload.is_active
    for item in list(combo.items):
        await db.delete(item)
    for group in list(combo.groups):
        await db.delete(group)
    await db.flush()
    for index, item in enumerate(payload.items):
        db.add(ComboItem(combo_id=combo.id, product_id=item.product_id, variant_id=item.variant_id, quantity=item.quantity, position=index))
    for group_index, group in enumerate(payload.groups):
        group_row = ComboGroup(combo_id=combo.id, name=group.name.strip(), min_select=group.min_select, max_select=group.max_select, is_required=group.is_required, position=group_index)
        db.add(group_row)
        await db.flush()
        for option_index, option in enumerate(group.options):
            db.add(ComboGroupOption(group_id=group_row.id, product_id=option.product_id, variant_id=option.variant_id, price_delta=option.price_delta, position=option_index))
    await db.commit()
    result = await db.execute(select(Combo).where(Combo.id == combo.id).options(*_combo_options()))
    return combo_read(result.scalar_one())


@router.delete("/combos/{combo_id}", tags=["catalog"])
async def delete_combo(combo_id: UUID, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    combo = (await db.execute(select(Combo).where(Combo.id == combo_id, Combo.company_id == membership.company_id))).scalar_one_or_none()
    if not combo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combo not found")
    await db.delete(combo)
    await db.commit()
    return {"ok": True}


def batch_read(batch: ProductBatch) -> ProductBatchRead:
    return ProductBatchRead(
        id=batch.id,
        product_id=batch.product_id,
        variant_id=batch.variant_id,
        store_id=batch.store_id,
        batch_code=batch.batch_code,
        expiry_date=batch.expiry_date,
        quantity_on_hand=batch.quantity_on_hand,
        cost_price=batch.cost_price,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


@router.get("/products/{product_id}/batches", response_model=list[ProductBatchRead], tags=["catalog"])
async def list_product_batches(product_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[ProductBatchRead]:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == context.membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    rows = (await db.execute(select(ProductBatch).where(ProductBatch.product_id == product.id).order_by(ProductBatch.expiry_date.asc().nulls_last(), ProductBatch.created_at))).scalars().all()
    return [batch_read(batch) for batch in rows]


@router.post("/products/{product_id}/batches", response_model=list[ProductBatchRead], status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def add_product_batches(product_id: UUID, payload: ProductBatchesSetRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> list[ProductBatchRead]:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    created: list[ProductBatch] = []
    for item in payload.batches:
        batch = ProductBatch(company_id=membership.company_id, product_id=product.id, variant_id=item.variant_id, store_id=context.store.id, batch_code=(item.batch_code.strip() if item.batch_code else None), expiry_date=item.expiry_date, quantity_on_hand=item.quantity_on_hand, cost_price=item.cost_price)
        db.add(batch)
        created.append(batch)
    await db.commit()
    for batch in created:
        await db.refresh(batch)
    return [batch_read(batch) for batch in created]


@router.get("/inventory/expiring-batches", response_model=list[ExpiringBatchRead], tags=["inventory"])
async def list_expiring_batches(days: int = Query(default=30, ge=0, le=365), context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[ExpiringBatchRead]:
    """Batches at this store with stock left that expire within ``days`` (or already have)."""
    today = now_utc().date()
    cutoff = today + timedelta(days=days)
    rows = (await db.execute(
        select(ProductBatch, Product, ProductVariant)
        .join(Product, Product.id == ProductBatch.product_id)
        .outerjoin(ProductVariant, ProductVariant.id == ProductBatch.variant_id)
        .where(
            ProductBatch.store_id == context.store.id,
            ProductBatch.quantity_on_hand > 0,
            ProductBatch.expiry_date.isnot(None),
            ProductBatch.expiry_date <= cutoff,
        )
        .order_by(ProductBatch.expiry_date.asc())
    )).all()
    return [
        ExpiringBatchRead(
            id=batch.id,
            product_id=batch.product_id,
            product_name=product.name,
            variant_id=batch.variant_id,
            variant_name=variant.name if variant else None,
            batch_code=batch.batch_code,
            expiry_date=batch.expiry_date,
            quantity_on_hand=batch.quantity_on_hand,
            days_until_expiry=(batch.expiry_date - today).days if batch.expiry_date else None,
        )
        for batch, product, variant in rows
    ]


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_IMAGE_BYTES = 5_000_000


async def read_image_upload(file: UploadFile) -> tuple[str, bytes]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported image type")
    content = await file.read()
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image must be 1 byte to 5MB")
    return suffix, content


@router.post("/products/{product_id}/image", response_model=ProductRead, tags=["catalog"])
async def upload_product_image(product_id: UUID, file: UploadFile = File(...), context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductRead:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id).options(selectinload(Product.category)))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    suffix, content = await read_image_upload(file)
    asset = await upsert_media_asset(db, company_id=membership.company_id, created_by=membership.user_id, content=content, suffix=suffix, filename=file.filename, content_type=file.content_type)
    product.image = asset.url
    await db.commit()
    refreshed = (await db.execute(select(Product).where(Product.id == product.id).options(selectinload(Product.category)))).scalar_one()
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))
    return product_read(refreshed, balance_result.scalar_one_or_none(), await load_product_variants(db, context.store.id, refreshed))


@router.post("/products/{product_id}/variants/{variant_id}/image", response_model=ProductRead, tags=["catalog"])
async def upload_variant_image(product_id: UUID, variant_id: UUID, file: UploadFile = File(...), context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductRead:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id).options(selectinload(Product.category)))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.product_id == product.id))).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    suffix, content = await read_image_upload(file)
    asset = await upsert_media_asset(db, company_id=membership.company_id, created_by=membership.user_id, content=content, suffix=suffix, filename=file.filename, content_type=file.content_type)
    variant.image = asset.url
    await db.commit()
    refreshed = (await db.execute(select(Product).where(Product.id == product.id).options(selectinload(Product.category)))).scalar_one()
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))
    return product_read(refreshed, balance_result.scalar_one_or_none(), await load_product_variants(db, context.store.id, refreshed))


@router.get("/media/assets", response_model=list[MediaAssetRead], tags=["catalog"])
async def list_media_assets(search: str | None = None, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> list[MediaAssetRead]:
    query = select(MediaAsset).where(MediaAsset.company_id == membership.company_id)
    if search and search.strip():
        query = query.where(MediaAsset.original_filename.ilike(f"%{search.strip()}%"))
    rows = (await db.execute(query.order_by(MediaAsset.created_at.desc()))).scalars().all()
    return [MediaAssetRead.model_validate(row) for row in rows]


@router.post("/media/assets", response_model=MediaAssetRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_media_asset(file: UploadFile = File(...), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> MediaAssetRead:
    suffix, content = await read_image_upload(file)
    asset = await upsert_media_asset(db, company_id=membership.company_id, created_by=membership.user_id, content=content, suffix=suffix, filename=file.filename, content_type=file.content_type)
    await db.commit()
    await db.refresh(asset)
    return MediaAssetRead.model_validate(asset)


@router.delete("/media/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["catalog"])
async def delete_media_asset(asset_id: UUID, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> Response:
    asset = (await db.execute(select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.company_id == membership.company_id))).scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    in_use_product = (await db.execute(select(Product.id).where(Product.company_id == membership.company_id, Product.image == asset.url).limit(1))).scalar_one_or_none()
    in_use_variant = (await db.execute(select(ProductVariant.id).join(Product, Product.id == ProductVariant.product_id).where(Product.company_id == membership.company_id, ProductVariant.image == asset.url).limit(1))).scalar_one_or_none()
    if in_use_product or in_use_variant:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This image is used by a product or variant")
    url = asset.url
    await db.delete(asset)
    await db.commit()
    delete_by_url(url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def stock_state(on_hand: Decimal, reorder_point: Decimal | int) -> str:
    return "out" if on_hand == 0 else "low" if on_hand <= reorder_point else "healthy"


async def inventory_for_product(db: AsyncSession, store_id: UUID, product: Product) -> InventoryRead:
    result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store_id, InventoryBalance.product_id == product.id))
    balance = result.scalar_one_or_none()
    on_hand = balance.on_hand if balance else Decimal("0")
    reorder_point = balance.reorder_point if balance else 10
    variant_rows: list[InventoryVariantRead] = []
    variants = (await db.execute(select(ProductVariant).where(ProductVariant.product_id == product.id).order_by(ProductVariant.position, ProductVariant.name))).scalars().all()
    if variants:
        balances = {row.variant_id: row for row in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store_id, VariantInventoryBalance.variant_id.in_([variant.id for variant in variants])))).scalars().all()}
        for variant in variants:
            variant_balance = balances.get(variant.id)
            variant_on_hand = variant_balance.on_hand if variant_balance else Decimal("0")
            variant_reorder = variant_balance.reorder_point if variant_balance else 10
            variant_rows.append(InventoryVariantRead(variant_id=variant.id, name=variant.name, sku=variant.sku, on_hand=float(variant_on_hand), reorder_point=variant_reorder, status=stock_state(variant_on_hand, variant_reorder), price=variant.price, cost_price=variant.cost_price))
    return InventoryRead(store_id=store_id, product_id=product.id, product_name=product.name, sku=product.sku, price=product.price, cost_price=product.cost_price, on_hand=float(on_hand), reorder_point=reorder_point, status=stock_state(on_hand, reorder_point), updated_at=balance.updated_at if balance else product.updated_at, track_serials=product.track_serials, image=product.image, variants=variant_rows)


@router.get("/inventory", response_model=list[InventoryRead], tags=["inventory"])
async def list_inventory(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), low_stock: bool = False) -> list[InventoryRead]:
    products = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.is_active.is_(True)).order_by(Product.name))).scalars().all()
    inventory = [await inventory_for_product(db, context.store.id, product) for product in products]

    def effective_status(item: InventoryRead) -> str:
        # A variant product keeps its stock per variant and leaves the
        # product-level balance at zero, so judge the summed variant stock.
        quantity = sum(variant.on_hand for variant in item.variants) if item.variants else item.on_hand
        return stock_state(quantity, item.reorder_point or 10)

    return [item for item in inventory if not low_stock or effective_status(item) in {"low", "out"}]


@router.get("/inventory/movements", response_model=list[StockMovementRead], tags=["inventory"])
async def list_stock_movements(context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db), product_id: UUID | None = None, variant_id: UUID | None = None, limit: int = Query(default=100, ge=1, le=300)) -> list[StockMovementRead]:
    """Recent stock changes for this store, newest first.

    Every restock, sale, refund, transfer and manual adjustment lands here with
    its reason, so a balance can always be explained.
    """
    await require_plan_feature(db, membership.company_id, "inventory_management")
    statement = (
        select(StockMovement, Product.name, ProductVariant.name, User.full_name)
        .join(Product, Product.id == StockMovement.product_id)
        .outerjoin(ProductVariant, ProductVariant.id == StockMovement.variant_id)
        .outerjoin(User, User.id == StockMovement.created_by)
        .where(StockMovement.store_id == context.store.id, Product.company_id == membership.company_id)
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    )
    if product_id:
        statement = statement.where(StockMovement.product_id == product_id)
    if variant_id:
        statement = statement.where(StockMovement.variant_id == variant_id)
    rows = (await db.execute(statement)).all()
    return [
        StockMovementRead(
            id=movement.id,
            created_at=movement.created_at,
            product_id=movement.product_id,
            product_name=product_name,
            variant_id=movement.variant_id,
            variant_name=variant_name,
            quantity=movement.quantity,
            movement_type=movement.movement_type,
            reason=movement.reason,
            reference_id=movement.reference_id,
            unit_cost=movement.unit_cost,
            actor=actor_name,
        )
        for movement, product_name, variant_name, actor_name in rows
    ]


@router.patch("/inventory/{product_id}", response_model=InventoryRead, tags=["inventory"])
async def adjust_inventory(product_id: UUID, payload: InventoryAdjustRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> InventoryRead:
    await require_plan_feature(db, membership.company_id, "inventory_management")
    product_result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id, Product.is_active.is_(True)))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if payload.variant_id:
        variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == payload.variant_id, ProductVariant.product_id == product.id))).scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
        existing = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id == variant.id))).scalar_one_or_none()
    else:
        existing = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))).scalar_one_or_none()
    difference = payload.quantity - (existing.on_hand if existing else Decimal("0"))
    policy = await load_approval_policy(db, membership.company_id)
    rule = policy.rules.get("stock_write_off")
    gate = approval_gate(rule, abs(difference)) if policy.enabled else "allow"
    if gate == "request":
        is_approver = rule is not None and membership.role in rule.approvers
        if not (is_approver and not (policy.maker_checker and membership.role != "owner")):
            return await _pending_approval_response(db, membership, store_id=context.store.id, action="stock_write_off", amount=abs(difference), payload={"product_id": str(product.id), "variant_id": str(payload.variant_id) if payload.variant_id else None, "quantity": str(payload.quantity), "reason": payload.reason}, user=context.user, reason=payload.reason)
    result = await _apply_inventory_change(db, store_id=context.store.id, membership=membership, product=product, variant_id=payload.variant_id, quantity=payload.quantity, reason=payload.reason, user=context.user)
    if gate == "review":
        await log_audit(db, membership, context.store.id, "stock_write_off_reviewed", "inventory", entity_id=product.id, details={"product": product.name, "difference": str(difference), "mode": "review"}, user=context.user)
        await notify_company_managers(db, membership.company_id, context.store.id, "stock_write_off_review", f"Stock adjustment flagged: {product.name}", f"{difference} units by {context.user.full_name}")
        await db.commit()
    return result


async def create_received_serial(
    db: AsyncSession,
    *,
    company_id: UUID,
    store_id: UUID,
    product: Product,
    variant_id: UUID | None,
    serial_number: str,
    entry: InventoryRestockSerialInput | None,
    default_unit_cost: Decimal | None,
    default_supplier_months: int | None,
    default_customer_months: int | None,
    user_id: UUID,
) -> ProductSerial:
    """Create one received unit, applying any per-unit override over batch defaults."""
    supplier_months = entry.supplier_warranty_months if entry and entry.supplier_warranty_months is not None else default_supplier_months
    customer_months = entry.customer_warranty_months if entry and entry.customer_warranty_months is not None else (default_customer_months if default_customer_months is not None else supplier_months)
    unit_cost = entry.unit_cost if entry and entry.unit_cost is not None else default_unit_cost
    supplier_until = utcnow() + timedelta(days=30 * supplier_months) if supplier_months else None
    serial = ProductSerial(
        company_id=company_id,
        product_id=product.id,
        variant_id=variant_id,
        store_id=store_id,
        serial_number=serial_number,
        imei=(entry.imei.strip() if entry and entry.imei else None),
        status="in_stock",
        cost_price=unit_cost,
        supplier_warranty_months=supplier_months,
        supplier_warranty_until=supplier_until,
        customer_warranty_months=customer_months,
        supplier_id=(entry.supplier_id if entry else None),
        condition_grade=(entry.condition_grade if entry else None),
        battery_health=(entry.battery_health if entry else None),
        battery_cycle_count=(entry.battery_cycle_count if entry else None),
        condition_report=(entry.condition_report if entry else None),
    )
    db.add(serial)
    await db.flush()
    if entry and (entry.condition_grade is not None or entry.battery_health is not None or entry.battery_cycle_count is not None or entry.condition_report is not None):
        stage_serial_condition(db, company_id, serial, user_id)
    return serial


@router.post("/inventory/{product_id}/restock", response_model=InventoryRead, tags=["inventory"])
async def restock_inventory(product_id: UUID, payload: InventoryRestockRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> InventoryRead:
    await require_plan_feature(db, membership.company_id, "inventory_management")
    product_result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id, Product.is_active.is_(True)))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    detail = payload.reason or (f"Received from {payload.supplier}" if payload.supplier else "Stock received")
    serial_values: list[str] = []
    entries_by_number: dict[str, InventoryRestockSerialInput] = {}
    if payload.serials is not None:
        if not product.track_serials:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product does not track serials")
        for entry in payload.serials:
            number = entry.serial_number.strip()
            if not number:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Serial number is required")
            if number in entries_by_number:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate serial numbers in request")
            entries_by_number[number] = entry
        serial_values = list(entries_by_number)
        if payload.quantity != int(payload.quantity) or len(serial_values) != int(payload.quantity):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide one serial per unit received")
        clashes = (await db.execute(select(ProductSerial.serial_number).where(ProductSerial.company_id == membership.company_id, ProductSerial.serial_number.in_(serial_values)))).scalars().all()
        if clashes:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial already exists: {clashes[0]}")
        entry_supplier_ids = {entry.supplier_id for entry in entries_by_number.values() if entry.supplier_id}
        if entry_supplier_ids:
            found_suppliers = set((await db.execute(select(Supplier.id).where(Supplier.id.in_(entry_supplier_ids), Supplier.company_id == membership.company_id))).scalars().all())
            if entry_supplier_ids - found_suppliers:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supplier not found")
    elif payload.serial_numbers:
        if not product.track_serials:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product does not track serials")
        serial_values = [value.strip() for value in payload.serial_numbers if value.strip()]
        if len(serial_values) != len(set(serial_values)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate serial numbers in request")
        if payload.quantity != int(payload.quantity) or len(serial_values) != int(payload.quantity):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide one serial per unit received")
        clashes = (await db.execute(select(ProductSerial.serial_number).where(ProductSerial.company_id == membership.company_id, ProductSerial.serial_number.in_(serial_values)))).scalars().all()
        if clashes:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial already exists: {clashes[0]}")
    elif product.track_serials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide one serial per unit received")
    customer_months = payload.customer_warranty_months if payload.customer_warranty_months is not None else payload.supplier_warranty_months
    # Movement cost is a batch aggregate; per-unit costs live on the serials. When
    # only per-unit costs are supplied, record their average so the ledger is not blank.
    movement_unit_cost = payload.unit_cost
    entry_costs = [entry.unit_cost for entry in entries_by_number.values() if entry.unit_cost is not None]
    if entry_costs:
        movement_unit_cost = (sum(entry_costs) / Decimal(len(entry_costs))).quantize(Decimal("0.01"))
    if payload.variant_id:
        variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == payload.variant_id, ProductVariant.product_id == product.id))).scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
        balance_result = await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id == variant.id).with_for_update())
        balance = balance_result.scalar_one_or_none()
        if not balance:
            balance = VariantInventoryBalance(store_id=context.store.id, variant_id=variant.id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
        balance.on_hand += payload.quantity
        db.add(StockMovement(store_id=context.store.id, product_id=product.id, variant_id=variant.id, quantity=payload.quantity, movement_type="restock", reason=detail, reference_id=payload.reference or payload.supplier, unit_cost=movement_unit_cost, created_by=context.user.id))
        if balance.on_hand <= (balance.reorder_point or 10):
            await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name} · {variant.name}", f"Only {balance.on_hand} left (reorder point {balance.reorder_point or 10})")
        for serial_number in serial_values:
            await create_received_serial(db, company_id=membership.company_id, store_id=context.store.id, product=product, variant_id=variant.id, serial_number=serial_number, entry=entries_by_number.get(serial_number), default_unit_cost=payload.unit_cost, default_supplier_months=payload.supplier_warranty_months, default_customer_months=customer_months, user_id=context.user.id)
        await db.commit()
        return await inventory_for_product(db, context.store.id, product)
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id).with_for_update())
    balance = balance_result.scalar_one_or_none()
    if not balance:
        balance = InventoryBalance(store_id=context.store.id, product_id=product.id, on_hand=0, reorder_point=10)
        db.add(balance)
        await db.flush()
    balance.on_hand += payload.quantity
    db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=payload.quantity, movement_type="restock", reason=detail, reference_id=payload.reference or payload.supplier, unit_cost=movement_unit_cost, created_by=context.user.id))
    if balance.on_hand <= (balance.reorder_point or 10):
        await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name}", f"Only {balance.on_hand} left (reorder point {balance.reorder_point or 10})")
    for serial_number in serial_values:
        await create_received_serial(db, company_id=membership.company_id, store_id=context.store.id, product=product, variant_id=None, serial_number=serial_number, entry=entries_by_number.get(serial_number), default_unit_cost=payload.unit_cost, default_supplier_months=payload.supplier_warranty_months, default_customer_months=customer_months, user_id=context.user.id)
    await db.commit()
    return await inventory_for_product(db, context.store.id, product)


@router.post("/inventory/{product_id}/variant-transfer", response_model=InventoryRead, tags=["inventory"])
async def transfer_variant_stock(product_id: UUID, payload: VariantStockTransferRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> InventoryRead:
    """Move stock between two variants of the same product in one atomic step.

    This is the fix for a mis-entered balance: instead of setting each variant
    separately (where the total can silently drift), the source is decremented
    and the destination incremented by the same amount, and both movements are
    recorded so the correction stays auditable.
    """
    await require_plan_feature(db, membership.company_id, "inventory_management")
    product_result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id, Product.is_active.is_(True)))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if payload.from_variant_id == payload.to_variant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination variants must be different")
    if product.track_serials:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This product tracks serials; reassign the serial to the correct variant instead of moving stock")
    variant_ids = [payload.from_variant_id, payload.to_variant_id]
    variant_rows = (await db.execute(select(ProductVariant).where(ProductVariant.id.in_(variant_ids), ProductVariant.product_id == product.id))).scalars().all()
    variants = {variant.id: variant for variant in variant_rows}
    if len(variants) != 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    # Lock both balances in a stable (variant_id) order so simultaneous transfers
    # in opposite directions cannot deadlock.
    locked = await db.execute(
        select(VariantInventoryBalance)
        .where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id.in_(variant_ids))
        .order_by(VariantInventoryBalance.variant_id)
        .with_for_update()
    )
    balances = {row.variant_id: row for row in locked.scalars().all()}
    source = balances.get(payload.from_variant_id)
    source_on_hand = source.on_hand if source else Decimal("0")
    if source_on_hand < payload.quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock: {variants[payload.from_variant_id].name} has only {source_on_hand}")
    if source is None:
        source = VariantInventoryBalance(store_id=context.store.id, variant_id=payload.from_variant_id, on_hand=0, reorder_point=10)
        db.add(source)
        await db.flush()
    target = balances.get(payload.to_variant_id)
    if target is None:
        target = VariantInventoryBalance(store_id=context.store.id, variant_id=payload.to_variant_id, on_hand=0, reorder_point=10)
        db.add(target)
        await db.flush()
    source.on_hand -= payload.quantity
    target.on_hand += payload.quantity
    reference = f"VTR-{now_utc():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    db.add(StockMovement(store_id=context.store.id, product_id=product.id, variant_id=source.variant_id, quantity=-payload.quantity, movement_type="variant_transfer_out", reason=payload.reason, reference_id=reference, created_by=context.user.id))
    db.add(StockMovement(store_id=context.store.id, product_id=product.id, variant_id=target.variant_id, quantity=payload.quantity, movement_type="variant_transfer_in", reason=payload.reason, reference_id=reference, created_by=context.user.id))
    if source.on_hand <= (source.reorder_point or 10):
        await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name} · {variants[payload.from_variant_id].name}", f"Only {source.on_hand} left (reorder point {source.reorder_point or 10})")
    await log_audit(db, membership, context.store.id, "variant_stock_transferred", "inventory", entity_id=product.id, details={"reference": reference, "from_variant_id": str(payload.from_variant_id), "to_variant_id": str(payload.to_variant_id), "quantity": str(payload.quantity), "reason": payload.reason}, user=context.user)
    await record_activity(db, "inventory.variant_transferred", company_id=membership.company_id, store_id=context.store.id, details={"company": await _company_name(db, membership.company_id), "product": product.name, "from_variant": variants[payload.from_variant_id].name, "to_variant": variants[payload.to_variant_id].name, "quantity": str(payload.quantity), "reference": reference})
    await db.commit()
    return await inventory_for_product(db, context.store.id, product)


@router.post("/inventory/transfers", tags=["inventory"])
async def transfer_stock(payload: StockTransferCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, membership.company_id, "inventory_management")
    if payload.to_store_id == context.store.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination stores must be different")
    to_store_result = await db.execute(select(Store).where(Store.id == payload.to_store_id, Store.company_id == membership.company_id, Store.is_active.is_(True)))
    to_store = to_store_result.scalar_one_or_none()
    if not to_store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination store not found")
    if membership.role != "owner":
        allowed = set(await get_membership_stores(db, membership.id))
        if payload.to_store_id not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to the destination store")
    keys = [(item.product_id, item.variant_id) for item in payload.items]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate items in transfer")
    product_ids = {item.product_id for item in payload.items}
    products_result = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))
    products = {product.id: product for product in products_result.scalars().all()}
    if len(products) != len(product_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    store_ids = [context.store.id, payload.to_store_id]
    variant_ids = {item.variant_id for item in payload.items if item.variant_id}
    variants: dict[UUID, ProductVariant] = {}
    variant_map: dict[tuple[UUID, UUID], VariantInventoryBalance] = {}
    if variant_ids:
        variants_result = await db.execute(select(ProductVariant).where(ProductVariant.id.in_(variant_ids), ProductVariant.is_active.is_(True)))
        variants = {variant.id: variant for variant in variants_result.scalars().all()}
        if len(variants) != len(variant_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more variants are not available")
        for item in payload.items:
            if item.variant_id and variants[item.variant_id].product_id != item.product_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant does not match its product")
        # Lock variant balances in a consistent order (variant, store) to avoid deadlocks
        # between opposite-direction transfers running at the same time.
        variant_rows = await db.execute(
            select(VariantInventoryBalance)
            .where(VariantInventoryBalance.store_id.in_(store_ids), VariantInventoryBalance.variant_id.in_(variant_ids))
            .order_by(VariantInventoryBalance.variant_id, VariantInventoryBalance.store_id)
            .with_for_update()
        )
        variant_map = {(row.store_id, row.variant_id): row for row in variant_rows.scalars().all()}
    # Lock product-level balances in a consistent order (product, store) to avoid deadlocks
    # between opposite-direction transfers running at the same time.
    balances_result = await db.execute(
        select(InventoryBalance)
        .where(InventoryBalance.store_id.in_(store_ids), InventoryBalance.product_id.in_(product_ids))
        .order_by(InventoryBalance.product_id, InventoryBalance.store_id)
        .with_for_update()
    )
    balance_map: dict[tuple[UUID, UUID], InventoryBalance] = {}
    for balance in balances_result.scalars().all():
        balance_map[(balance.store_id, balance.product_id)] = balance

    # Serial-tracked products move real serial units, so the caller must say
    # which ones. Validate them against the source store before touching balances.
    serial_values = [value.strip() for item in payload.items for value in (item.serial_numbers or []) if value.strip()]
    if len(serial_values) != len(set(serial_values)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate serial numbers in transfer")
    serials_by_item: dict[tuple[UUID, UUID | None], list[ProductSerial]] = {}
    if serial_values:
        serial_rows = (await db.execute(select(ProductSerial).where(ProductSerial.company_id == membership.company_id, ProductSerial.serial_number.in_(serial_values)).with_for_update())).scalars().all()
        by_number = {row.serial_number: row for row in serial_rows}
        missing = next((value for value in serial_values if value not in by_number), None)
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown serial: {missing}")
        for item in payload.items:
            for value in (item.serial_numbers or []):
                value = value.strip()
                if not value:
                    continue
                serial = by_number[value]
                if serial.status != "in_stock":
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Serial {value} is not in stock")
                if serial.store_id != context.store.id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Serial {value} is not at {context.store.name}")
                if serial.product_id != item.product_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Serial {value} does not belong to this product")
                if serial.variant_id != item.variant_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Serial {value} does not belong to the chosen variant")
                serials_by_item.setdefault((item.product_id, item.variant_id), []).append(serial)
    for item in payload.items:
        product = products[item.product_id]
        provided = len(item.serial_numbers or [])
        if product.track_serials:
            if item.quantity != int(item.quantity) or provided != int(item.quantity):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provide one serial per unit transferred for {product.name}")
        elif provided:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{product.name} does not track serials")

    def source_on_hand(item: StockTransferItemRequest) -> Decimal:
        if item.variant_id:
            row = variant_map.get((context.store.id, item.variant_id))
            return row.on_hand if row else Decimal("0")
        row = balance_map.get((context.store.id, item.product_id))
        return row.on_hand if row else Decimal("0")

    shortage = next(
        (
            f"{products[item.product_id].name} · {variants[item.variant_id].name}" if item.variant_id else products[item.product_id].name
            for item in payload.items
            if source_on_hand(item) < item.quantity
        ),
        None,
    )
    if shortage:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock at {context.store.name} for {shortage}")
    reference = f"TRF-{now_utc():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    moved = []
    for item in payload.items:
        product = products[item.product_id]
        for serial in serials_by_item.get((item.product_id, item.variant_id), []):
            serial.store_id = payload.to_store_id
        if item.variant_id:
            variant = variants[item.variant_id]
            label = f"{product.name} · {variant.name}"
            source = variant_map.get((context.store.id, variant.id))
            if source is None:
                source = VariantInventoryBalance(store_id=context.store.id, variant_id=variant.id, on_hand=0, reorder_point=10)
                db.add(source)
                await db.flush()
                variant_map[(context.store.id, variant.id)] = source
            target = variant_map.get((payload.to_store_id, variant.id))
            if target is None:
                target = VariantInventoryBalance(store_id=payload.to_store_id, variant_id=variant.id, on_hand=0, reorder_point=10)
                db.add(target)
                await db.flush()
                variant_map[(payload.to_store_id, variant.id)] = target
            source.on_hand -= item.quantity
            target.on_hand += item.quantity
            transfer_cost = await weighted_average_cost(db, context.store.id, product.id, variant.id)
            db.add(StockMovement(store_id=context.store.id, product_id=product.id, variant_id=variant.id, quantity=-item.quantity, movement_type="transfer_out", reason="stock_transfer", reference_id=reference, unit_cost=transfer_cost, created_by=context.user.id))
            db.add(StockMovement(store_id=payload.to_store_id, product_id=product.id, variant_id=variant.id, quantity=item.quantity, movement_type="transfer_in", reason="stock_transfer", reference_id=reference, unit_cost=transfer_cost, created_by=context.user.id))
            if source.on_hand <= (source.reorder_point or 10):
                await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {label}", f"Only {source.on_hand} left (reorder point {source.reorder_point or 10})")
            moved.append({"product_id": str(product.id), "product_name": product.name, "variant_id": str(variant.id), "variant_name": variant.name, "quantity": item.quantity, "serials": [serial.serial_number for serial in serials_by_item.get((item.product_id, item.variant_id), [])]})
        else:
            source = balance_map[(context.store.id, product.id)]
            target = balance_map.get((payload.to_store_id, product.id))
            if target is None:
                target = InventoryBalance(store_id=payload.to_store_id, product_id=product.id, on_hand=0, reorder_point=10)
                db.add(target)
                await db.flush()
            source.on_hand -= item.quantity
            target.on_hand += item.quantity
            transfer_cost = await weighted_average_cost(db, context.store.id, product.id, None)
            db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=-item.quantity, movement_type="transfer_out", reason="stock_transfer", reference_id=reference, unit_cost=transfer_cost, created_by=context.user.id))
            db.add(StockMovement(store_id=payload.to_store_id, product_id=product.id, quantity=item.quantity, movement_type="transfer_in", reason="stock_transfer", reference_id=reference, unit_cost=transfer_cost, created_by=context.user.id))
            if source.on_hand <= (source.reorder_point or 10):
                await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name}", f"Only {source.on_hand} left (reorder point {source.reorder_point or 10})")
            moved.append({"product_id": str(product.id), "product_name": product.name, "quantity": item.quantity, "serials": [serial.serial_number for serial in serials_by_item.get((item.product_id, item.variant_id), [])]})
    note = (payload.note or "").strip() or None
    await log_audit(db, membership, context.store.id, "stock_transferred_out", "inventory", entity_id=None, details={"reference": reference, "to_store_id": str(payload.to_store_id), "note": note}, user=context.user)
    await log_audit(db, membership, payload.to_store_id, "stock_transferred_in", "inventory", entity_id=None, details={"reference": reference, "from_store_id": str(context.store.id), "note": note}, user=context.user)
    await notify_company_managers(db, membership.company_id, payload.to_store_id, "stock_transfer", f"Incoming stock transfer", f"{len(moved)} item(s) in transit from {context.store.name}")
    await record_activity(db, "inventory.transferred", company_id=membership.company_id, store_id=context.store.id, details={"company": await _company_name(db, membership.company_id), "from_store": context.store.name, "to_store": to_store.name, "items": f"{len(moved)} item(s)", "reference": reference})
    await db.commit()
    return {"reference": reference, "from_store_id": str(context.store.id), "from_store_name": context.store.name, "to_store_id": str(payload.to_store_id), "to_store_name": to_store.name, "items": moved, "note": note}


def order_read(order: Order) -> OrderRead:
    payment_tenders = [tender for tender in order.tenders if tender.kind == "payment"]
    change_tender = next((tender for tender in order.tenders if tender.kind == "change"), None)
    amount_paid = sum((payment.amount for payment in order.payments if payment.status == "paid"), Decimal("0.00"))
    # A balance only matters while an order is still collecting; terminal states
    # always read as fully settled so the UI never offers to collect.
    balance_due = order.total - amount_paid
    if balance_due < 0 or order.status in ("paid", "cancelled", "refunded", "payment_expired", "reservation_expired"):
        balance_due = Decimal("0.00")
    return OrderRead(
        id=order.id,
        store_id=order.store_id,
        order_number=order.order_number,
        status=order.status,
        customer_name=order.customer_name,
        currency_code=order.currency_code,
        subtotal=order.subtotal,
        discount=order.discount,
        tax=order.tax,
        total=order.total,
        tip=order.tip,
        order_type=order.order_type,
        table_id=order.table_id,
        deposit=order.deposit,
        amount_paid=amount_paid,
        balance_due=balance_due,
        pickup_at=order.pickup_at,
        pickup_note=order.pickup_note,
        reservation_expires_at=order.reservation_expires_at,
        stock_held=order.stock_held,
        delivery_status=order.delivery_status,
        driver_name=order.driver_name,
        delivery_address=order.delivery_address,
        delivery_notes=order.delivery_notes,
        assigned_at=order.assigned_at,
        delivered_at=order.delivered_at,
        created_at=order.created_at,
        paid_at=order.paid_at,
        refunded_amount=sum((refund.total for refund in order.refunds), Decimal("0.00")),
        customer=CustomerBriefRead(id=order.customer.id, name=order.customer.name, phone=order.customer.phone, email=order.customer.email) if order.customer else None,
        items=[{"id": item.id, "product_id": item.product_id, "variant_id": item.variant_id, "variant_name": item.variant_name, "attributes": item.attributes, "modifiers": item.modifiers, "serials": [serial.serial_number for serial in item.serials], "condition_grade": item.condition_grade, "product_name": item.product_name, "sku": item.sku, "unit_price": item.unit_price, "quantity": item.quantity, "line_total": item.line_total, "combo_id": item.combo_id, "combo_name": item.combo_name, "combo_components": item.combo_components, "seat": item.seat, "course": item.course} for item in order.items],
        payments=[PaymentRead.model_validate(payment) for payment in order.payments],
        tenders=[OrderTenderRead.model_validate(tender) for tender in order.tenders],
        tendered_base_amount=sum((tender.base_amount for tender in payment_tenders), Decimal("0.00")),
        change_amount=change_tender.amount if change_tender else Decimal("0.00"),
        change_currency_code=change_tender.currency_code if change_tender else None,
    )


async def order_by_id(db: AsyncSession, order_id: UUID) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id).options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.tenders), selectinload(Order.refunds), selectinload(Order.customer)))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_order(payload: OrderCreateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> OrderRead:
    await ensure_transaction_available(db, context.membership.company_id)
    if payload.tenders and payload.payment_method:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use tenders or payment_method, not both")
    combo_ids = [item.combo_id for item in payload.items if item.combo_id]
    combos: dict[UUID, Combo] = {}
    if combo_ids:
        combo_rows = (await db.execute(select(Combo).where(Combo.id.in_(combo_ids), Combo.company_id == context.membership.company_id, Combo.is_active.is_(True)).options(selectinload(Combo.items), selectinload(Combo.groups).selectinload(ComboGroup.options)))).scalars().all()
        combos = {combo.id: combo for combo in combo_rows}
        if len(combos) != len(set(combo_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more combos are not available")
    # A combo line sells its components, so load every direct product plus every
    # combo component and check stock for all of them together.
    product_ids = [item.product_id for item in payload.items if item.product_id]
    product_ids += [combo_item.product_id for combo in combos.values() for combo_item in combo.items]
    product_ids += [option.product_id for combo in combos.values() for group in combo.groups for option in group.options]
    product_ids = list(dict.fromkeys(product_ids))
    products_result = await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))
    products = {product.id: product for product in products_result.scalars().all()}
    if len(products) != len(set(product_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    base_currency = await require_enabled_currency(db, context.membership.company_id, context.store.currency_code)
    balances_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids)).with_for_update())
    balances = {balance.product_id: balance for balance in balances_result.scalars().all()}
    requested_serials = [value.strip() for item in payload.items for value in (item.serial_numbers or [])]
    if len(requested_serials) != len(set(requested_serials)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each serial number can only be sold once per order")
    requested_variant_ids = [item.variant_id for item in payload.items if item.variant_id]
    requested_variant_ids += [combo_item.variant_id for combo in combos.values() for combo_item in combo.items if combo_item.variant_id]
    requested_variant_ids += [option.variant_id for combo in combos.values() for group in combo.groups for option in group.options if option.variant_id]
    requested_variant_ids = list(dict.fromkeys(requested_variant_ids))
    variants: dict[UUID, ProductVariant] = {}
    variant_balances: dict[UUID, VariantInventoryBalance] = {}
    if requested_variant_ids:
        variants_result = await db.execute(select(ProductVariant).where(ProductVariant.id.in_(requested_variant_ids), ProductVariant.is_active.is_(True)))
        variants = {variant.id: variant for variant in variants_result.scalars().all()}
        variant_balances_result = await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id.in_(requested_variant_ids)).with_for_update())
        variant_balances = {balance.variant_id: balance for balance in variant_balances_result.scalars().all()}
    group_ids = {product.modifier_group_id for product in products.values() if product.modifier_group_id}
    modifier_by_group_name: dict[tuple[UUID, str], Modifier] = {}
    if group_ids:
        modifier_rows = (await db.execute(select(Modifier).where(Modifier.group_id.in_(group_ids)))).scalars().all()
        modifier_by_group_name = {(row.group_id, row.name): row for row in modifier_rows}
    subtotal = Decimal("0.00")
    item_rows: list[OrderItem] = []
    line_serials: list[list[ProductSerial]] = []
    for requested in payload.items:
        if requested.combo_id:
            combo = combos[requested.combo_id]

            def resolve_component(product_id, variant_id, quantity):
                component_product = products.get(product_id)
                if component_product is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Combo {combo.name} has an unavailable component")
                needed = quantity * requested.quantity
                if variant_id:
                    component_variant = variants.get(variant_id)
                    if not component_variant or component_variant.product_id != product_id:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Combo {combo.name} has an unavailable variant")
                    component_balance = variant_balances.get(variant_id)
                    if not component_balance or component_balance.on_hand < needed:
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {component_product.name}")
                    component_unit_price = component_variant.price if component_variant.price is not None else component_product.price
                    return {"product_id": str(product_id), "variant_id": str(component_variant.id), "name": component_product.name, "variant_name": component_variant.name, "sku": component_variant.sku, "quantity": str(quantity), "unit_price": str(component_unit_price)}
                component_balance = balances.get(product_id)
                if not component_balance or component_balance.on_hand < needed:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {component_product.name}")
                return {"product_id": str(product_id), "variant_id": None, "name": component_product.name, "variant_name": None, "sku": component_product.sku, "quantity": str(quantity), "unit_price": str(component_product.price)}

            components: list[dict] = []
            for component in sorted(combo.items, key=lambda row: (row.position, str(row.id))):
                components.append(resolve_component(component.product_id, component.variant_id, component.quantity))

            groups_by_id = {group.id: group for group in combo.groups}
            selections_by_group: dict[UUID, list] = {}
            for selection in requested.combo_selections:
                if selection.group_id not in groups_by_id:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Combo {combo.name} has no such choice group")
                selections_by_group.setdefault(selection.group_id, []).append(selection)

            extra_unit_price = Decimal("0.00")
            for group in sorted(combo.groups, key=lambda row: (row.position, str(row.id))):
                group_selections = selections_by_group.get(group.id, [])
                selected_total = sum((selection.quantity for selection in group_selections), Decimal("0"))
                if selected_total < group.min_select or selected_total > group.max_select:
                    expected = str(group.min_select) if group.min_select == group.max_select else f"{group.min_select}-{group.max_select}"
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Choose {expected} for {group.name}")
                options_by_id = {option.id: option for option in group.options}
                for selection in group_selections:
                    option = options_by_id.get(selection.option_id)
                    if option is None:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"That option is not available for {group.name}")
                    record = resolve_component(option.product_id, option.variant_id, selection.quantity)
                    record["group_id"] = str(group.id)
                    record["group_name"] = group.name
                    components.append(record)
                    extra_unit_price += option.price_delta * selection.quantity

            if not components:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Combo {combo.name} has no components")
            lead_product_id = UUID(components[0]["product_id"])
            lead_product = products[lead_product_id]
            unit_price = combo.price + extra_unit_price
            line_total = (unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line_total
            item_rows.append(OrderItem(product_id=lead_product_id, product_name=combo.name, sku=(combo.sku or lead_product.sku), attributes=None, modifiers=None, unit_price=unit_price, quantity=requested.quantity, line_total=line_total, combo_id=combo.id, combo_name=combo.name, combo_components=components, seat=requested.seat, course=requested.course))
            line_serials.append([])
            continue
        product = products[requested.product_id]
        if product.track_serials and not requested.serial_numbers:
            has_units = (await db.execute(select(ProductSerial.id).where(ProductSerial.company_id == context.membership.company_id, ProductSerial.product_id == product.id, (ProductSerial.store_id == context.store.id) | (ProductSerial.store_id.is_(None)), ProductSerial.status == "in_stock").limit(1))).scalar_one_or_none()
            if has_units:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Select a serial number for {product.name}")
        serials_for_line: list[ProductSerial] = []
        if requested.serial_numbers:
            await release_stale_reservations_for_serials(db, context.membership.company_id, [value.strip() for value in requested.serial_numbers])
            if len(requested.serial_numbers) != requested.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provide one serial per unit for {product.name}")
            serial_rows = (await db.execute(select(ProductSerial).where(ProductSerial.company_id == context.membership.company_id, ProductSerial.product_id == product.id, ProductSerial.status == "in_stock", (ProductSerial.store_id == context.store.id) | (ProductSerial.store_id.is_(None)), ProductSerial.serial_number.in_([value.strip() for value in requested.serial_numbers])).with_for_update())).scalars().all()
            if len(serial_rows) != requested.quantity:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial not available for {product.name}")
            if requested.variant_id and any(serial.variant_id not in (None, requested.variant_id) for serial in serial_rows):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial does not match variant for {product.name}")
            serials_for_line = list(serial_rows)
        line_serials.append(serials_for_line)
        modifier_delta = sum((entry.price_delta for entry in requested.modifiers), Decimal("0.00"))
        modifier_snapshot = []
        for entry in requested.modifiers:
            record: dict = {"name": entry.name, "price_delta": str(entry.price_delta)}
            meta = modifier_by_group_name.get((product.modifier_group_id, entry.name)) if product.modifier_group_id else None
            if meta and meta.ingredient_product_id:
                record["ingredient_product_id"] = str(meta.ingredient_product_id)
                record["ingredient_quantity"] = meta.quantity
            modifier_snapshot.append(record)
        modifier_snapshot = modifier_snapshot or None
        if requested.variant_id:
            variant = variants.get(requested.variant_id)
            if not variant or variant.product_id != product.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Variant not available for {product.name}")
            for serial in serials_for_line:
                if serial.variant_id is None:
                    serial.variant_id = variant.id
                    # A serial received without a variant was never counted into a
                    # variant balance; count it now so this sale can draw it down.
                    await adjust_serial_stock(db, context.store.id, product, variant.id, 1, "restock", "serial_attributed", context.user.id)
            variant_balance = variant_balances.get(variant.id)
            if not variant_balance or variant_balance.on_hand < requested.quantity:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name} · {variant.name}")
            unit_price = (variant.price if variant.price is not None else product.price) + modifier_delta
            line_total = (unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line_total
            item_rows.append(OrderItem(product_id=product.id, product_name=product.name, sku=variant.sku, variant_id=variant.id, variant_name=variant.name, attributes=dict(variant.attributes) if variant.attributes else None, modifiers=modifier_snapshot, unit_price=unit_price, quantity=requested.quantity, line_total=line_total, seat=requested.seat, course=requested.course))
        else:
            balance = balances.get(product.id)
            if not balance or balance.on_hand < requested.quantity:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name}")
            unit_price = product.price + modifier_delta
            line_total = (unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line_total
            item_rows.append(OrderItem(product_id=product.id, product_name=product.name, sku=product.sku, attributes=dict(product.attributes) if product.attributes else None, modifiers=modifier_snapshot, unit_price=unit_price, quantity=requested.quantity, line_total=line_total, seat=requested.seat, course=requested.course))
    if payload.discount > subtotal:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Discount cannot exceed subtotal")
    store_prefs = dict(context.store.preferences or {})
    tax_inclusive = bool(store_prefs.get("tax_inclusive", False))
    prefix = (str(store_prefs.get("receipt_prefix") or "CHM").strip().upper()[:6]) or "CHM"
    tax_rate = context.store.service_tax_rate
    if tax_inclusive:
        total = (subtotal - payload.discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (total * tax_rate / (Decimal("100") + tax_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        taxable = total - tax
    else:
        taxable = subtotal - payload.discount
        tax = (taxable * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = taxable + tax
    if any((products.get(row.product_id).tax_rate if products.get(row.product_id) else None) is not None for row in item_rows):
        tax = Decimal("0.00")
        total = Decimal("0.00")
        for row in item_rows:
            rate = products[row.product_id].tax_rate if row.product_id in products else None
            if rate is None:
                rate = context.store.service_tax_rate
            line_discount = (payload.discount * row.line_total / subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if subtotal > 0 and payload.discount > 0 else Decimal("0.00")
            base = row.line_total - line_discount
            if tax_inclusive:
                line_tax = (base * rate / (Decimal("100") + rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total += base
            else:
                line_tax = (base * rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total += base + line_tax
            tax += line_tax
        taxable = total - tax
    if payload.tip > 0 and not store_prefs.get("allow_tip", True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tips are disabled for this store")
    if not store_prefs.get("charge_tax", True):
        tax = Decimal("0.00")
        total = (subtotal - payload.discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = total + payload.tip

    tender_specs: list[OrderTenderRequest]
    if payload.tenders:
        tender_specs = payload.tenders
    elif payload.payment_method:
        tender_specs = [OrderTenderRequest(method=payload.payment_method, currency_code=context.store.currency_code, amount=total)]
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment method or tenders are required")

    has_khqr = any(tender.method == "khqr" for tender in tender_specs)
    merchant_link: str | None = None
    merchant_store_ref: str | None = None
    merchant_scope = "none"
    if has_khqr:
        if len(tender_specs) != 1 or tender_specs[0].currency_code != "USD" or context.store.currency_code != "USD" or tender_specs[0].amount != total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR must be one exact USD tender in v1")
        merchant_link = context.store.aba_payway_link if context.store.aba_payway_status == "active" else None
        merchant_store_ref = context.store.chamabapay_store_id if merchant_link else None
        merchant_scope = "store"
        if not merchant_link:
            company_row = await get_company(db, context.membership.company_id)
            merchant_link = company_row.aba_payway_link if company_row.aba_payway_status == "active" else None
            merchant_store_ref = company_row.chamabapay_store_id if merchant_link else None
            merchant_scope = "company"
        if not merchant_link:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR checkout is unavailable until the store or company has an active ABA PayWay link")
    payment_tenders: list[OrderTender] = []
    tendered_base = Decimal("0.00")
    for tender in tender_specs:
        currency = await require_enabled_currency(db, context.membership.company_id, tender.currency_code)
        if tender.amount != round_currency(tender.amount, currency.decimal_places):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Amount must use {currency.decimal_places} decimal place(s) for {currency.code}")
        rate = await get_exchange_rate(db, context.membership.company_id, context.store.currency_code, tender.currency_code)
        base_amount = round_currency(tender.amount / rate, base_currency.decimal_places)
        tendered_base += base_amount
        payment_tenders.append(OrderTender(order_id=None, kind="payment", method=tender.method, currency_code=tender.currency_code, amount=tender.amount, base_amount=base_amount, exchange_rate=rate))
    tendered_base = round_currency(tendered_base, base_currency.decimal_places)
    pickup_at = payload.pickup_at
    if pickup_at is not None and pickup_at.tzinfo is None:
        pickup_at = pickup_at.replace(tzinfo=timezone.utc)
    # A reservation pays a deposit now (less than the total) and collects later;
    # a pickup date with the full total is an ordinary prepaid sale.
    is_reservation = pickup_at is not None and tendered_base < total
    hold_stock = bool(is_reservation and payload.hold_stock)
    if is_reservation:
        if tendered_base <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reservation needs a deposit")
        if has_khqr:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A deposit cannot be paid by KHQR; use cash or a trade-in credit")
    elif tendered_base < total:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payment is short by {total - tendered_base:.2f} {context.store.currency_code}")
    change_base = tendered_base - total
    change_tender: OrderTender | None = None
    change_currency = payload.change_currency_code
    if change_base > 0:
        if not any(tender.method == "cash" for tender in tender_specs):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Change can only be returned when a cash tender is included")
        change_currency = change_currency or context.store.currency_code
        change_currency_row = await require_enabled_currency(db, context.membership.company_id, change_currency)
        change_rate = await get_exchange_rate(db, context.membership.company_id, context.store.currency_code, change_currency)
        change_amount = round_currency(change_base * change_rate, change_currency_row.decimal_places)
        change_tender = OrderTender(order_id=None, kind="change", method="cash", currency_code=change_currency, amount=change_amount, base_amount=change_base, exchange_rate=change_rate)
    if payload.table_id:
        table_row = (await db.execute(select(DiningTable).where(DiningTable.id == payload.table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
        if not table_row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Table not found")
    customer = None
    customer_name = (payload.customer_name or "").strip() or None
    if payload.customer_id:
        customer = (await db.execute(select(Customer).where(Customer.id == payload.customer_id, Customer.company_id == context.membership.company_id))).scalar_one_or_none()
        if not customer or not customer.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        customer_name = customer.name.strip()
    order = Order(store_id=context.store.id, created_by=context.user.id, order_number=await next_document_number(db, store_id=context.store.id, scope="order", prefix=prefix), status="payment_pending", customer_id=customer.id if customer else None, customer_name=customer_name, tip=payload.tip, order_type=payload.order_type, table_id=payload.table_id, pickup_at=pickup_at, pickup_note=(payload.pickup_note or "").strip() or None, stock_held=hold_stock, currency_code=context.store.currency_code, subtotal=subtotal, discount=payload.discount, tax=tax, total=total, items=item_rows, tenders=payment_tenders + ([change_tender] if change_tender else []))
    db.add(order)
    await db.flush()
    # Apply any trade-in credit to the accepted TradeIn records (one use each).
    for tender in tender_specs:
        if tender.method == "trade_in" and tender.trade_in_id:
            trade_in = (await db.execute(select(TradeIn).where(TradeIn.id == tender.trade_in_id, TradeIn.store_id == context.store.id).with_for_update())).scalar_one_or_none()
            if not trade_in or trade_in.status != "accepted" or trade_in.order_id is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade-in is not available for this sale")
            if Decimal(tender.amount) != trade_in.assessed_value:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade-in credit does not match the assessed value")
            trade_in.order_id = order.id
    for index, row in enumerate(item_rows):
        for serial in line_serials[index]:
            serial.order_item_id = row.id
            if has_khqr or hold_stock:
                # Hold the unit while the QR payment is pending, or for the life
                # of a deposit reservation, so it cannot be sold twice.
                serial.status = "reserved"
    payment_method = tender_specs[0].method if len(tender_specs) == 1 else "mixed"
    if is_reservation:
        # Take the deposit and leave the order open as a reservation to be
        # collected later. Held stock was drawn down above (hold_order_stock).
        db.add(Payment(order_id=order.id, provider=payment_method, status="paid", amount=tendered_base, currency_code=order.currency_code, reference_id=order.order_number, approved_at=now_utc()))
        order.deposit = tendered_base
        order.status = "pending_pickup"
        grace_hours = int(store_prefs.get("reservation_grace_hours", 24) or 24)
        order.reservation_expires_at = pickup_at + timedelta(hours=grace_hours)
        if hold_stock:
            await hold_order_stock(db, order)
    elif not has_khqr:
        db.add(Payment(order_id=order.id, provider=payment_method, status="paid", amount=total, currency_code=order.currency_code, reference_id=order.order_number, approved_at=now_utc()))
        await db.flush()
        await complete_order(db, order.id)
    else:
        provider = await active_payment_provider(db)
        merchant_meta: dict = {"type": "pos_order", "store_id": str(context.store.id), "merchant_connection": merchant_scope}
        if merchant_link:
            merchant_meta["merchant_aba_link"] = merchant_link
        if not merchant_store_ref:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR checkout is unavailable until the merchant's ChmabaPay store is active")
        try:
            provider_payment = await provider.create_payment(
                total,
                order.order_number,
                idempotency_key=order.order_number,
                store_ref=merchant_store_ref,
                metadata=merchant_meta,
            )
        except PaymentProviderError as exc:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        db.add(Payment(order_id=order.id, provider=provider.name, status=provider_payment.status, amount=total, currency_code=provider_payment.currency, external_id=provider_payment.id, reference_id=provider_payment.reference_id or order.order_number, qr_string=provider_payment.qr_string, checkout_url=provider_payment.checkout_url, provider_metadata=provider_payment.metadata or merchant_meta))
    await flag_discount_review(db, context, order, subtotal, payload.discount)
    await db.commit()
    return order_read(await order_by_id(db, order.id))


@router.get("/orders", response_model=list[OrderRead], tags=["orders"])
async def list_orders(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db), order_status: str | None = Query(default=None, alias="status"), limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)) -> list[OrderRead]:
    # Sweep lapsed reservations before listing so staff see accurate stock and
    # order states without a separate cron dependency.
    if await release_stale_reservations(db, context.membership.company_id):
        await db.commit()
    query = select(Order).where(Order.store_id == context.store.id).options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.tenders), selectinload(Order.refunds), selectinload(Order.customer)).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    if order_status:
        query = query.where(Order.status == order_status)
    orders = (await db.execute(query)).scalars().unique().all()
    return [order_read(order) for order in orders]


@router.get("/deliveries", response_model=list[OrderRead], tags=["orders"])
async def list_deliveries(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db), delivery_status: str | None = Query(default=None, alias="status"), limit: int = Query(default=100, ge=1, le=200)) -> list[OrderRead]:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    statement = select(Order).where(Order.store_id == context.store.id, Order.order_type == "delivery").options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.tenders), selectinload(Order.refunds), selectinload(Order.customer)).order_by(Order.created_at.desc()).limit(limit)
    if delivery_status:
        statement = statement.where(Order.delivery_status == delivery_status)
    orders = (await db.execute(statement)).scalars().unique().all()
    return [order_read(order) for order in orders]


@router.patch("/orders/{order_id}/delivery", response_model=OrderRead, tags=["orders"])
async def update_order_delivery(order_id: UUID, payload: DeliveryUpdateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> OrderRead:
    await require_plan_feature(db, context.membership.company_id, "table_management")
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.order_type != "delivery":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order is not a delivery")
    if payload.driver_name is not None:
        order.driver_name = payload.driver_name.strip() or None
    if payload.delivery_address is not None:
        order.delivery_address = payload.delivery_address.strip() or None
    if payload.delivery_notes is not None:
        order.delivery_notes = payload.delivery_notes.strip() or None
    if payload.status is not None:
        order.delivery_status = payload.status
        if payload.status == "assigned" and order.assigned_at is None:
            order.assigned_at = now_utc()
        if payload.status == "delivered":
            order.delivered_at = now_utc()
    await db.commit()
    return order_read(await order_by_id(db, order.id))


@router.get("/orders/{order_id}", response_model=OrderRead, tags=["orders"])
async def get_order(order_id: UUID, context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db)) -> OrderRead:
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "paid":
        try:
            if await reconcile_pending_order_payment(db, order):
                order = await order_by_id(db, order_id)
        except HTTPException as exc:
            # A late or duplicate settlement can hit a stock conflict while
            # completing an order another sale already consumed. Return the
            # order's current state instead of failing the read with a raw 409.
            if exc.status_code != status.HTTP_409_CONFLICT:
                raise
            await db.rollback()
            order = await order_by_id(db, order_id)
    return order_read(order)


async def release_order_serials(db: AsyncSession, order: Order) -> None:
    """Return serials held by a pending order to available stock."""
    item_ids = [item.id for item in (order.items or [])]
    if not item_ids:
        return
    rows = (await db.execute(select(ProductSerial).where(ProductSerial.order_item_id.in_(item_ids), ProductSerial.status == "reserved"))).scalars().all()
    for serial in rows:
        serial.status = "in_stock"
        serial.order_item_id = None


async def release_stale_serial_reservations(db: AsyncSession, company_id: UUID | None = None) -> int:
    """Free serials held by pending orders older than the QR window; mark those orders expired."""
    cutoff = now_utc() - timedelta(minutes=15)
    # Only pending KHQR orders expire on this short window; a deposit
    # reservation holds its serials until its own ``reservation_expires_at``.
    statement = (select(Order).join(OrderItem, OrderItem.order_id == Order.id).join(ProductSerial, ProductSerial.order_item_id == OrderItem.id).where(ProductSerial.status == "reserved", Order.status == "payment_pending", Order.created_at < cutoff).options(selectinload(Order.items)).distinct())
    if company_id:
        statement = statement.where(ProductSerial.company_id == company_id)
    orders = (await db.execute(statement)).scalars().all()
    for order in orders:
        await release_order_serials(db, order)
        order.status = "payment_expired"
    return len(orders)


async def release_stale_reservations_for_serials(db: AsyncSession, company_id: UUID, serial_numbers: list[str]) -> None:
    """Free specific serials whose pending order is older than the QR window (caller commits)."""
    if not serial_numbers:
        return
    cutoff = now_utc() - timedelta(minutes=15)
    rows = (await db.execute(select(ProductSerial, Order).join(OrderItem, OrderItem.id == ProductSerial.order_item_id).join(Order, Order.id == OrderItem.order_id).where(ProductSerial.company_id == company_id, ProductSerial.status == "reserved", ProductSerial.serial_number.in_(serial_numbers), Order.status == "payment_pending", Order.created_at < cutoff))).all()
    for serial, order in rows:
        serial.status = "in_stock"
        serial.order_item_id = None
        order.status = "payment_expired"


def reservation_refund_enabled(store: Store, override: bool | None) -> bool:
    """Whether a cancelled/expired reservation should refund its deposit.

    ``store.preferences['reservation_cancel_deposit']`` is ``refund`` by default
    and ``forfeit`` to keep the money; an explicit per-call override wins.
    """
    if override is not None:
        return override
    policy = str(dict(store.preferences or {}).get("reservation_cancel_deposit", "refund")).lower()
    return policy != "forfeit"


async def refund_reservation_deposit(db: AsyncSession, order: Order, reason: str, created_by: UUID | None = None) -> Decimal | None:
    """Record a refund of the deposit already collected on a reservation.

    Only the not-yet-refunded portion of paid tenders is refunded, so calling it
    twice can never over-refund. Held stock is restored separately by the caller
    (``release_order_stock``), so this only moves the money record.
    """
    paid = sum((payment.amount for payment in order.payments if payment.status == "paid"), Decimal("0.00"))
    already_refunded = sum((refund.total for refund in order.refunds), Decimal("0.00"))
    amount = (paid - already_refunded).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= 0:
        return None
    method = next((payment.provider for payment in order.payments if payment.status == "paid"), None) or "cash"
    db.add(Refund(store_id=order.store_id, order_id=order.id, created_by=created_by or order.created_by, method=method, reason=reason, currency_code=order.currency_code, subtotal=amount, tax=Decimal("0.00"), total=amount, items=[]))
    return amount


async def release_stale_reservations(db: AsyncSession, company_id: UUID | None = None) -> int:
    """Expire reservations whose pickup window lapsed and return their stock.

    Held inventory (and any ``reserved`` serials) is put back on the shelf so an
    abandoned reservation never blocks a sale, and the deposit is refunded when
    the store's ``reservation_cancel_deposit`` policy says so (the default). The
    order is closed as ``reservation_expired``.
    """
    statement = (select(Order).where(Order.status == "pending_pickup", Order.reservation_expires_at.is_not(None), Order.reservation_expires_at < now_utc()).options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.refunds)))
    if company_id:
        statement = statement.join(Store, Store.id == Order.store_id).where(Store.company_id == company_id)
    orders = (await db.execute(statement)).scalars().unique().all()
    if not orders:
        return 0
    store_ids = {order.store_id for order in orders}
    stores = {store.id: store for store in (await db.execute(select(Store).where(Store.id.in_(store_ids)))).scalars().all()}
    terminal_payment_statuses = {"paid", "failed", "expired", "superseded", "reversed"}
    for order in orders:
        # A balance QR that is still open means the customer is mid-payment;
        # leave the reservation open so the settlement can complete.
        if any(payment.external_id and payment.status not in terminal_payment_statuses for payment in order.payments):
            continue
        if order.stock_held:
            await release_order_stock(db, order, "reservation_expired")
            order.stock_held = False
        else:
            await release_order_serials(db, order)
        store = stores.get(order.store_id)
        if store and reservation_refund_enabled(store, None):
            await refund_reservation_deposit(db, order, "reservation_expired")
        order.status = "reservation_expired"
    return len(orders)


@router.post("/orders/{order_id}/cancel", response_model=OrderRead, tags=["orders"])
async def cancel_order(order_id: UUID, payload: OrderCancelRequest | None = None, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> OrderRead:
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status == "paid":
        # Voiding a paid order reverses a completed sale, so it runs through the
        # refund engine and is gated by the cancel_paid_order approval rule.
        policy = await load_approval_policy(db, membership.company_id)
        rule = policy.rules.get("cancel_paid_order")
        if not (policy.enabled and rule is not None and rule.mode != "off"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paid orders require a refund flow")
        gate = approval_gate(rule, order.total)
        if gate == "request":
            is_approver = membership.role in rule.approvers
            if not (is_approver and not (policy.maker_checker and membership.role != "owner")):
                return await _pending_approval_response(db, membership, store_id=context.store.id, action="cancel_paid_order", amount=order.total, payload={"order_id": str(order.id)}, user=context.user)
        await _void_paid_order(db, context, order)
        if gate == "review":
            await log_audit(db, membership, context.store.id, "cancel_paid_order_reviewed", "order", order.id, {"order_number": order.order_number, "mode": "review"}, user=context.user)
            await notify_company_managers(db, membership.company_id, context.store.id, "cancel_paid_order_review", f"Paid order void flagged: {order.order_number}", f"by {context.user.full_name}")
            await db.commit()
        return order_read(await order_by_id(db, order.id))
    if order.status in ("cancelled", "refunded", "reservation_expired", "payment_expired"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is already closed")
    if order.stock_held:
        # A reservation drew stock down at deposit time; put it back.
        await release_order_stock(db, order, "reservation_cancelled")
        order.stock_held = False
    # Refund the deposit unless the store forfeits it (or the caller overrides).
    override = payload.refund_deposit if payload else None
    if reservation_refund_enabled(context.store, override):
        await refund_reservation_deposit(db, order, "reservation_cancelled", created_by=context.user.id)
    order.status = "cancelled"
    await release_order_serials(db, order)
    await db.commit()
    # ``expire_on_commit=False`` keeps the loaded collections, so refresh the
    # refunds we just added before rendering the response.
    await db.refresh(order, ["refunds"])
    return order_read(order)


@router.post("/orders/{order_id}/collect", response_model=OrderRead, tags=["orders"])
async def collect_order(order_id: UUID, payload: OrderCollectRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> OrderRead:
    """Settle a reservation's outstanding balance and complete the sale."""
    # Cash and accepted trade-in credit settle immediately. KHQR issues a balance
    # QR on the order and settles asynchronously through the webhook / reconcile
    # path, exactly like a normal KHQR sale.
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "pending_pickup":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is not awaiting pickup")
    base_currency = await require_enabled_currency(db, context.membership.company_id, context.store.currency_code)
    amount_paid = sum((payment.amount for payment in order.payments if payment.status == "paid"), Decimal("0.00"))
    balance = round_currency(order.total - amount_paid, base_currency.decimal_places)
    if balance <= 0:
        await complete_order(db, order.id)
        await db.commit()
        await db.refresh(order, ["payments", "tenders"])
        return order_read(order)

    has_khqr = any(tender.method == "khqr" for tender in payload.tenders)
    if has_khqr:
        # A single exact USD QR for the balance; the order stays open until it
        # settles (webhook/reconcile calls complete_order, which finalizes it).
        if len(payload.tenders) != 1 or payload.tenders[0].currency_code != "USD" or context.store.currency_code != "USD" or payload.tenders[0].amount != balance:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR must be one exact USD tender for the balance")
        merchant_link = context.store.aba_payway_link if context.store.aba_payway_status == "active" else None
        merchant_store_ref = context.store.chamabapay_store_id if merchant_link else None
        merchant_scope = "store"
        if not merchant_link:
            company_row = await get_company(db, context.membership.company_id)
            merchant_link = company_row.aba_payway_link if company_row.aba_payway_status == "active" else None
            merchant_store_ref = company_row.chamabapay_store_id if merchant_link else None
            merchant_scope = "company"
        if not merchant_link:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR checkout is unavailable until the store or company has an active ABA PayWay link")
        provider = await active_payment_provider(db)
        reference = f"{order.order_number}-BAL"
        merchant_meta: dict = {"type": "reservation_balance", "store_id": str(context.store.id), "merchant_connection": merchant_scope}
        if merchant_link:
            merchant_meta["merchant_aba_link"] = merchant_link
        if not merchant_store_ref:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR checkout is unavailable until the merchant's ChmabaPay store is active")
        try:
            provider_payment = await provider.create_payment(balance, reference, idempotency_key=reference, store_ref=merchant_store_ref, metadata=merchant_meta)
        except PaymentProviderError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        db.add(Payment(order_id=order.id, provider=provider.name, status=provider_payment.status, amount=balance, currency_code=provider_payment.currency, external_id=provider_payment.id, reference_id=provider_payment.reference_id or reference, qr_string=provider_payment.qr_string, checkout_url=provider_payment.checkout_url, provider_metadata=provider_payment.metadata or merchant_meta))
        await db.flush()
        await db.commit()
        await db.refresh(order, ["payments", "tenders"])
        return order_read(order)

    # Cash and/or accepted trade-in credit settle the balance immediately.
    payment_tenders: list[OrderTender] = []
    tendered_base = Decimal("0.00")
    for tender in payload.tenders:
        currency = await require_enabled_currency(db, context.membership.company_id, tender.currency_code)
        if tender.amount != round_currency(tender.amount, currency.decimal_places):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Amount must use {currency.decimal_places} decimal place(s) for {currency.code}")
        rate = await get_exchange_rate(db, context.membership.company_id, context.store.currency_code, tender.currency_code)
        base_amount = round_currency(tender.amount / rate, base_currency.decimal_places)
        tendered_base += base_amount
        payment_tenders.append(OrderTender(order_id=order.id, kind="payment", method=tender.method, currency_code=tender.currency_code, amount=tender.amount, base_amount=base_amount, exchange_rate=rate))
    tendered_base = round_currency(tendered_base, base_currency.decimal_places)
    if tendered_base < balance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payment is short by {balance - tendered_base:.2f} {context.store.currency_code}")
    # Claim any trade-in credits (one use each), mirroring create_order.
    for tender in payload.tenders:
        if tender.method == "trade_in" and tender.trade_in_id:
            trade_in = (await db.execute(select(TradeIn).where(TradeIn.id == tender.trade_in_id, TradeIn.store_id == context.store.id).with_for_update())).scalar_one_or_none()
            if not trade_in or trade_in.status != "accepted" or trade_in.order_id is not None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade-in is not available for this sale")
            if Decimal(tender.amount) != trade_in.assessed_value:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade-in credit does not match the assessed value")
            trade_in.order_id = order.id
    change_base = tendered_base - balance
    if change_base > 0:
        if not any(tender.method == "cash" for tender in payload.tenders):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Change can only be returned when a cash tender is included")
        change_currency = payload.change_currency_code or context.store.currency_code
        change_currency_row = await require_enabled_currency(db, context.membership.company_id, change_currency)
        change_rate = await get_exchange_rate(db, context.membership.company_id, context.store.currency_code, change_currency)
        change_amount = round_currency(change_base * change_rate, change_currency_row.decimal_places)
        payment_tenders.append(OrderTender(order_id=order.id, kind="change", method="cash", currency_code=change_currency, amount=change_amount, base_amount=change_base, exchange_rate=change_rate))
    for tender in payment_tenders:
        db.add(tender)
    payment_method = payload.tenders[0].method if len(payload.tenders) == 1 else "mixed"
    db.add(Payment(order_id=order.id, provider=payment_method, status="paid", amount=balance, currency_code=order.currency_code, reference_id=order.order_number, approved_at=now_utc()))
    await db.flush()
    await complete_order(db, order.id)
    await db.commit()
    await db.refresh(order, ["payments", "tenders"])
    return order_read(order)


def held_order_read(held: HeldOrder, cashier_name: str | None = None, tax_rate: Decimal = Decimal("10.00"), tax_inclusive: bool = False) -> HeldOrderRead:
    items: list[HeldItemRead] = []
    subtotal = Decimal("0.00")
    item_count = Decimal("0")
    for raw in held.items or []:
        # Quantities are stored as decimal strings (weighed goods, partial
        # units); parse as Decimal so fractions never blow up serialisation.
        quantity = Decimal(str(raw.get("quantity", 0)))
        item_count += quantity
        unit_price = Decimal(str(raw.get("unit_price", "0")))
        line_total = Decimal(str(raw.get("line_total", "0")))
        subtotal += line_total
        items.append(HeldItemRead(
            product_id=UUID(raw["product_id"]),
            variant_id=UUID(raw["variant_id"]) if raw.get("variant_id") else None,
            variant_name=raw.get("variant_name"),
            attributes=raw.get("attributes"),
            modifiers=raw.get("modifiers"),
            line_key=raw.get("line_key") or str(raw["product_id"]),
            product_name=raw.get("product_name", ""),
            sku=raw.get("sku", ""),
            unit_price=unit_price,
            quantity=float(quantity),
            line_total=line_total,
            seat=raw.get("seat"),
            course=raw.get("course"),
            fired_at=raw.get("fired_at"),
        ))
    subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = Decimal("0.00") if tax_inclusive else (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return HeldOrderRead(id=held.id, store_id=held.store_id, created_by=held.created_by, cashier_name=cashier_name, label=held.label, order_type=held.order_type, table_id=held.table_id, status=held.status, source=held.source, customer_note=held.customer_note, payment_status=held.payment_status, payment_qr_string=held.payment_qr_string, payment_checkout_url=held.payment_checkout_url, paid_at=held.paid_at, created_at=held.created_at, item_count=float(item_count), subtotal=subtotal, tax=tax, total=subtotal + tax, items=items)


@router.get("/held-orders", response_model=list[HeldOrderRead], tags=["orders"])
async def list_held_orders(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[HeldOrderRead]:
    result = await db.execute(select(HeldOrder, User.full_name).outerjoin(User, User.id == HeldOrder.created_by).where(HeldOrder.store_id == context.store.id, HeldOrder.payment_status != "pending").order_by(HeldOrder.created_at.desc()))
    return [held_order_read(held, cashier_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False))) for held, cashier_name in result.all()]


@router.post("/held-orders", response_model=HeldOrderRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_held_order(payload: HeldOrderCreateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    product_ids = [item.product_id for item in payload.items]
    products_result = await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))
    products = {product.id: product for product in products_result.scalars().all()}
    if len(products) != len(set(product_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    variant_ids = [item.variant_id for item in payload.items if item.variant_id]
    variants: dict[UUID, ProductVariant] = {}
    if variant_ids:
        variants = {variant.id: variant for variant in (await db.execute(select(ProductVariant).where(ProductVariant.id.in_(variant_ids), ProductVariant.is_active.is_(True)))).scalars().all()}
    balances_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids)))
    balances = {balance.product_id: balance for balance in balances_result.scalars().all()}
    variant_balances: dict[UUID, VariantInventoryBalance] = {}
    if variant_ids:
        variant_balances = {balance.variant_id: balance for balance in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id.in_(variant_ids)))).scalars().all()}
    snapshot: list[dict] = []
    for requested in payload.items:
        product = products[requested.product_id]
        variant = variants.get(requested.variant_id) if requested.variant_id else None
        if requested.variant_id and not variant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Variant not available for {product.name}")
        base_price = variant.price if (variant and variant.price is not None) else product.price
        modifier_delta = sum((entry.price_delta for entry in requested.modifiers), Decimal("0.00"))
        unit_price = base_price + modifier_delta
        # Stock is tracked per variant when the line names one, else per product.
        if variant is not None:
            balance = variant_balances.get(variant.id)
        else:
            balance = balances.get(product.id)
        if not balance or balance.on_hand < requested.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name}")
        line_total = (unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        snapshot.append({
            "line_key": held_line_key(product.id, variant.id if variant else None, requested.modifiers, requested.seat),
            "product_id": str(product.id),
            "product_name": product.name,
            "sku": variant.sku if variant else product.sku,
            "variant_id": str(variant.id) if variant else None,
            "variant_name": variant.name if variant else None,
            "attributes": dict(variant.attributes) if (variant and variant.attributes) else (dict(product.attributes) if product.attributes else None),
            "modifiers": [{"name": entry.name, "price_delta": str(entry.price_delta)} for entry in requested.modifiers] or None,
            "unit_price": str(unit_price),
            "quantity": str(requested.quantity),
            "line_total": str(line_total),
            "seat": requested.seat,
            "course": requested.course,
            "fired_at": None,
        })
    table = None
    if payload.table_id:
        table = (await db.execute(select(DiningTable).where(DiningTable.id == payload.table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
        if not table:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Table not found")
    held = HeldOrder(store_id=context.store.id, created_by=context.user.id, label=(payload.label or "").strip()[:120] or None, order_type=payload.order_type, table_id=payload.table_id, items=snapshot)
    db.add(held)
    if table is not None:
        # Opening a ticket seats the table; the status is freed again when the
        # last held order for it is settled or discarded.
        table.status = "occupied"
    await db.commit()
    return held_order_read(held, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.delete("/held-orders/{held_id}", tags=["orders"])
async def delete_held_order(held_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    result = await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))
    held = result.scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    table_id = held.table_id
    await db.delete(held)
    await db.flush()
    if table_id:
        still_open = (await db.execute(select(HeldOrder.id).where(HeldOrder.table_id == table_id).limit(1))).scalar_one_or_none()
        if still_open is None:
            table = (await db.execute(select(DiningTable).where(DiningTable.id == table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
            if table is not None and table.status == "occupied":
                table.status = "available"
    await db.commit()
    return {"ok": True}


@router.post("/held-orders/{held_id}/merge", response_model=HeldOrderRead, tags=["orders"])
async def merge_held_order(held_id: UUID, payload: HeldOrderMergeRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    if held_id == payload.into_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot merge a held order into itself")
    rows = (await db.execute(select(HeldOrder).where(HeldOrder.id.in_([held_id, payload.into_id]), HeldOrder.store_id == context.store.id))).scalars().all()
    by_id = {row.id: row for row in rows}
    source = by_id.get(held_id)
    target = by_id.get(payload.into_id)
    if not source or not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    # Fold the source lines into the target, summing quantities per product.
    merged: dict[str, dict] = {}
    keys: list[str] = []
    for row in (target, source):
        for item in row.items or []:
            key = str(item.get("line_key") or item.get("product_id"))
            if key in merged:
                quantity = Decimal(str(merged[key]["quantity"])) + Decimal(str(item.get("quantity", "0")))
                merged[key]["quantity"] = str(quantity)
                merged[key]["line_total"] = str((Decimal(str(merged[key]["unit_price"])) * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            else:
                merged[key] = dict(item)
                keys.append(key)
    target.items = [merged[key] for key in keys]
    source_table = source.table_id
    await db.delete(source)
    await db.flush()
    # Free the source table unless it is the target's (or another ticket's).
    if source_table and source_table != target.table_id:
        still_open = (await db.execute(select(HeldOrder.id).where(HeldOrder.table_id == source_table).limit(1))).scalar_one_or_none()
        if still_open is None:
            table = (await db.execute(select(DiningTable).where(DiningTable.id == source_table, DiningTable.store_id == context.store.id))).scalar_one_or_none()
            if table is not None and table.status == "occupied":
                table.status = "available"
    await db.commit()
    await db.refresh(target)
    return held_order_read(target, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.post("/held-orders/{held_id}/split", response_model=HeldOrderRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
async def split_held_order(held_id: UUID, payload: HeldOrderSplitRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    held = (await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))).scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    source_items = {str(item.get("line_key") or item.get("product_id")): dict(item) for item in (held.items or [])}
    split_rows: list[dict] = []
    for requested in payload.items:
        key = held_line_key(requested.product_id, requested.variant_id, requested.modifiers, requested.seat)
        line = source_items.get(key)
        if not line:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An item is not on this held order")
        available = Decimal(str(line.get("quantity", "0")))
        if available < requested.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot split more than is on the held order")
        unit_price = Decimal(str(line.get("unit_price", "0")))
        moved = dict(line)
        moved["quantity"] = str(requested.quantity)
        moved["line_total"] = str((unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        split_rows.append(moved)
        remaining = available - requested.quantity
        if remaining <= 0:
            del source_items[key]
        else:
            line["quantity"] = str(remaining)
            line["line_total"] = str((unit_price * remaining).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            source_items[key] = line
    # The split keeps the source's line order; drop the lines that moved.
    held.items = [source_items[key] for key in (str(item.get("line_key") or item.get("product_id")) for item in (held.items or [])) if key in source_items]
    if payload.table_id:
        dest_table = (await db.execute(select(DiningTable).where(DiningTable.id == payload.table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
        if not dest_table:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Table not found")
        dest_table.status = "occupied"
    split = HeldOrder(store_id=context.store.id, created_by=context.user.id, order_type=held.order_type, table_id=payload.table_id, items=split_rows)
    db.add(split)
    if not held.items:
        # Everything moved off: retire the source and free its table if it was
        # not the split's destination.
        source_table = held.table_id
        await db.delete(held)
        await db.flush()
        if source_table and source_table != payload.table_id:
            still_open = (await db.execute(select(HeldOrder.id).where(HeldOrder.table_id == source_table).limit(1))).scalar_one_or_none()
            if still_open is None:
                src_table = (await db.execute(select(DiningTable).where(DiningTable.id == source_table, DiningTable.store_id == context.store.id))).scalar_one_or_none()
                if src_table is not None and src_table.status == "occupied":
                    src_table.status = "available"
    await db.commit()
    await db.refresh(split)
    return held_order_read(split, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.patch("/held-orders/{held_id}", response_model=HeldOrderRead, tags=["orders"])
async def update_held_order(held_id: UUID, payload: HeldOrderUpdateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    held = (await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))).scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    # open | served — the kitchen marks a ticket served (or reopens it).
    held.status = payload.status
    await db.commit()
    await db.refresh(held)
    return held_order_read(held, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.post("/held-orders/{held_id}/fire", response_model=HeldOrderRead, tags=["orders"])
async def fire_held_order(held_id: UUID, payload: HeldOrderFireRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    held = (await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))).scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    fired_at = now_utc().isoformat()
    fired = False
    rows: list[dict] = []
    for raw in held.items or []:
        row = dict(raw)
        # Fire every unfired line in the requested course (or all when none).
        if not row.get("fired_at") and (payload.course is None or (row.get("course") or None) == payload.course):
            row["fired_at"] = fired_at
            fired = True
        rows.append(row)
    if not fired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to fire for that course")
    held.items = rows
    await db.commit()
    await db.refresh(held)
    return held_order_read(held, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.patch("/held-orders/{held_id}/items", response_model=HeldOrderRead, tags=["orders"])
async def update_held_order_line(held_id: UUID, payload: HeldLineUpdateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    held = (await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))).scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    rows = [dict(raw) for raw in (held.items or [])]
    index = next((position for position, row in enumerate(rows) if str(row.get("line_key") or row.get("product_id")) == payload.line_key), None)
    if index is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found on this ticket")
    row = rows[index]
    # Seat is part of the identity, so re-keying must not collide with another line.
    new_key = held_line_key(UUID(row["product_id"]), UUID(row["variant_id"]) if row.get("variant_id") else None, row.get("modifiers"), payload.seat)
    if new_key != payload.line_key and any(str(other.get("line_key") or other.get("product_id")) == new_key for position, other in enumerate(rows) if position != index):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A line already exists for that seat")
    row["seat"] = payload.seat
    row["course"] = payload.course
    row["line_key"] = new_key
    held.items = rows
    await db.commit()
    await db.refresh(held)
    return held_order_read(held, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.post("/held-orders/{held_id}/transfer", response_model=HeldOrderRead, tags=["orders"])
async def transfer_held_order(held_id: UUID, payload: HeldOrderTransferRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    held = (await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))).scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    if payload.table_id == held.table_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The ticket is already on that table")
    dest_table = None
    if payload.table_id:
        dest_table = (await db.execute(select(DiningTable).where(DiningTable.id == payload.table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
        if not dest_table:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Table not found")
    previous_table_id = held.table_id
    held.table_id = payload.table_id
    if dest_table is not None:
        dest_table.status = "occupied"
    await db.flush()
    # Free the previous table unless another open ticket still uses it (or it is
    # the destination).
    if previous_table_id and previous_table_id != payload.table_id:
        still_open = (await db.execute(select(HeldOrder.id).where(HeldOrder.table_id == previous_table_id).limit(1))).scalar_one_or_none()
        if still_open is None:
            prev_table = (await db.execute(select(DiningTable).where(DiningTable.id == previous_table_id, DiningTable.store_id == context.store.id))).scalar_one_or_none()
            if prev_table is not None and prev_table.status == "occupied":
                prev_table.status = "available"
    await db.commit()
    await db.refresh(held)
    return held_order_read(held, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


def refund_read(refund: Refund, order: Order | None = None, cashier_name: str | None = None) -> RefundRead:
    items: list[RefundItemRead] = []
    subtotal = Decimal("0.00")
    item_count = Decimal("0")
    for raw in refund.items or []:
        quantity = Decimal(str(raw.get("quantity", 0)))
        item_count += quantity
        unit_price = Decimal(str(raw.get("unit_price", "0")))
        line_total = Decimal(str(raw.get("line_total", "0")))
        subtotal += line_total
        items.append(RefundItemRead(product_id=UUID(raw["product_id"]), variant_id=UUID(raw["variant_id"]) if raw.get("variant_id") else None, variant_name=raw.get("variant_name"), product_name=raw.get("product_name", ""), sku=raw.get("sku", ""), unit_price=unit_price, quantity=float(quantity), line_total=line_total))
    return RefundRead(
        id=refund.id,
        order_id=refund.order_id,
        order_number=order.order_number if order else None,
        cashier_name=cashier_name,
        method=refund.method,
        reason=refund.reason,
        currency_code=refund.currency_code,
        subtotal=subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        tax=refund.tax,
        total=refund.total,
        item_count=float(item_count),
        items=items,
        created_at=refund.created_at,
    )


@router.get("/orders/{order_id}/refunds", response_model=list[RefundRead], tags=["orders"])
async def list_order_refunds(order_id: UUID, context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db)) -> list[RefundRead]:
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    result = await db.execute(select(Refund, User.full_name).join(User, User.id == Refund.created_by).where(Refund.order_id == order.id).order_by(Refund.created_at.desc()))
    return [refund_read(refund, order, cashier_name) for refund, cashier_name in result.all()]


async def _refund_order(db: AsyncSession, context: StoreContext, membership: Membership, order_id: UUID, payload: RefundCreateRequest) -> RefundRead:
    await require_plan_feature(db, context.membership.company_id, "refunds")
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only paid orders can be refunded")
    existing_refunds = (await db.execute(select(Refund).where(Refund.order_id == order.id))).scalars().all()
    refunded_quantity: dict[tuple[UUID, UUID | None], Decimal] = defaultdict(int)
    for refund in existing_refunds:
        for raw in refund.items or []:
            key = (UUID(raw["product_id"]), UUID(raw["variant_id"]) if raw.get("variant_id") else None)
            refunded_quantity[key] += Decimal(str(raw.get("quantity", 0)))
    order_items = {(item.product_id, item.variant_id): item for item in order.items}
    snapshot: list[dict] = []
    subtotal = Decimal("0.00")
    for requested in payload.items:
        order_item = order_items.get((requested.product_id, requested.variant_id))
        if not order_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product is not part of this order")
        remaining = order_item.quantity - refunded_quantity.get((order_item.product_id, order_item.variant_id), 0)
        if requested.quantity > remaining:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only {remaining} of {order_item.product_name} can be refunded")
        requested_serials = [value.strip() for value in (requested.serial_numbers or []) if value.strip()]
        if requested_serials:
            if len(requested_serials) != int(requested.quantity):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provide one serial per unit for {order_item.product_name}")
            on_order = set((await db.execute(select(ProductSerial.serial_number).where(ProductSerial.order_item_id == order_item.id, ProductSerial.status == "sold", ProductSerial.serial_number.in_(requested_serials)))).scalars().all())
            missing = [value for value in requested_serials if value not in on_order]
            if missing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Serial not on this order: {', '.join(missing)}")
        line_total = (order_item.unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total
        snapshot.append({"product_id": str(order_item.product_id), "variant_id": str(order_item.variant_id) if order_item.variant_id else None, "variant_name": order_item.variant_name, "order_item_id": str(order_item.id), "product_name": order_item.product_name, "sku": order_item.sku, "unit_price": str(order_item.unit_price), "quantity": str(requested.quantity), "line_total": str(line_total), "serial_numbers": requested_serials, "unit_cost": str(order_item.cost_price) if order_item.cost_price is not None else None, "combo_components": order_item.combo_components})
    subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    store_settings = dict(context.store.preferences or {})
    if bool(store_settings.get("tax_inclusive", False)) or not bool(store_settings.get("charge_tax", True)):
        tax = Decimal("0.00")
        total = subtotal
    else:
        tax = (subtotal * context.store.service_tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + tax
    method = payload.method
    if method == "original":
        first_tender = next((tender for tender in order.tenders if tender.kind == "payment"), None)
        method = first_tender.method if first_tender else (order.payments[0].provider if order.payments else "cash")
    for row in snapshot:
        refund_unit_cost = Decimal(str(row["unit_cost"])) if row.get("unit_cost") not in (None, "") else None
        if row.get("combo_components"):
            await restore_combo_components(db, context.store.id, row["combo_components"], Decimal(str(row["quantity"])), "refund", "order_refund", order.order_number, refund_unit_cost, context.user.id)
            continue
        if row.get("variant_id"):
            variant_id = UUID(row["variant_id"])
            balance_result = await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id == variant_id).with_for_update())
            balance = balance_result.scalar_one_or_none()
            if not balance:
                balance = VariantInventoryBalance(store_id=context.store.id, variant_id=variant_id, on_hand=0, reorder_point=10)
                db.add(balance)
                await db.flush()
            balance.on_hand += Decimal(str(row["quantity"]))
            db.add(StockMovement(store_id=context.store.id, product_id=UUID(row["product_id"]), variant_id=variant_id, quantity=Decimal(str(row["quantity"])), movement_type="refund", reason="order_refund", reference_id=order.order_number, unit_cost=refund_unit_cost, created_by=context.user.id))
        else:
            balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == UUID(row["product_id"])).with_for_update())
            balance = balance_result.scalar_one_or_none()
            if not balance:
                balance = InventoryBalance(store_id=context.store.id, product_id=UUID(row["product_id"]), on_hand=0, reorder_point=10)
                db.add(balance)
                await db.flush()
            balance.on_hand += Decimal(str(row["quantity"]))
            db.add(StockMovement(store_id=context.store.id, product_id=UUID(row["product_id"]), quantity=Decimal(str(row["quantity"])), movement_type="refund", reason="order_refund", reference_id=order.order_number, unit_cost=refund_unit_cost, created_by=context.user.id))
    for row in snapshot:
        if row.get("order_item_id"):
            statement = select(ProductSerial).where(ProductSerial.order_item_id == UUID(row["order_item_id"]), ProductSerial.status == "sold")
            explicit_serials = row.get("serial_numbers") or []
            if explicit_serials:
                statement = statement.where(ProductSerial.serial_number.in_(explicit_serials))
            sold_serials = (await db.execute(statement.limit(int(Decimal(str(row["quantity"])))))).scalars().all()
            for serial in sold_serials:
                serial.status = "in_stock"
                serial.order_item_id = None
                serial.sold_at = None
                serial.customer_warranty_until = None
    refund = Refund(store_id=context.store.id, order_id=order.id, created_by=context.user.id, method=method, reason=(payload.reason or "").strip()[:255] or None, currency_code=order.currency_code, subtotal=subtotal, tax=tax, total=total, items=snapshot)
    db.add(refund)
    previously_refunded = sum((existing.total for existing in existing_refunds), Decimal("0.00"))
    if previously_refunded + subtotal >= order.subtotal:
        order.status = "refunded"
    await notify_company_managers(db, context.membership.company_id, context.store.id, "refund", f"Refund on {order.order_number}", f"{method.title()} refund of {total} {order.currency_code}")
    await queue_refund_note(db, context.store, order_number=order.order_number, total=total, currency_code=order.currency_code, method=method, actor=context.user.full_name)
    await log_audit(db, context.membership, context.store.id, "refunded", "order", order.id, {"order_number": order.order_number, "total": str(total), "method": method}, context.user)
    await record_activity(db, "order.refunded", company_id=context.membership.company_id, store_id=context.store.id, details={"company": await _company_name(db, context.membership.company_id), "store": context.store.name, "order_number": order.order_number, "amount": f"{total} {order.currency_code}", "method": method})
    await db.commit()
    # Best-effort buyer confirmation in a second transaction so a mail problem
    # cannot undo the refund.
    try:
        company_name = await _company_name(db, context.membership.company_id)
        if await queue_refund_confirmation(db, order, context.store, company_name=company_name, amount=total, method=method):
            await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Could not queue the refund confirmation")
    return refund_read(refund, order, context.user.full_name)


async def _void_paid_order(db: AsyncSession, context: StoreContext, order: Order) -> RefundRead:
    """Void a paid order by refunding every remaining item (money, stock, serials)."""
    existing_refunds = (await db.execute(select(Refund).where(Refund.order_id == order.id))).scalars().all()
    refunded: dict[tuple[UUID, UUID | None], Decimal] = defaultdict(int)
    for refund in existing_refunds:
        for raw in refund.items or []:
            key = (UUID(raw["product_id"]), UUID(raw["variant_id"]) if raw.get("variant_id") else None)
            refunded[key] += Decimal(str(raw.get("quantity", 0)))
    items = []
    for item in order.items:
        remaining = item.quantity - refunded.get((item.product_id, item.variant_id), 0)
        if remaining > 0:
            items.append(RefundItemRequest(product_id=item.product_id, variant_id=item.variant_id, quantity=remaining))
    if not items:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This order has already been fully refunded")
    payload = RefundCreateRequest(method="original", reason="paid order void", items=items)
    result = await _refund_order(db, context, context.membership, order.id, payload)
    order.status = "cancelled"
    await db.commit()
    return result


async def load_approval_policy(db: AsyncSession, company_id: UUID) -> ApprovalPolicy:
    company = await get_company(db, company_id)
    stored = (company.settings or {}).get("approval_policy") or default_approval_policy()
    return ApprovalPolicy.model_validate(stored)


def approval_gate(rule, amount: Decimal) -> str:
    """How an action of the given amount is treated: allow, review or request."""
    if rule is None or rule.mode == "off":
        return "allow"
    if rule.threshold is not None and amount <= rule.threshold:
        return "allow"
    return "review" if rule.mode == "review" else "request"


async def flag_discount_review(db: AsyncSession, context: StoreContext, order: Order, subtotal: Decimal, discount: Decimal) -> None:
    """Flag an oversized discount for review. Discounts are never held: the sale cannot wait."""
    if discount <= 0 or subtotal <= 0:
        return
    policy = await load_approval_policy(db, context.membership.company_id)
    if not policy.enabled:
        return
    rule = policy.rules.get("discount")
    if rule is None or rule.mode == "off":
        return
    percent = (discount / subtotal * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rule.threshold is not None and percent <= rule.threshold:
        return
    await log_audit(db, context.membership, context.store.id, "discount_reviewed", "order", order.id, {"order_number": order.order_number, "discount": str(discount), "percent": str(percent), "mode": rule.mode}, context.user)
    await notify_company_managers(db, context.membership.company_id, context.store.id, "discount_review", f"Discount on {order.order_number}", f"{percent}% off ({discount} {order.currency_code}) by {context.user.full_name}")
    await record_activity(db, "order.discount_reviewed", company_id=context.membership.company_id, store_id=context.store.id, details={"company": await _company_name(db, context.membership.company_id), "store": context.store.name, "order_number": order.order_number, "percent": str(percent), "amount": f"{discount} {order.currency_code}"})


async def _apply_product_update(db: AsyncSession, *, store_id: UUID, membership: Membership, product: Product, payload, user: User) -> Product:
    """Apply a product update payload and audit any price/cost change.

    Shared by the catalog endpoint and the approval executor so an approved
    price/cost edit applies exactly what the requester sent.
    """
    price_before = product.price
    cost_before = product.cost_price
    for field in ("name", "sku", "price", "cost_price", "category_id", "description", "image", "barcode", "brand", "unit", "track_inventory", "track_serials", "attributes", "modifier_group_id", "tax_rate", "is_active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(product, field, value.strip() if isinstance(value, str) and field in {"name", "sku", "barcode", "brand", "unit"} else value)
    if product.price != price_before or product.cost_price != cost_before:
        await log_audit(db, membership, store_id, "product_price_changed", "product", entity_id=product.id, details={"product": product.name, "price": str(product.price), "cost_price": str(product.cost_price) if product.cost_price is not None else None}, user=user)
    await db.commit()
    return product


async def _apply_inventory_change(db: AsyncSession, *, store_id: UUID, membership: Membership, product: Product, variant_id: UUID | None, quantity: Decimal, reason: str | None, user: User) -> InventoryRead:
    """Set a product or variant balance to ``quantity`` and record the movement.

    Shared by the inventory endpoint and the approval executor so an approved
    stock write-off applies exactly what the requester asked for.
    """
    variant = None
    if variant_id:
        variant = (await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id, ProductVariant.product_id == product.id))).scalar_one_or_none()
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
        balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store_id, VariantInventoryBalance.variant_id == variant.id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = VariantInventoryBalance(store_id=store_id, variant_id=variant.id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
    else:
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store_id, InventoryBalance.product_id == product.id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = InventoryBalance(store_id=store_id, product_id=product.id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
    difference = quantity - balance.on_hand
    balance.on_hand = quantity
    if difference:
        details = {"product": product.name, "quantity": str(balance.on_hand), "reason": reason}
        if variant:
            details["variant"] = variant.name
        db.add(StockMovement(store_id=store_id, product_id=product.id, variant_id=variant.id if variant else None, quantity=difference, movement_type="manual_adjustment", reason=reason, created_by=user.id))
        await log_audit(db, membership, store_id, "inventory_adjusted", "inventory", entity_id=product.id, details=details, user=user)
    if balance.on_hand <= (balance.reorder_point or 10):
        label = f"{product.name} · {variant.name}" if variant else product.name
        await notify_company_managers(db, membership.company_id, store_id, "low_stock", f"Low stock: {label}", f"Only {balance.on_hand} left (reorder point {balance.reorder_point or 10})")
    await db.commit()
    return await inventory_for_product(db, store_id, product)


async def _apply_points_change(db: AsyncSession, membership: Membership, customer: Customer, delta: int) -> dict:
    """Apply a loyalty-point delta, refusing to take a balance below zero."""
    updated = int(customer.points) + delta
    if updated < 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Customer only has {int(customer.points)} points")
    customer.points = updated
    await db.commit()
    return {"customer_id": str(customer.id), "points": updated}


async def _pending_approval_response(db: AsyncSession, membership: Membership, *, store_id: UUID, action: str, amount: Decimal, payload: dict, user: User, reason: str | None = None) -> JSONResponse:
    """Queue an approval request and return the 202 body the endpoints share."""
    policy = await load_approval_policy(db, membership.company_id)
    request = ApprovalRequest(company_id=membership.company_id, store_id=store_id, action=action, status="pending", amount=amount, reason=(reason or "").strip()[:255] or None, payload=payload, requested_by=user.id, expires_at=now_utc() + timedelta(minutes=policy.expiry_minutes))
    db.add(request)
    await notify_company_managers(db, membership.company_id, store_id, "approval_request", f"{action.replace('_', ' ').title()} needs approval", f"{amount} requested by {user.full_name}")
    await log_audit(db, membership, store_id, f"{action}_approval_requested", action, entity_id=None, details={"amount": str(amount)}, user=user)
    await record_activity(db, "approval.requested", company_id=membership.company_id, store_id=store_id, details={"company": await _company_name(db, membership.company_id), "action": action, "amount": str(amount)})
    await db.commit()
    await db.refresh(request)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "pending_approval", "approval_request": ApprovalRequestRead.model_validate(request).model_dump(mode="json")})


async def restore_inventory(db: AsyncSession, store_id: UUID, product_id: UUID, variant_id: UUID | None, quantity: Decimal, movement_type: str, reason: str, reference_id: str | None, unit_cost: Decimal | None, created_by: UUID | None) -> None:
    """Return stock to the shelf, creating the balance row if this is its first receipt."""
    if variant_id:
        balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == store_id, VariantInventoryBalance.variant_id == variant_id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = VariantInventoryBalance(store_id=store_id, variant_id=variant_id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
    else:
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store_id, InventoryBalance.product_id == product_id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = InventoryBalance(store_id=store_id, product_id=product_id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
    balance.on_hand += quantity
    db.add(StockMovement(store_id=store_id, product_id=product_id, variant_id=variant_id, quantity=quantity, movement_type=movement_type, reason=reason, reference_id=reference_id, unit_cost=unit_cost, created_by=created_by))


async def restore_combo_components(db: AsyncSession, store_id: UUID, combo_components: list, multiplier: Decimal, movement_type: str, reason: str, reference_id: str | None, unit_cost: Decimal | None, created_by: UUID | None) -> None:
    """Undo a combo sale by returning every component to stock (docs/combos-plan.md)."""
    for component in combo_components:
        product_id = UUID(component["product_id"])
        variant_id = UUID(component["variant_id"]) if component.get("variant_id") else None
        quantity = Decimal(str(component.get("quantity", "1"))) * multiplier
        await restore_inventory(db, store_id, product_id, variant_id, quantity, movement_type, reason, reference_id, unit_cost, created_by)


@router.post("/orders/{order_id}/refund", status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_order_refund(order_id: UUID, payload: RefundCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)):
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    policy = await load_approval_policy(db, membership.company_id)
    rule = policy.rules.get("refund")
    order_items = {(line.product_id, line.variant_id): line for line in order.items}
    amount = sum((order_items[(line.product_id, line.variant_id)].unit_price * line.quantity for line in payload.items if (line.product_id, line.variant_id) in order_items), Decimal("0.00"))
    gate = approval_gate(rule, amount) if policy.enabled else "allow"
    if gate == "allow":
        return await _refund_order(db, context, membership, order_id, payload)
    if gate == "review":
        result = await _refund_order(db, context, membership, order_id, payload)
        await log_audit(db, membership, context.store.id, "refund_reviewed", "order", order.id, {"order_number": order.order_number, "amount": str(amount), "mode": "review"}, user=context.user)
        await notify_company_managers(db, membership.company_id, context.store.id, "refund_review", f"Refund flagged on {order.order_number}", f"{amount} {order.currency_code} by {context.user.full_name}")
        await db.commit()
        return result
    is_approver = rule is not None and membership.role in rule.approvers
    if is_approver and not (policy.maker_checker and membership.role != "owner"):
        return await _refund_order(db, context, membership, order_id, payload)
    request = ApprovalRequest(company_id=membership.company_id, store_id=context.store.id, action="refund", status="pending", amount=amount, reason=(payload.reason or "").strip()[:255] or None, payload={"order_id": str(order.id), "items": [line.model_dump(mode="json") for line in payload.items], "method": payload.method, "reason": payload.reason}, requested_by=context.user.id, expires_at=now_utc() + timedelta(minutes=policy.expiry_minutes))
    db.add(request)
    await notify_company_managers(db, membership.company_id, context.store.id, "approval_request", f"Refund needs approval on {order.order_number}", f"{amount} {order.currency_code} requested by {context.user.full_name}")
    await log_audit(db, membership, context.store.id, "refund_approval_requested", "order", order.id, {"order_number": order.order_number, "amount": str(amount)}, context.user)
    await record_activity(db, "approval.requested", company_id=membership.company_id, store_id=context.store.id, details={"company": await _company_name(db, membership.company_id), "action": "refund", "order_number": order.order_number, "amount": f"{amount} {order.currency_code}"})
    await db.commit()
    await db.refresh(request)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "pending_approval", "approval_request": ApprovalRequestRead.model_validate(request).model_dump(mode="json")})


@router.get("/approvals", response_model=list[ApprovalRequestRead], tags=["approvals"])
async def list_approvals(membership: Membership = Depends(require_roles("owner", "manager")), db: AsyncSession = Depends(get_db), status_filter: str = Query(default="pending", alias="status")) -> list[ApprovalRequestRead]:
    statement = select(ApprovalRequest).where(ApprovalRequest.company_id == membership.company_id).order_by(ApprovalRequest.created_at.desc()).limit(200)
    if status_filter:
        statement = statement.where(ApprovalRequest.status == status_filter)
    return [ApprovalRequestRead.model_validate(row) for row in (await db.execute(statement)).scalars().all()]


@router.post("/approvals/{request_id}/reject", response_model=ApprovalRequestRead, tags=["approvals"])
async def reject_approval(request_id: UUID, payload: ApprovalDecisionRequest, membership: Membership = Depends(require_roles("owner", "manager")), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> ApprovalRequestRead:
    request = (await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id, ApprovalRequest.company_id == membership.company_id))).scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request has already been decided")
    request.status = "rejected"
    request.decided_by = membership.user_id
    request.decided_at = now_utc()
    request.decision_reason = (payload.reason or "").strip()[:255] or None
    await log_audit(db, membership, request.store_id, "approval_rejected", "approval", request.id, {"action": request.action, "reason": request.decision_reason}, user)
    await record_activity(db, "approval.rejected", company_id=membership.company_id, store_id=request.store_id, details={"company": await _company_name(db, membership.company_id), "action": request.action})
    await db.commit()
    await db.refresh(request)
    return ApprovalRequestRead.model_validate(request)


@router.post("/approvals/{request_id}/approve", tags=["approvals"])
async def approve_approval(request_id: UUID, payload: ApprovalDecisionRequest, context: StoreContext = Depends(get_store_context), membership: Membership = Depends(require_roles("owner", "manager")), db: AsyncSession = Depends(get_db)):
    request = (await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == request_id, ApprovalRequest.company_id == membership.company_id))).scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request has already been decided")
    if request.expires_at and request.expires_at < now_utc():
        request.status = "expired"
        request.decided_at = now_utc()
        await db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request has expired")
    policy = await load_approval_policy(db, membership.company_id)
    rule = policy.rules.get(request.action)
    if rule is None or membership.role not in rule.approvers:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to approve this action")
    if policy.maker_checker and request.requested_by == membership.user_id and membership.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot approve your own request")
    request_payload = request.payload or {}
    if request.action == "refund":
        store = await db.get(Store, request.store_id)
        refund_payload = RefundCreateRequest.model_validate({"items": request_payload.get("items") or [], "method": request_payload.get("method") or "original", "reason": request_payload.get("reason")})
        result = await _refund_order(db, StoreContext(user=context.user, membership=membership, store=store), membership, UUID(str(request_payload.get("order_id"))), refund_payload)
        body = result.model_dump(mode="json")
    elif request.action == "stock_write_off":
        product = (await db.execute(select(Product).where(Product.id == UUID(str(request_payload.get("product_id"))), Product.company_id == membership.company_id, Product.is_active.is_(True)))).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The product no longer exists")
        variant_id = UUID(str(request_payload["variant_id"])) if request_payload.get("variant_id") else None
        result = await _apply_inventory_change(db, store_id=request.store_id, membership=membership, product=product, variant_id=variant_id, quantity=Decimal(str(request_payload.get("quantity"))), reason=(request_payload.get("reason") or "approved stock adjustment"), user=context.user)
        body = result.model_dump(mode="json")
    elif request.action == "loyalty_adjust":
        customer = (await db.execute(select(Customer).where(Customer.id == UUID(str(request_payload.get("customer_id"))), Customer.company_id == membership.company_id))).scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The customer no longer exists")
        body = await _apply_points_change(db, membership, customer, int(request_payload.get("delta") or 0))
    elif request.action == "price_cost_edit":
        product = (await db.execute(select(Product).where(Product.id == UUID(str(request_payload.get("product_id"))), Product.company_id == membership.company_id, Product.is_active.is_(True)))).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The product no longer exists")
        update_request = ProductUpdateRequest.model_validate(request_payload)
        await _apply_product_update(db, store_id=request.store_id, membership=membership, product=product, payload=update_request, user=context.user)
        body = {"product_id": str(product.id), "price": str(product.price), "cost_price": str(product.cost_price) if product.cost_price is not None else None}
    elif request.action == "cancel_paid_order":
        order = await order_by_id(db, UUID(str(request_payload.get("order_id"))))
        if order.store_id != request.store_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The order no longer exists")
        store = await db.get(Store, request.store_id)
        await _void_paid_order(db, StoreContext(user=context.user, membership=membership, store=store), order)
        body = {"order_id": str(order.id), "status": order.status}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported approval action")
    request.status = "approved"
    request.decided_by = membership.user_id
    request.decided_at = now_utc()
    request.decision_reason = (payload.reason or "").strip()[:255] or None
    await log_audit(db, membership, request.store_id, "approval_approved", "approval", request.id, {"action": request.action}, context.user)
    await record_activity(db, "approval.approved", company_id=membership.company_id, store_id=request.store_id, details={"company": await _company_name(db, membership.company_id), "action": request.action})
    await db.commit()
    return JSONResponse(content=body)


@router.get("/billing/subscription", response_model=SubscriptionRead, tags=["billing"])
async def current_subscription(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> SubscriptionRead:
    result = await db.execute(select(Subscription).where(Subscription.company_id == membership.company_id, Subscription.status.in_(["active", "pending"])).order_by(Subscription.created_at.desc()))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return SubscriptionRead.model_validate(subscription)


@router.put("/billing/schedule", response_model=SubscriptionRead, tags=["billing"])
async def schedule_plan_change(payload: BillingScheduleRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> SubscriptionRead:
    ent = await load_entitlement(db, membership.company_id)
    current = ent.subscription
    if current is None or current.plan_code == FREE_PLAN_CODE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An active paid plan is required to schedule a change")
    target = await get_plan(db, payload.plan_code)
    if target.code == current.plan_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This plan is already active")
    keep_store_ids = list(dict.fromkeys(payload.keep_store_ids))
    keep_member_ids = list(dict.fromkeys(payload.keep_member_ids))
    if len(keep_store_ids) > target.max_stores:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{target.name} allows at most {target.max_stores} store(s)")
    try:
        parsed_store_ids = [UUID(raw_id) for raw_id in keep_store_ids]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more store identifiers are invalid")
    if keep_store_ids:
        valid_stores = await db.scalar(select(func.count(Store.id)).where(Store.company_id == membership.company_id, Store.id.in_(parsed_store_ids)))
        if valid_stores != len(parsed_store_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more stores are not part of this workspace")
    if len(keep_member_ids) > target.max_members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{target.name} allows at most {target.max_members} team member(s)")
    try:
        parsed_member_ids = [UUID(raw_id) for raw_id in keep_member_ids]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more team member identifiers are invalid")
    if keep_member_ids:
        valid_members = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == membership.company_id, Membership.id.in_(parsed_member_ids)))
        if valid_members != len(parsed_member_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more team members are not part of this workspace")
    current.scheduled_plan_code = target.code
    current.scheduled_store_ids = keep_store_ids or None
    current.scheduled_member_ids = keep_member_ids or None
    await db.commit()
    await db.refresh(current)
    return SubscriptionRead.model_validate(current)


@router.delete("/billing/schedule", response_model=SubscriptionRead, tags=["billing"])
async def clear_plan_schedule(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> SubscriptionRead:
    ent = await load_entitlement(db, membership.company_id)
    current = ent.subscription
    if current is None or ent.synthetic_free:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active plan to reschedule")
    current.scheduled_plan_code = None
    current.scheduled_store_ids = None
    current.scheduled_member_ids = None
    await db.commit()
    await db.refresh(current)
    return SubscriptionRead.model_validate(current)


@router.post("/billing/checkout", response_model=BillingCheckoutRead, status_code=status.HTTP_201_CREATED, tags=["billing"])
async def create_billing_checkout(payload: BillingCheckoutRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> BillingCheckoutRead:
    plan = await get_plan(db, payload.plan_code)
    if plan.monthly_price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Free plan does not need payment")
    ent = await load_entitlement(db, membership.company_id)
    governing = ent.subscription
    if (
        governing is not None
        and governing.plan_code != FREE_PLAN_CODE
        and plan.code != FREE_PLAN_CODE
        and plan.monthly_price < ent.plan.monthly_price
        and governing.scheduled_plan_code != plan.code
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{plan.name} is a downgrade from your current {ent.plan.name} plan. Downgrades are scheduled for the end of your current period from Billing — nothing is charged today.",
        )
    pending_result = await db.execute(select(Subscription).where(Subscription.company_id == membership.company_id, Subscription.status == "pending").order_by(Subscription.created_at.desc()))
    for pending_subscription in pending_result.scalars().all():
        pending_subscription.status = "canceled"
        pending_subscription.ends_at = now_utc()
    billing_cycle = payload.billing_cycle
    total_amount = period_total(plan.monthly_price, billing_cycle)
    subscription = Subscription(company_id=membership.company_id, plan_code=plan.code, billing_cycle=billing_cycle, status="pending", starts_at=now_utc())
    db.add(subscription)
    await db.flush()
    reference = f"plan-{membership.company_id}-{uuid.uuid4().hex}"
    provider_metadata = {"type": "subscription", "subscription_id": str(subscription.id), "plan_code": plan.code, "billing_cycle": billing_cycle}
    provider, provider_payment = await request_billing_payment(db, total_amount, reference, provider_metadata)
    provider_metadata["provider"] = provider
    payment = BillingPayment(subscription_id=subscription.id, company_id=membership.company_id, plan_code=plan.code, billing_cycle=billing_cycle, provider=provider, amount=total_amount, currency_code=provider_payment.currency, external_id=provider_payment.id, reference_id=provider_payment.reference_id or reference, status=provider_payment.status, qr_string=provider_payment.qr_string, checkout_url=provider_payment.checkout_url, provider_metadata=provider_metadata)
    db.add(payment)
    await db.commit()
    await db.refresh(subscription)
    await db.refresh(payment)
    return BillingCheckoutRead(subscription=SubscriptionRead.model_validate(subscription), payment=BillingPaymentRead.model_validate(payment))


@router.delete("/billing/checkout", response_model=SubscriptionRead, tags=["billing"])
async def cancel_pending_checkout(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> SubscriptionRead:
    """Cancel an unpaid pending checkout and fall back to the current plan.

    A pending checkout never takes a user off the plan they already paid for:
    cancelling marks pending subscriptions ``canceled``, expires their still-open
    payments (so a late webhook cannot activate them) and returns the governing
    subscription. When no paid plan is in force (a plan picked during onboarding
    that was never paid) the workspace falls back to the Free plan with its
    capacity enforced.
    """
    company_id = membership.company_id
    now = now_utc()
    pending_result = await db.execute(select(Subscription).where(Subscription.company_id == company_id, Subscription.status == "pending"))
    pending_rows = list(pending_result.scalars().all())
    if not pending_rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pending checkout to cancel")
    for subscription in pending_rows:
        subscription.status = "canceled"
        subscription.ends_at = now
        open_payments = (
            await db.execute(
                select(BillingPayment).where(
                    BillingPayment.subscription_id == subscription.id,
                    BillingPayment.status.in_(["pending", "scanned"]),
                )
            )
        ).scalars().all()
        for payment in open_payments:
            payment.status = "expired"
    ent = await load_entitlement(db, company_id)
    if ent.subscription is not None and not ent.synthetic_free:
        governing = ent.subscription
    else:
        free_plan = await db.get(Plan, FREE_PLAN_CODE)
        if free_plan is None:
            raise LookupError("Free plan is not configured")
        paused_store_ids = await pause_stores_over_capacity(db, company_id, limit=free_plan.max_stores)
        revoked_member_ids = await revoke_staff_over_capacity(db, company_id)
        governing = Subscription(
            company_id=company_id,
            plan_code=FREE_PLAN_CODE,
            billing_cycle="monthly",
            status="active",
            starts_at=now,
            ends_at=None,
            paused_store_ids=paused_store_ids,
            paused_member_ids=revoked_member_ids,
        )
        db.add(governing)
        await db.flush()
        await record_capacity_actions(
            db, subscription=governing, resource_type="store", resource_ids=paused_store_ids, action="pause", reason="checkout_cancelled"
        )
        await record_capacity_actions(
            db, subscription=governing, resource_type="member", resource_ids=revoked_member_ids, action="pause", reason="checkout_cancelled"
        )
    await db.commit()
    await db.refresh(governing)
    return SubscriptionRead.model_validate(governing)


@router.get("/billing/payments", response_model=list[BillingPaymentRead], tags=["billing"])
async def billing_payments(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=100)) -> list[BillingPaymentRead]:
    query = select(BillingPayment).join(Subscription, Subscription.id == BillingPayment.subscription_id).where(Subscription.company_id == membership.company_id).order_by(BillingPayment.created_at.desc()).limit(limit)
    return [BillingPaymentRead.model_validate(payment) for payment in (await db.execute(query)).scalars().all()]


@router.get("/billing/receipts", response_model=list[BillingReceiptRead], tags=["billing"])
async def billing_receipts(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=100)) -> list[BillingReceiptRead]:
    query = select(BillingReceipt).where(BillingReceipt.company_id == membership.company_id).order_by(BillingReceipt.created_at.desc()).limit(limit)
    return [BillingReceiptRead.model_validate(receipt) for receipt in (await db.execute(query)).scalars().all()]


@router.get("/team", response_model=list[MembershipRead], tags=["team"])
async def list_team(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[MembershipRead]:
    result = await db.execute(select(Membership).where(Membership.company_id == membership.company_id).options(selectinload(Membership.user)).order_by(Membership.created_at))
    memberships = result.scalars().all()
    output = []
    for member in memberships:
        output.append(MembershipRead(id=member.id, user_id=member.user_id, company_id=member.company_id, role=member.role, status=member.status, user=user_read(member.user), store_ids=await get_membership_stores(db, member.id)))
    return output


@router.post("/team/invitations", response_model=InvitationRead, status_code=status.HTTP_201_CREATED, tags=["team"])
async def invite_team_member(payload: InvitationCreateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> InvitationRead:
    block_detail = await member_capacity_block_detail(db, membership.company_id, count_invited=True, action="invite team members")
    if block_detail:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=block_detail)
    if payload.store_ids:
        await require_plan_feature(db, membership.company_id, "roles_permissions")
        valid_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == membership.company_id, Store.id.in_(payload.store_ids), Store.is_active.is_(True)))
        if valid_count != len(set(payload.store_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more stores are not available")
    raw_token = create_opaque_token()
    invitation = Invitation(company_id=membership.company_id, email=payload.email.lower(), role=payload.role, store_ids=[str(store_id) for store_id in payload.store_ids], token_hash=hash_opaque_token(raw_token), expires_at=now_utc() + timedelta(days=7), invited_by=membership.user_id)
    db.add(invitation)
    company = await get_company(db, membership.company_id)
    await record_activity(db, "team.invited", company_id=membership.company_id, email=invitation.email, details={"company": company.name, "role": invitation.role})
    await queue_team_activity(db, membership.company_id, title=f"Team invite · {company.name}", detail=f"{invitation.email} was invited as {invitation.role}.")
    await db.commit()
    await db.refresh(invitation)
    await send_invitation_email(invitation.email, raw_token, company.name)
    return InvitationRead.model_validate({**invitation.__dict__, "dev_invitation_token": raw_token if settings.environment in {"development", "test"} else None})


@router.post("/team/invitations/accept", response_model=TokenResponse, tags=["team"])
async def accept_team_invitation(payload: InvitationAcceptRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(Invitation).where(Invitation.token_hash == hash_opaque_token(payload.token)))
    invitation = result.scalar_one_or_none()
    if not invitation or invitation.accepted_at or invitation.expires_at < now_utc():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation is invalid or expired")
    existing_result = await db.execute(select(User).where(User.email == invitation.email))
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists; sign in instead")
    block_detail = await member_capacity_block_detail(db, invitation.company_id, count_invited=False, action="accept team invitations")
    if block_detail:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=block_detail)
    user = User(email=invitation.email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password), is_email_verified=True)
    db.add(user)
    await db.flush()
    member = Membership(company_id=invitation.company_id, user_id=user.id, role=invitation.role, status="active")
    db.add(member)
    await db.flush()
    store_ids = [UUID(store_id) for store_id in invitation.store_ids]
    if not store_ids:
        stores_result = await db.execute(select(Store.id).where(Store.company_id == invitation.company_id, Store.is_active.is_(True)))
        store_ids = list(stores_result.scalars().all())
    for store_id in store_ids:
        db.add(MembershipStore(membership_id=member.id, store_id=store_id))
    invitation.accepted_at = now_utc()
    await record_activity(db, "team.invitation_accepted", user=user, company_id=invitation.company_id, details={"company": await _company_name(db, invitation.company_id), "role": invitation.role})
    await queue_team_activity(db, invitation.company_id, title="Team member joined", detail=f"{user.full_name} ({user.email}) joined as {invitation.role}.")
    session, refresh_token = await create_session(db, user, remember=True, request=request)
    cookie_max_age = session_cookie_max_age(session)
    await db.commit()
    await db.refresh(user)
    _set_refresh_cookie(response, refresh_token, max_age=cookie_max_age)
    return TokenResponse(
        access_token=create_token(user.id, session_id=session.id),
        expires_in=settings.jwt_access_ttl_minutes * 60,
        user=user_read(user),
    )


@router.patch("/team/{membership_id}", response_model=MembershipRead, tags=["team"])
async def update_team_member(membership_id: UUID, payload: MembershipUpdateRequest, actor: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> MembershipRead:
    result = await db.execute(select(Membership).where(Membership.id == membership_id, Membership.company_id == actor.company_id).options(selectinload(Membership.user)))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    if member.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner role cannot be changed")
    if payload.role is not None or payload.store_ids is not None:
        await require_plan_feature(db, actor.company_id, "roles_permissions")
    if payload.role is not None:
        member.role = payload.role
    if payload.store_ids is not None:
        valid_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == actor.company_id, Store.id.in_(payload.store_ids), Store.is_active.is_(True)))
        if valid_count != len(set(payload.store_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more stores are not available")
        old_links = (await db.execute(select(MembershipStore).where(MembershipStore.membership_id == member.id))).scalars().all()
        for link in old_links:
            await db.delete(link)
        for store_id in payload.store_ids:
            db.add(MembershipStore(membership_id=member.id, store_id=store_id))
    if payload.status is not None:
        if payload.status == "active" and member.status != "active" and member.role != "owner":
            ent = await load_entitlement(db, actor.company_id)
            active_count = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == actor.company_id, Membership.status == "active"))
            if ent.plan and active_count >= ent.plan.max_members:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{ent.plan.name} plan allows {ent.plan.max_members} active team member(s). Upgrade your plan to add more.")
        member.status = payload.status
    await queue_team_activity(db, actor.company_id, title="Team member updated", detail=f"{member.user.full_name} is now {member.role} ({member.status}).")
    await db.commit()
    return MembershipRead(id=member.id, user_id=member.user_id, company_id=member.company_id, role=member.role, status=member.status, user=user_read(member.user), store_ids=await get_membership_stores(db, member.id))


@router.delete("/team/{membership_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["team"])
async def remove_team_member(membership_id: UUID, actor: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> Response:
    result = await db.execute(select(Membership).where(Membership.id == membership_id, Membership.company_id == actor.company_id))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    if member.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner cannot be removed")
    removed_user = await db.get(User, member.user_id)
    label = (removed_user.full_name or removed_user.email) if removed_user else "A team member"
    await queue_team_activity(db, actor.company_id, title="Team member removed", detail=f"{label} was removed from the team.")
    member.status = "revoked"
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def signature_failure_reason(raw_body: bytes, signature: str, secret: str | None, mode: str, environment: str) -> str | None:
    """Return why a ChmabaPay signature is rejected, or ``None`` when it is valid."""
    if not secret:
        if mode == "mock" and environment != "production":
            return None
        return "the webhook secret is not configured"
    if not signature:
        return "the signature header is missing"
    pieces = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in signature.split(",") if "=" in part}
    timestamp = pieces.get("t")
    received = pieces.get("v1")
    if not timestamp or not received:
        return "the signature header is malformed"
    try:
        age = abs(now_utc().timestamp() - int(timestamp))
    except ValueError:
        return "the signature timestamp is invalid"
    if age >= 300:
        return "the signature timestamp is stale"
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received, expected):
        return "the signature does not match the configured secret"
    return None


def signature_is_valid(raw_body: bytes, signature: str, secret: str | None, mode: str, environment: str) -> bool:
    return signature_failure_reason(raw_body, signature, secret, mode, environment) is None


TERMINAL_BILLING_PAYMENT_STATUSES = frozenset({"paid", "failed", "expired", "canceled"})


async def _issue_billing_receipt(
    db: AsyncSession,
    *,
    payment: BillingPayment,
    subscription: Subscription,
    period_start: datetime | None,
    period_end: datetime | None,
    paid_at: datetime,
) -> BillingReceipt:
    """Issue the immutable receipt for a fulfilled payment.

    Called only from :func:`fulfill_billing_payment`, which is itself guarded by
    ``BillingPayment.fulfilled_at`` — so exactly one receipt is ever created per
    payment. The number is drawn from ``billing_receipt_number_seq``.
    """
    sequence = await db.scalar(text("SELECT nextval('billing_receipt_number_seq')"))
    receipt = BillingReceipt(
        receipt_number=f"CHM-{paid_at.year}-{int(sequence):06d}",
        company_id=payment.company_id,
        subscription_id=subscription.id,
        billing_payment_id=payment.id,
        plan_code=payment.plan_code or subscription.plan_code,
        billing_cycle=payment.billing_cycle or subscription.billing_cycle,
        period_start=period_start,
        period_end=period_end,
        amount=payment.amount,
        currency_code=payment.currency_code,
        provider=payment.provider,
        paid_at=paid_at,
    )
    db.add(receipt)
    # Queue the receipt email in the same transaction as the receipt itself:
    # ``fulfill_billing_payment`` is idempotent, so this runs exactly once.
    await queue_billing_receipt_email(
        db,
        company_id=payment.company_id,
        plan_code=receipt.plan_code,
        amount=receipt.amount,
        currency_code=receipt.currency_code,
        receipt_number=receipt.receipt_number,
        period_end=receipt.period_end,
        paid_at=paid_at,
    )
    return receipt


async def fulfill_billing_payment(provider_id: str, reference_id: str | None, approved_at: datetime | None, db: AsyncSession) -> bool:
    """Apply a confirmed provider payment to its pending subscription.

    Idempotent by construction: the payment row is locked and its
    ``fulfilled_at`` marker is set exactly once, so a webhook replayed any
    number of times (or racing a poll / mock completion) activates the plan
    exactly once. The purchase snapshot (plan, cycle, period) is frozen here.
    """
    query = select(BillingPayment).where(BillingPayment.external_id == provider_id)
    if reference_id:
        query = select(BillingPayment).where((BillingPayment.external_id == provider_id) | (BillingPayment.reference_id == reference_id))
    payment = (await db.execute(query.with_for_update())).scalars().first()
    if not payment:
        return False
    if payment.fulfilled_at is not None:
        return True
    subscription_result = await db.execute(select(Subscription).where(Subscription.id == payment.subscription_id).with_for_update())
    subscription = subscription_result.scalar_one()
    approved = approved_at or now_utc()
    payment.status = "paid"
    payment.approved_at = approved
    payment.fulfilled_at = approved
    payment.company_id = subscription.company_id
    payment.plan_code = subscription.plan_code
    payment.billing_cycle = subscription.billing_cycle
    await record_activity(db, "billing.plan_paid", company_id=subscription.company_id, details={"plan": subscription.plan_code, "cycle": subscription.billing_cycle, "amount": f"{payment.amount} {payment.currency_code}"})
    if subscription.status != "pending":
        return True
    active_result = await db.execute(select(Subscription).where(Subscription.company_id == subscription.company_id, Subscription.status == "active"))
    actives = active_result.scalars().all()
    governing = next((active for active in actives if active.id != subscription.id and is_in_force(active)), None)
    if (
        governing is not None
        and governing.plan_code == subscription.plan_code
        and governing.ends_at is not None
        and governing.ends_at > approved
    ):
        governing.scheduled_plan_code = None
        governing.scheduled_store_ids = None
        governing.scheduled_member_ids = None
        queued = next(
            (
                active
                for active in actives
                if active.id != subscription.id
                and active.plan_code == subscription.plan_code
                and active.starts_at is not None
                and active.starts_at > approved
                and active.ends_at is not None
            ),
            None,
        )
        if queued is not None:
            previous_end = queued.ends_at
            queued.ends_at = period_end(previous_end, subscription.billing_cycle)
            payment.subscription_id = queued.id
            payment.period_start = previous_end
            payment.period_end = queued.ends_at
            subscription.status = "canceled"
            subscription.ends_at = approved
            await _issue_billing_receipt(db, payment=payment, subscription=queued, period_start=previous_end, period_end=queued.ends_at, paid_at=approved)
        else:
            boundary = governing.ends_at
            subscription.status = "active"
            subscription.starts_at = boundary
            subscription.ends_at = period_end(boundary, subscription.billing_cycle)
            payment.period_start = boundary
            payment.period_end = subscription.ends_at
            await _issue_billing_receipt(db, payment=payment, subscription=subscription, period_start=boundary, period_end=subscription.ends_at, paid_at=approved)
        return True
    if (
        governing is not None
        and governing.plan_code != subscription.plan_code
        and governing.scheduled_plan_code == subscription.plan_code
        and governing.ends_at is not None
        and governing.ends_at > approved
    ):
        boundary = governing.ends_at
        subscription.status = "active"
        subscription.starts_at = boundary
        subscription.ends_at = period_end(boundary, subscription.billing_cycle)
        subscription.scheduled_store_ids = governing.scheduled_store_ids
        subscription.scheduled_member_ids = governing.scheduled_member_ids
        governing.scheduled_plan_code = None
        governing.scheduled_store_ids = None
        governing.scheduled_member_ids = None
        payment.period_start = boundary
        payment.period_end = subscription.ends_at
        await _issue_billing_receipt(db, payment=payment, subscription=subscription, period_start=boundary, period_end=subscription.ends_at, paid_at=approved)
        return True
    paused_store_ids: list[str] = []
    paused_member_ids: list[str] = []
    keep_store_ids: list[str] = []
    keep_member_ids: list[str] = []
    for active in actives:
        if active.id == subscription.id:
            continue
        if active.paused_store_ids:
            paused_store_ids = list(active.paused_store_ids or [])
            paused_member_ids = list(active.paused_member_ids or [])
        if active.scheduled_plan_code == subscription.plan_code and not keep_store_ids:
            keep_store_ids = list(active.scheduled_store_ids or [])
            keep_member_ids = list(active.scheduled_member_ids or [])
        active.status = "canceled"
        active.ends_at = approved
    subscription.status = "active"
    subscription.starts_at = approved
    subscription.ends_at = period_end(approved, subscription.billing_cycle)
    payment.period_start = approved
    payment.period_end = subscription.ends_at
    await _issue_billing_receipt(db, payment=payment, subscription=subscription, period_start=approved, period_end=subscription.ends_at, paid_at=approved)
    if subscription.plan_code != FREE_PLAN_CODE:
        plan = await db.get(Plan, subscription.plan_code)
        if plan:
            if paused_store_ids or paused_member_ids:
                await restore_capacity(
                    db,
                    subscription.company_id,
                    plan=plan,
                    store_ids=paused_store_ids,
                    member_ids=paused_member_ids,
                    subscription=subscription,
                    reason="upgrade",
                )
            await enforce_plan_capacity(
                db,
                subscription.company_id,
                subscription=subscription,
                plan=plan,
                keep_store_ids=keep_store_ids,
                keep_member_ids=keep_member_ids,
                reason="upgrade",
            )
    return True


# Billing payment statuses that can still become ``paid`` via a late webhook
# or reconciliation. Terminal rows are never re-checked.
OPEN_BILLING_PAYMENT_STATUSES = frozenset({"pending", "scanned", "processing"})
# Skip very recent payments: their QR is still live and the webhook has not had
# a chance to arrive yet.
RECONCILE_MIN_AGE = timedelta(minutes=3)
RECONCILE_BATCH_LIMIT = 200


async def reconcile_pending_billing_payments(db: AsyncSession, *, limit: int = RECONCILE_BATCH_LIMIT) -> dict:
    """Re-check open plan payments with the provider and fulfill any that settled.

    A dropped ``payment.completed`` webhook must not leave a paying merchant
    unactivated. This asks the provider for the authoritative status of each open
    billing payment and routes a PAID result through
    :func:`fulfill_billing_payment`, which is idempotent (``fulfilled_at``), so it
    is safe to run alongside the webhook and repeatedly.
    """
    cutoff = now_utc() - RECONCILE_MIN_AGE
    rows = (
        await db.execute(
            select(BillingPayment)
            .where(
                BillingPayment.external_id.is_not(None),
                BillingPayment.fulfilled_at.is_(None),
                BillingPayment.status.in_(OPEN_BILLING_PAYMENT_STATUSES),
                BillingPayment.created_at <= cutoff,
            )
            .order_by(BillingPayment.created_at)
            .limit(limit)
        )
    ).scalars().all()
    if not rows:
        return {"checked": 0, "activated": 0, "closed": 0}
    provider = await active_payment_provider(db)
    reconcile = getattr(provider, "reconcile", None)
    if reconcile is None:
        return {"checked": 0, "activated": 0, "closed": 0}
    activated = 0
    closed = 0
    for payment in rows:
        try:
            result = await reconcile(payment.external_id)
        except PaymentProviderError:
            continue
        provider_status = str(result.get("status", "")).upper()
        if provider_status == "PAID":
            if await fulfill_billing_payment(payment.external_id, payment.reference_id, None, db):
                activated += 1
        elif provider_status in {"FAILED", "EXPIRED"} and payment.status not in TERMINAL_BILLING_PAYMENT_STATUSES:
            payment.status = "failed" if provider_status == "FAILED" else "expired"
            closed += 1
            try:
                await queue_billing_failure_email(
                    db,
                    company_id=payment.company_id,
                    plan_code=payment.plan_code or "",
                    amount=payment.amount,
                    currency_code=payment.currency_code,
                    reason=payment.status,
                )
            except Exception:
                logger.exception("Could not queue the billing-failure email")
    if activated or closed:
        logger.warning("Billing reconcile self-healed payments: activated=%s closed=%s", activated, closed)
    await db.commit()
    return {"checked": len(rows), "activated": activated, "closed": closed}


async def reconcile_open_order_payments(db: AsyncSession, *, limit: int = RECONCILE_BATCH_LIMIT) -> dict:
    """Re-check open KHQR order payments in bulk (late settlement)."""
    cutoff = now_utc() - RECONCILE_MIN_AGE
    orders = (
        await db.execute(
            select(Order)
            .join(Payment, Payment.order_id == Order.id)
            .where(
                Order.status.notin_(["paid", "refunded"]),
                Payment.external_id.is_not(None),
                Payment.status.notin_(["paid", "failed", "expired"]),
                Order.created_at <= cutoff,
            )
            .options(selectinload(Order.payments))
            .distinct()
            .order_by(Order.created_at)
            .limit(limit)
        )
    ).scalars().unique().all()
    activated = 0
    for order in orders:
        try:
            if await reconcile_pending_order_payment(db, order):
                activated += 1
        except HTTPException as exc:
            # Skip orders that cannot be fulfilled (e.g. stock consumed by a
            # concurrent sale) so one bad order does not abort the whole batch.
            if exc.status_code != status.HTTP_409_CONFLICT:
                raise
            await db.rollback()
    if activated:
        logger.warning("Order reconcile self-healed payments: activated=%s", activated)
    return {"checked": len(orders), "activated": activated}


async def reconcile_open_held_order_payments(db: AsyncSession, *, limit: int = RECONCILE_BATCH_LIMIT) -> dict:
    """Re-check pending online-order (held ticket) payments in bulk (late settlement)."""
    cutoff = now_utc() - RECONCILE_MIN_AGE
    held_orders = (
        await db.execute(
            select(HeldOrder)
            .where(
                HeldOrder.payment_status == "pending",
                HeldOrder.payment_external_id.is_not(None),
                HeldOrder.created_at <= cutoff,
            )
            .order_by(HeldOrder.created_at)
            .limit(limit)
        )
    ).scalars().all()
    provider = await active_payment_provider(db)
    reconcile = getattr(provider, "reconcile", None)
    if reconcile is None:
        return {"checked": 0, "paid": 0, "closed": 0}
    paid = 0
    closed = 0
    for held in held_orders:
        try:
            result = await reconcile(held.payment_external_id)
        except PaymentProviderError:
            continue
        provider_status = str(result.get("status", "")).upper()
        if provider_status == "PAID":
            held.payment_status = "paid"
            held.paid_at = now_utc()
            paid += 1
        elif provider_status in {"FAILED", "EXPIRED"}:
            held.payment_status = "failed" if provider_status == "FAILED" else "expired"
            closed += 1
    if paid or closed:
        logger.warning("Held-order reconcile self-healed payments: paid=%s closed=%s", paid, closed)
    return {"checked": len(held_orders), "paid": paid, "closed": closed}


async def _system_reverse_order(db: AsyncSession, order: Order) -> None:
    """Record a provider-initiated reversal as a refund and return stock.

    Runs without a user session; the original cashier is recorded as the actor.
    Refunds the not-yet-refunded items and marks the order ``refunded``.
    """
    if order.status == "refunded":
        return
    existing_refunds = (await db.execute(select(Refund).where(Refund.order_id == order.id))).scalars().all()
    refunded_quantity: dict[tuple[UUID, UUID | None], Decimal] = defaultdict(int)
    for refund in existing_refunds:
        for raw in refund.items or []:
            key = (UUID(raw["product_id"]), UUID(raw["variant_id"]) if raw.get("variant_id") else None)
            refunded_quantity[key] += Decimal(str(raw.get("quantity", 0)))
    snapshot: list[dict] = []
    subtotal = Decimal("0.00")
    for item in order.items:
        remaining = item.quantity - refunded_quantity.get((item.product_id, item.variant_id), 0)
        if remaining <= 0:
            continue
        line_total = (item.unit_price * remaining).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total
        snapshot.append({"product_id": str(item.product_id), "variant_id": str(item.variant_id) if item.variant_id else None, "variant_name": item.variant_name, "order_item_id": str(item.id), "product_name": item.product_name, "sku": item.sku, "unit_price": str(item.unit_price), "quantity": str(remaining), "line_total": str(line_total), "unit_cost": str(item.cost_price) if item.cost_price is not None else None, "combo_components": item.combo_components})
    if not snapshot:
        order.status = "refunded"
        return
    subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = (order.tax * subtotal / order.subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if order.subtotal else Decimal("0.00")
    for row in snapshot:
        reverse_unit_cost = Decimal(str(row["unit_cost"])) if row.get("unit_cost") not in (None, "") else None
        if row.get("combo_components"):
            await restore_combo_components(db, order.store_id, row["combo_components"], Decimal(str(row["quantity"])), "refund", "payment_reversed", order.order_number, reverse_unit_cost, order.created_by)
            continue
        if row.get("variant_id"):
            variant_id = UUID(row["variant_id"])
            balance_result = await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == order.store_id, VariantInventoryBalance.variant_id == variant_id).with_for_update())
            balance = balance_result.scalar_one_or_none()
            if not balance:
                balance = VariantInventoryBalance(store_id=order.store_id, variant_id=variant_id, on_hand=0, reorder_point=10)
                db.add(balance)
                await db.flush()
            balance.on_hand += Decimal(str(row["quantity"]))
            db.add(StockMovement(store_id=order.store_id, product_id=UUID(row["product_id"]), variant_id=variant_id, quantity=Decimal(str(row["quantity"])), movement_type="refund", reason="payment_reversed", reference_id=order.order_number, unit_cost=reverse_unit_cost, created_by=order.created_by))
        else:
            balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == order.store_id, InventoryBalance.product_id == UUID(row["product_id"])).with_for_update())
            balance = balance_result.scalar_one_or_none()
            if not balance:
                balance = InventoryBalance(store_id=order.store_id, product_id=UUID(row["product_id"]), on_hand=0, reorder_point=10)
                db.add(balance)
                await db.flush()
            balance.on_hand += Decimal(str(row["quantity"]))
            db.add(StockMovement(store_id=order.store_id, product_id=UUID(row["product_id"]), quantity=Decimal(str(row["quantity"])), movement_type="refund", reason="payment_reversed", reference_id=order.order_number, unit_cost=reverse_unit_cost, created_by=order.created_by))
    for row in snapshot:
        if row.get("order_item_id"):
            sold_serials = (await db.execute(select(ProductSerial).where(ProductSerial.order_item_id == UUID(row["order_item_id"]), ProductSerial.status == "sold").limit(int(Decimal(str(row["quantity"])))))).scalars().all()
            for serial in sold_serials:
                serial.status = "in_stock"
                serial.order_item_id = None
                serial.sold_at = None
                serial.customer_warranty_until = None
    db.add(Refund(store_id=order.store_id, order_id=order.id, created_by=order.created_by, method="original", reason="ChmabaPay payment reversed", currency_code=order.currency_code, subtotal=subtotal, tax=tax, total=subtotal + tax, items=snapshot))
    order.status = "refunded"


@router.post("/webhooks/chamabapay", status_code=status.HTTP_200_OK, include_in_schema=True, tags=["payments"])
async def chamabapay_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Apply a signed ChmabaPay event to its billing or order payment.

    Signature uses the ``t=…,v1=…`` HMAC-SHA256 scheme. Events are
    ``payment.completed``/``expired``/``superseded``/``reversed``; the outcome is
    decided from ``data.payment.status``. A ``reversed`` payment records a refund
    and returns stock. A paid test-scan payment activates the merchant's ABA
    PayWay link (the link's scope and entity travel in ``reference_id``).

    The signature header is read from either ``X-ChmabaPay-Signature`` (the
    product's name) or the legacy ``X-ChamabaPay-Signature`` spelling.

    Returns ``{"status": "ok"}`` with HTTP 200 once the event is applied.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-ChmabaPay-Signature") or request.headers.get("X-ChamabaPay-Signature") or ""
    cfg = await load_payment_settings(db)
    secret = cfg.get("chamabapay_webhook_secret")
    mode = cfg.get("chamabapay_mode") or settings.chamabapay_mode
    if not signature_is_valid(raw_body, signature, secret, mode, settings.environment):
        reason = signature_failure_reason(raw_body, signature, secret, mode, settings.environment)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ChmabaPay signature: {reason}")
    try:
        event = ChmabaPayWebhookEvent.model_validate(json.loads(raw_body))
    except (ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ChmabaPay event") from exc
    provider_payment = event.data.payment
    provider_id = provider_payment.id
    provider_status = (provider_payment.status or "").lower()
    reference_id = provider_payment.reference_id
    if not provider_id or not provider_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incomplete ChmabaPay payment")

    billing_query = select(BillingPayment).where((BillingPayment.external_id == provider_id) | (BillingPayment.reference_id == reference_id if reference_id else BillingPayment.external_id == provider_id))
    billing_payment = (await db.execute(billing_query)).scalars().first()
    if billing_payment and provider_payment.amount is not None and billing_payment.amount != provider_payment.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ChmabaPay payment amount does not match billing record")
    if billing_payment and billing_payment.status not in TERMINAL_BILLING_PAYMENT_STATUSES:
        previous_status = billing_payment.status
        billing_payment.status = provider_status
        if provider_status in {"failed", "expired"} and provider_status != previous_status:
            try:
                await queue_billing_failure_email(
                    db,
                    company_id=billing_payment.company_id,
                    plan_code=billing_payment.plan_code or "",
                    amount=billing_payment.amount,
                    currency_code=billing_payment.currency_code,
                    reason=provider_status,
                )
            except Exception:
                logger.exception("Could not queue the billing-failure email")
    if provider_status == "paid":
        await fulfill_billing_payment(provider_id, reference_id, provider_payment.approved_at, db)

    payment_query = select(Payment).where((Payment.external_id == provider_id) | (Payment.reference_id == reference_id if reference_id else Payment.external_id == provider_id)).options(selectinload(Payment.order).selectinload(Order.items))
    payment = (await db.execute(payment_query)).scalars().first()
    if payment and provider_payment.amount is not None and payment.amount != provider_payment.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ChmabaPay payment amount does not match order record")
    if payment:
        payment.status = provider_status
        if provider_status == "paid":
            await complete_order(db, payment.order_id, now_utc())
        elif provider_status in {"expired", "failed", "superseded"}:
            if payment.order.status != "pending_pickup":
                payment.order.status = f"payment_{provider_status}"
                await release_order_serials(db, payment.order)
        elif provider_status == "reversed":
            await _system_reverse_order(db, payment.order)
    held_order = (await db.execute(select(HeldOrder).where(HeldOrder.payment_external_id == provider_id))).scalars().first()
    if held_order and not held_order.paid_at:
        if provider_status == "paid":
            held_order.payment_status = "paid"
            held_order.paid_at = provider_payment.approved_at or now_utc()
        elif provider_status in {"expired", "failed", "superseded"}:
            held_order.payment_status = provider_status
    if provider_status == "paid" and reference_id and reference_id.startswith(TEST_SCAN_REFERENCE_PREFIX):
        await _activate_link_from_test_scan_reference(db, reference_id, provider_id)
    await db.commit()
    return {"status": "ok"}


@router.post("/mock/chamabapay/{provider_payment_id}/complete", status_code=status.HTTP_204_NO_CONTENT, tags=["development"])
async def complete_mock_chamabapay_payment(provider_payment_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Dev-only completion for ChmabaPay mock payments (no sandbox exists)."""
    cfg = await load_payment_settings(db)
    if settings.environment == "production" or (cfg.get("chamabapay_mode") or settings.chamabapay_mode) != "mock":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock payment endpoint is disabled")
    order_payment_result = await db.execute(select(Payment).where(Payment.external_id == provider_payment_id))
    order_payment = order_payment_result.scalar_one_or_none()
    if order_payment:
        order_payment.status = "paid"
        await complete_order(db, order_payment.order_id)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    held_result = await db.execute(select(HeldOrder).where(HeldOrder.payment_external_id == provider_payment_id))
    held_order = held_result.scalar_one_or_none()
    if held_order:
        held_order.payment_status = "paid"
        held_order.paid_at = now_utc()
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    billing_result = await db.execute(select(BillingPayment).where(BillingPayment.external_id == provider_payment_id))
    billing_payment = billing_result.scalar_one_or_none()
    if billing_payment:
        await fulfill_billing_payment(provider_payment_id, billing_payment.reference_id, now_utc(), db)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")


@router.get("/reports/reservations", response_model=ReservationReport, tags=["reports"])
async def report_reservations(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db)) -> ReservationReport:
    """Open deposit reservations: what is held and what is still owed.

    Lapsed reservations are swept first so the report reflects the current book.
    """
    if await release_stale_reservations(db, context.membership.company_id):
        await db.commit()
    orders = (await db.execute(select(Order).where(Order.store_id == context.store.id, Order.status == "pending_pickup").options(selectinload(Order.payments)).order_by(Order.pickup_at.asc().nulls_last(), Order.created_at.asc()))).scalars().unique().all()
    now = now_utc()
    rows: list[ReservationReportRow] = []
    deposits_held = Decimal("0.00")
    balances_due = Decimal("0.00")
    overdue_count = 0
    for order in orders:
        paid = sum((payment.amount for payment in order.payments if payment.status == "paid"), Decimal("0.00"))
        due = (order.total - paid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if due < 0:
            due = Decimal("0.00")
        deposits_held += paid
        balances_due += due
        overdue = bool(order.reservation_expires_at and order.reservation_expires_at < now)
        overdue_count += 1 if overdue else 0
        rows.append(ReservationReportRow(order_id=order.id, order_number=order.order_number, customer_name=order.customer_name, currency_code=order.currency_code, total=order.total, deposit=order.deposit, amount_paid=paid, balance_due=due, pickup_at=order.pickup_at, reservation_expires_at=order.reservation_expires_at, overdue=overdue, created_at=order.created_at))
    return ReservationReport(
        generated_at=now,
        open_count=len(rows),
        overdue_count=overdue_count,
        deposits_held=deposits_held.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        balances_due=balances_due.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        rows=rows,
    )


@router.get("/reports/summary", response_model=ReportSummary, tags=["reports"])
async def report_summary(
    context: StoreContext = Depends(get_store_context_read),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> ReportSummary:
    end_date = to_date or now_utc().date()
    start_date = from_date or end_date.replace(day=1)
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from_date must be before to_date")
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    orders_result = await db.execute(select(Order).where(Order.store_id == context.store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at).options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.refunds)))
    orders = orders_result.scalars().unique().all()
    gross = sum((order.subtotal for order in orders), Decimal("0.00"))
    discounts = sum((order.discount for order in orders), Decimal("0.00"))
    tax = sum((order.tax for order in orders), Decimal("0.00"))
    net = sum((order.total for order in orders), Decimal("0.00"))
    daily = defaultdict(lambda: Decimal("0.00"))
    category = defaultdict(lambda: Decimal("0.00"))
    methods = defaultdict(lambda: Decimal("0.00"))
    products: dict[str, dict] = {}
    combos: dict[str, dict] = {}
    items_sold = Decimal("0")
    product_ids = {item.product_id for order in orders for item in order.items}
    product_rows = (await db.execute(select(Product.id, Category.name).outerjoin(Category, Category.id == Product.category_id).where(Product.id.in_(product_ids)))).all() if product_ids else []
    category_names = {product_id: category_name or "Uncategorized" for product_id, category_name in product_rows}
    for order in orders:
        daily[order.created_at.date().isoformat()] += order.total
        for item in order.items:
            # A combo is credited to the combo, not to its lead component, so the
            # product and category breakdowns are not skewed by bundle sales.
            if item.combo_id or item.combo_name:
                combo_row = combos.setdefault(str(item.combo_id or item.combo_name), {"name": item.combo_name or item.product_name, "quantity": 0, "amount": Decimal("0.00")})
                combo_row["quantity"] += item.quantity
                combo_row["amount"] += item.line_total
                items_sold += item.quantity
                continue
            category[category_names.get(item.product_id, "Uncategorized")] += item.line_total
            row = products.setdefault(str(item.product_id), {"name": item.product_name, "quantity": 0, "amount": Decimal("0.00")})
            row["quantity"] += item.quantity
            row["amount"] += item.line_total
            items_sold += item.quantity
        for payment in order.payments:
            if payment.status == "paid":
                methods[payment.provider] += payment.amount
    refund_agg = await db.execute(select(func.coalesce(func.sum(Refund.total), 0), func.count(Refund.id)).where(Refund.store_id == context.store.id, Refund.created_at >= start_at, Refund.created_at < end_at))
    refund_total, refund_count = refund_agg.one()
    refund_total = Decimal(str(refund_total))
    net_after_refunds = (net - refund_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if net > refund_total else Decimal("0.00")
    trade_in_agg = await db.execute(select(func.coalesce(func.sum(TradeIn.assessed_value), 0), func.count(TradeIn.id)).where(TradeIn.store_id == context.store.id, TradeIn.status == "accepted", TradeIn.created_at >= start_at, TradeIn.created_at < end_at))
    trade_in_value, trade_in_count = trade_in_agg.one()
    trade_in_value = Decimal(str(trade_in_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    warranty_agg = await db.execute(select(func.count(WarrantyClaim.id), func.coalesce(func.sum(WarrantyClaim.cost), 0)).where(WarrantyClaim.store_id == context.store.id, WarrantyClaim.claimed_at >= start_at, WarrantyClaim.claimed_at < end_at))
    warranty_claim_count, warranty_claim_cost = warranty_agg.one()
    warranty_claim_cost = Decimal(str(warranty_claim_cost)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Forward-looking run rate from the selected period. Estimates only; the UI
    # presents these separately from actuals.
    days_in_period = (end_date - start_date).days + 1
    average_daily_net = (net_after_refunds / days_in_period).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if days_in_period > 0 else Decimal("0.00")
    projected_next_30_days = (average_daily_net * 30).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    top_products = sorted(({"name": data["name"], "quantity": float(data["quantity"]), "amount": str(data["amount"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))} for data in products.values()), key=lambda row: Decimal(row["amount"]), reverse=True)[:10]
    top_combos = sorted(({"name": data["name"], "quantity": float(data["quantity"]), "amount": str(data["amount"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))} for data in combos.values()), key=lambda row: Decimal(row["amount"]), reverse=True)[:10]
    transaction_rows: list[ReportTransactionRead] = []
    for order in sorted(orders, key=lambda row: row.created_at, reverse=True):
        paid_providers = {payment.provider for payment in order.payments if payment.status == "paid"}
        method = paid_providers.pop() if len(paid_providers) == 1 else ("mixed" if paid_providers else None)
        refunded = sum((refund.total for refund in order.refunds), Decimal("0.00")) if order.refunds else Decimal("0.00")
        transaction_rows.append(ReportTransactionRead(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            customer_name=order.customer_name,
            currency_code=order.currency_code,
            subtotal=order.subtotal,
            discount=order.discount,
            tax=order.tax,
            tip=order.tip,
            total=order.total,
            refunded_amount=refunded,
            items_count=len(order.items),
            units_count=sum((item.quantity for item in order.items), 0),
            payment_method=method,
            created_at=order.created_at,
        ))
    return ReportSummary(
        from_date=start_date,
        to_date=end_date,
        gross_sales=gross,
        net_sales=net,
        tax=tax,
        discounts=discounts,
        transactions=len(orders),
        refunds=refund_total,
        average_order=(net / len(orders)).quantize(Decimal("0.01")) if orders else Decimal("0.00"),
        items_sold=items_sold,
        refunds_count=int(refund_count),
        net_after_refunds=net_after_refunds,
        trade_in_value=trade_in_value,
        trade_in_count=int(trade_in_count),
        warranty_claim_count=int(warranty_claim_count),
        warranty_claim_cost=warranty_claim_cost,
        days_in_period=days_in_period,
        average_daily_net=average_daily_net,
        projected_next_30_days=projected_next_30_days,
        top_products=top_products,
        top_combos=top_combos,
        daily_sales=[{"date": key, "amount": amount} for key, amount in sorted(daily.items())],
        category_sales=[{"category": key, "amount": amount} for key, amount in sorted(category.items(), key=lambda item: item[1], reverse=True)],
        payment_methods=[{"method": key, "amount": amount} for key, amount in sorted(methods.items(), key=lambda item: item[1], reverse=True)],
        transactions_detail=transaction_rows,
    )


@router.get("/reports/margin", response_model=MarginReport, tags=["reports"])
async def report_margin(
    context: StoreContext = Depends(get_store_context_read),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> MarginReport:
    end_date = to_date or now_utc().date()
    start_date = from_date or end_date.replace(day=1)
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from_date must be before to_date")
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    orders = (await db.execute(select(Order).where(Order.store_id == context.store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at).options(selectinload(Order.items)))).scalars().unique().all()
    product_ids = {item.product_id for order in orders for item in order.items}
    variant_ids = {item.variant_id for order in orders for item in order.items if item.variant_id}
    product_costs = {pid: cost for pid, cost in (await db.execute(select(Product.id, Product.cost_price).where(Product.id.in_(product_ids)))).all()} if product_ids else {}
    variant_costs = {vid: cost for vid, cost in (await db.execute(select(ProductVariant.id, ProductVariant.cost_price).where(ProductVariant.id.in_(variant_ids)))).all()} if variant_ids else {}
    rows: dict[str, dict] = {}
    combos: dict[str, dict] = {}
    for order in orders:
        for item in order.items:
            if item.combo_id or item.combo_name:
                # A combo's cost is frozen as the summed component cost on the line.
                combo_entry = combos.setdefault(str(item.combo_id or item.combo_name), {"name": item.combo_name or item.product_name, "quantity": Decimal("0"), "revenue": Decimal("0"), "cost": Decimal("0")})
                combo_entry["quantity"] += item.quantity
                combo_entry["revenue"] += item.line_total
                if item.cost_price is not None:
                    combo_entry["cost"] += item.cost_price * item.quantity
                continue
            entry = rows.setdefault(str(item.product_id), {"name": item.product_name, "sku": item.sku, "quantity": Decimal("0"), "revenue": Decimal("0"), "cost": Decimal("0")})
            entry["quantity"] += item.quantity
            entry["revenue"] += item.line_total
            if item.cost_price is not None:
                # Cost frozen at fulfillment — historical margin is immutable.
                entry["cost"] += item.cost_price * item.quantity
                continue
            serials = list(item.serials or [])
            serial_costs = [serial.cost_price for serial in serials if serial.cost_price is not None]
            if serials and len(serial_costs) == len(serials):
                entry["cost"] += sum(serial_costs, Decimal("0"))
            else:
                unit_cost = variant_costs.get(item.variant_id) if item.variant_id else None
                if unit_cost is None:
                    unit_cost = product_costs.get(item.product_id)
                entry["cost"] += (unit_cost or Decimal("0")) * item.quantity

    def margin_percent(margin: Decimal, revenue: Decimal) -> float:
        return float((margin / revenue * Decimal("100")).quantize(Decimal("0.01"))) if revenue > 0 else 0.0

    total_revenue = sum((entry["revenue"] for entry in rows.values()), Decimal("0")) + sum((entry["revenue"] for entry in combos.values()), Decimal("0"))
    total_cost = sum((entry["cost"] for entry in rows.values()), Decimal("0")) + sum((entry["cost"] for entry in combos.values()), Decimal("0"))
    total_margin = total_revenue - total_cost
    report_rows = []
    for product_id, entry in rows.items():
        margin = entry["revenue"] - entry["cost"]
        report_rows.append(MarginReportRow(product_id=UUID(product_id), product_name=entry["name"], sku=entry["sku"], quantity=float(entry["quantity"]), revenue=entry["revenue"].quantize(Decimal("0.01")), cost=entry["cost"].quantize(Decimal("0.01")), margin=margin.quantize(Decimal("0.01")), margin_percent=margin_percent(margin, entry["revenue"])))
    report_rows.sort(key=lambda row: row.margin, reverse=True)
    combo_rows = []
    for key, entry in combos.items():
        margin = entry["revenue"] - entry["cost"]
        try:
            combo_uuid = UUID(key)
        except ValueError:
            combo_uuid = None
        combo_rows.append(ComboMarginRow(combo_id=combo_uuid, combo_name=entry["name"], quantity=float(entry["quantity"]), revenue=entry["revenue"].quantize(Decimal("0.01")), cost=entry["cost"].quantize(Decimal("0.01")), margin=margin.quantize(Decimal("0.01")), margin_percent=margin_percent(margin, entry["revenue"])))
    combo_rows.sort(key=lambda row: row.margin, reverse=True)
    return MarginReport(from_date=start_date, to_date=end_date, currency_code=context.store.currency_code, revenue=total_revenue.quantize(Decimal("0.01")), cost=total_cost.quantize(Decimal("0.01")), margin=total_margin.quantize(Decimal("0.01")), margin_percent=margin_percent(total_margin, total_revenue), rows=report_rows, combos=combo_rows)


@router.get("/reports/condition", response_model=ConditionReport, tags=["reports"])
async def report_condition(
    context: StoreContext = Depends(get_store_context_read),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
) -> ConditionReport:
    """Condition breakdown for used / refurbished stock.

    Combines the margin of graded sales with a view of what is on hand by grade,
    the battery-health mix, and per-supplier outcomes.
    """
    end_date = to_date or now_utc().date()
    start_date = from_date or end_date.replace(day=1)
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from_date must be before to_date")
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    orders = (await db.execute(select(Order).where(Order.store_id == context.store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at).options(selectinload(Order.items)))).scalars().unique().all()
    product_ids = {item.product_id for order in orders for item in order.items}
    variant_ids = {item.variant_id for order in orders for item in order.items if item.variant_id}
    product_costs = {pid: cost for pid, cost in (await db.execute(select(Product.id, Product.cost_price).where(Product.id.in_(product_ids)))).all()} if product_ids else {}
    variant_costs = {vid: cost for vid, cost in (await db.execute(select(ProductVariant.id, ProductVariant.cost_price).where(ProductVariant.id.in_(variant_ids)))).all()} if variant_ids else {}
    graded: dict[str | None, dict] = {}
    for order in orders:
        for item in order.items:
            entry = graded.setdefault(item.condition_grade, {"quantity": Decimal("0"), "revenue": Decimal("0"), "cost": Decimal("0")})
            entry["quantity"] += item.quantity
            entry["revenue"] += item.line_total
            if item.cost_price is not None:
                # Cost frozen at fulfillment — historical margin is immutable.
                entry["cost"] += item.cost_price * item.quantity
                continue
            serial_costs = [serial.cost_price for serial in (item.serials or []) if serial.cost_price is not None]
            if serial_costs and len(serial_costs) == len(item.serials or []):
                entry["cost"] += sum(serial_costs, Decimal("0"))
            else:
                unit_cost = variant_costs.get(item.variant_id) if item.variant_id else None
                if unit_cost is None:
                    unit_cost = product_costs.get(item.product_id)
                entry["cost"] += (unit_cost or Decimal("0")) * item.quantity

    def grade_margin_percent(margin: Decimal, revenue: Decimal) -> float:
        return float((margin / revenue * Decimal("100")).quantize(Decimal("0.01"))) if revenue > 0 else 0.0

    by_grade: list[ConditionGradeMarginRow] = []
    for grade, entry in graded.items():
        margin = entry["revenue"] - entry["cost"]
        by_grade.append(ConditionGradeMarginRow(condition_grade=grade, quantity=float(entry["quantity"]), revenue=entry["revenue"].quantize(Decimal("0.01")), cost=entry["cost"].quantize(Decimal("0.01")), margin=margin.quantize(Decimal("0.01")), margin_percent=grade_margin_percent(margin, entry["revenue"])))
    by_grade.sort(key=lambda row: row.margin, reverse=True)

    serials = (await db.execute(select(ProductSerial).where(ProductSerial.store_id == context.store.id))).scalars().all()
    on_hand: dict[str | None, dict] = {}
    supplier_stats: dict[UUID | None, dict] = {}
    battery_counts = {"unknown": 0, "below_80": 0, "80_to_89": 0, "90_to_100": 0}
    for serial in serials:
        stats = supplier_stats.setdefault(serial.supplier_id, {"units": 0, "in_stock": 0, "sold": 0, "returned": 0, "defective": 0})
        stats["units"] += 1
        if serial.status in stats:
            stats[serial.status] += 1
        if serial.status != "in_stock":
            continue
        row = on_hand.setdefault(serial.condition_grade, {"units": 0, "battery_total": 0, "battery_count": 0})
        row["units"] += 1
        if serial.battery_health is None:
            battery_counts["unknown"] += 1
        else:
            row["battery_total"] += serial.battery_health
            row["battery_count"] += 1
            if serial.battery_health < 80:
                battery_counts["below_80"] += 1
            elif serial.battery_health < 90:
                battery_counts["80_to_89"] += 1
            else:
                battery_counts["90_to_100"] += 1

    on_hand_rows = [ConditionOnHandRow(condition_grade=grade, units=row["units"], avg_battery_health=(row["battery_total"] / row["battery_count"]) if row["battery_count"] else None) for grade, row in on_hand.items()]
    on_hand_rows.sort(key=lambda row: row.units, reverse=True)

    supplier_names = await supplier_name_map(db, set(supplier_stats.keys()))
    supplier_rows = [ConditionSupplierRow(supplier_id=supplier_id, supplier_name=supplier_names.get(supplier_id) if supplier_id else None, **stats) for supplier_id, stats in supplier_stats.items()]
    supplier_rows.sort(key=lambda row: row.units, reverse=True)

    total_revenue = sum((row.revenue for row in by_grade), Decimal("0"))
    total_cost = sum((row.cost for row in by_grade), Decimal("0"))
    total_margin = total_revenue - total_cost
    return ConditionReport(
        from_date=start_date,
        to_date=end_date,
        currency_code=context.store.currency_code,
        revenue=total_revenue.quantize(Decimal("0.01")),
        cost=total_cost.quantize(Decimal("0.01")),
        margin=total_margin.quantize(Decimal("0.01")),
        margin_percent=grade_margin_percent(total_margin, total_revenue),
        by_grade=by_grade,
        on_hand_by_grade=on_hand_rows,
        battery=[
            ConditionBatteryBucket(label="Unknown", count=battery_counts["unknown"]),
            ConditionBatteryBucket(label="Below 80%", count=battery_counts["below_80"]),
            ConditionBatteryBucket(label="80-89%", count=battery_counts["80_to_89"]),
            ConditionBatteryBucket(label="90-100%", count=battery_counts["90_to_100"]),
        ],
        suppliers=supplier_rows,
    )


@router.get("/reports/consolidated", response_model=ConsolidatedReportRead, tags=["reports"])
async def consolidated_report(
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    store_ids: list[UUID] | None = Query(default=None),
) -> ConsolidatedReportRead:
    if membership.role not in {"owner", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners and managers can view consolidated reports")
    await require_plan_feature(db, membership.company_id, "advanced_reports")
    end_date = to_date or now_utc().date()
    start_date = from_date or end_date.replace(day=1)
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="from_date must be before to_date")
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    store_query = select(Store).where(Store.company_id == membership.company_id, Store.is_active.is_(True))
    if membership.role != "owner":
        store_query = store_query.join(MembershipStore, MembershipStore.store_id == Store.id).where(MembershipStore.membership_id == membership.id)
    stores = (await db.execute(store_query.order_by(Store.created_at))).scalars().unique().all()
    if not stores:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active stores to report on")
    if store_ids:
        allowed_ids = {store.id for store in stores}
        requested = {store_id for store_id in store_ids}
        if not requested.issubset(allowed_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more selected stores are not available to report on")
        stores = [store for store in stores if store.id in requested]
    if not stores:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active stores match the selected report scope")
    company = await get_company(db, membership.company_id)
    base_code = (company.default_currency_code or "USD").upper()
    base_currency = await get_currency(db, base_code)
    store_scope = [store.id for store in stores]
    store_names = {store.id: store.name for store in stores}
    quantum = Decimal("1") if base_currency.decimal_places == 0 else Decimal("1") / (Decimal("10") ** base_currency.decimal_places)
    rate_cache: dict[tuple[str, str], Decimal] = {}

    async def to_base(amount: Decimal, currency_code: str, at: datetime) -> Decimal:
        code = (currency_code or base_code).upper()
        if code == base_code:
            return amount
        key = (code, as_utc(at).date().isoformat())
        rate = rate_cache.get(key)
        if rate is None:
            rate = await get_exchange_rate(db, membership.company_id, code, base_code, at)
            rate_cache[key] = rate
        return (amount * rate).quantize(quantum, rounding=ROUND_HALF_UP)

    orders_result = await db.execute(
        select(Order)
        .where(Order.store_id.in_(store_scope), Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at)
        .options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.refunds))
    )
    orders = orders_result.scalars().unique().all()
    gross = Decimal("0.00")
    discounts = Decimal("0.00")
    tax = Decimal("0.00")
    net = Decimal("0.00")
    daily = defaultdict(lambda: Decimal("0.00"))
    category = defaultdict(lambda: Decimal("0.00"))
    methods = defaultdict(lambda: Decimal("0.00"))
    products: dict[str, dict] = {}
    items_sold = Decimal("0")
    per_store: dict[UUID, dict] = {store.id: {"transactions": 0, "net_sales": Decimal("0.00"), "gross_sales": Decimal("0.00"), "items_sold": Decimal("0")} for store in stores}
    product_ids = {item.product_id for order in orders for item in order.items}
    product_rows = (await db.execute(select(Product.id, Category.name).outerjoin(Category, Category.id == Product.category_id).where(Product.id.in_(product_ids)))).all() if product_ids else []
    category_names = {product_id: category_name or "Uncategorized" for product_id, category_name in product_rows}
    transaction_rows: list[ReportTransactionRead] = []
    for order in orders:
        order_base = {field: await to_base(getattr(order, field), order.currency_code, order.created_at) for field in ("subtotal", "discount", "tax", "tip", "total")}
        daily[order.created_at.date().isoformat()] += order_base["total"]
        gross += order_base["subtotal"]
        discounts += order_base["discount"]
        tax += order_base["tax"]
        net += order_base["total"]
        stats = per_store[order.store_id]
        stats["transactions"] += 1
        stats["net_sales"] += order_base["total"]
        stats["gross_sales"] += order_base["subtotal"]
        for item in order.items:
            converted = await to_base(item.line_total, order.currency_code, order.created_at)
            category[category_names.get(item.product_id, "Uncategorized")] += converted
            row = products.setdefault(str(item.product_id), {"name": item.product_name, "quantity": 0, "amount": Decimal("0.00")})
            row["quantity"] += item.quantity
            row["amount"] += converted
            items_sold += item.quantity
            stats["items_sold"] += item.quantity
        for payment in order.payments:
            if payment.status == "paid":
                methods[payment.provider] += await to_base(payment.amount, payment.currency_code, order.created_at)
        paid_providers = {payment.provider for payment in order.payments if payment.status == "paid"}
        method = paid_providers.pop() if len(paid_providers) == 1 else ("mixed" if paid_providers else None)
        refunded = Decimal("0.00")
        if order.refunds:
            for refund in order.refunds:
                refunded += await to_base(refund.total, refund.currency_code, refund.created_at)
        transaction_rows.append(ReportTransactionRead(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            customer_name=order.customer_name,
            currency_code=base_code,
            store_id=order.store_id,
            store_name=store_names.get(order.store_id),
            subtotal=order_base["subtotal"],
            discount=order_base["discount"],
            tax=order_base["tax"],
            tip=order_base["tip"],
            total=order_base["total"],
            refunded_amount=refunded,
            items_count=len(order.items),
            units_count=sum((item.quantity for item in order.items), 0),
            payment_method=method,
            created_at=order.created_at,
        ))
    refund_rows = (await db.execute(select(Refund).where(Refund.store_id.in_(store_scope), Refund.created_at >= start_at, Refund.created_at < end_at))).scalars().all()
    refund_total = Decimal("0.00")
    per_store_refunds_total: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0.00"))
    per_store_refunds_count: dict[UUID, int] = defaultdict(int)
    for refund in refund_rows:
        amount = await to_base(refund.total, refund.currency_code, refund.created_at)
        refund_total += amount
        per_store_refunds_total[refund.store_id] += amount
        per_store_refunds_count[refund.store_id] += 1
    refund_count = len(refund_rows)
    net_after_refunds = (net - refund_total).quantize(quantum, rounding=ROUND_HALF_UP) if net > refund_total else Decimal("0.00")
    return ConsolidatedReportRead(
        from_date=start_date,
        to_date=end_date,
        stores_count=len(stores),
        transactions=len(orders),
        items_sold=items_sold,
        gross_sales=gross,
        discounts=discounts,
        tax=tax,
        net_sales=net,
        refunds=refund_total,
        refunds_count=int(refund_count),
        net_after_refunds=net_after_refunds,
        average_order=(net / len(orders)).quantize(quantum, rounding=ROUND_HALF_UP) if orders else Decimal("0.00"),
        base_currency_code=base_code,
        daily_sales=[{"date": key, "amount": amount} for key, amount in sorted(daily.items())],
        payment_methods=[{"method": key, "amount": amount} for key, amount in sorted(methods.items(), key=lambda item: item[1], reverse=True)],
        category_sales=[{"category": key, "amount": amount} for key, amount in sorted(category.items(), key=lambda item: item[1], reverse=True)],
        top_products=[{"name": data["name"], "quantity": float(data["quantity"]), "amount": str(data["amount"].quantize(quantum, rounding=ROUND_HALF_UP))} for data in sorted(products.values(), key=lambda row: row["amount"], reverse=True)[:10]],
        per_store=[
            ConsolidatedStoreReportRead(
                store_id=store.id,
                store_name=store.name,
                transactions=stats["transactions"],
                net_sales=stats["net_sales"].quantize(quantum, rounding=ROUND_HALF_UP),
                gross_sales=stats["gross_sales"].quantize(quantum, rounding=ROUND_HALF_UP),
                items_sold=stats["items_sold"],
                refunds=per_store_refunds_total[store.id].quantize(quantum, rounding=ROUND_HALF_UP),
                refunds_count=int(per_store_refunds_count[store.id]),
                average_order=(stats["net_sales"] / stats["transactions"]).quantize(quantum, rounding=ROUND_HALF_UP) if stats["transactions"] else Decimal("0.00"),
            )
            for store, stats in ((store, per_store[store.id]) for store in stores)
        ],
        transactions_detail=transaction_rows,
    )


def customer_read(customer: Customer) -> CustomerRead:
    return CustomerRead(id=customer.id, name=customer.name, phone=customer.phone, email=customer.email, notes=customer.notes, points=customer.points, is_active=customer.is_active, created_at=customer.created_at)


@router.get("/customers", response_model=list[CustomerRead], tags=["customers"])
async def list_customers(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db), search: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200), include_inactive: bool = False) -> list[CustomerRead]:
    query = select(Customer).where(Customer.company_id == membership.company_id)
    if not include_inactive:
        query = query.where(Customer.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        query = query.where(Customer.name.ilike(like) | Customer.phone.ilike(like) | Customer.email.ilike(like))
    query = query.order_by(Customer.created_at.desc()).limit(limit)
    customers = (await db.execute(query)).scalars().all()
    return [customer_read(customer) for customer in customers]


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED, tags=["customers"])
async def create_customer(payload: CustomerCreateRequest, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> CustomerRead:
    customer = Customer(company_id=membership.company_id, name=payload.name.strip(), phone=(payload.phone or "").strip() or None, email=payload.email, notes=(payload.notes or "").strip() or None)
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer_read(customer)


@router.patch("/customers/{customer_id}", response_model=CustomerRead, tags=["customers"])
async def update_customer(customer_id: UUID, payload: CustomerUpdateRequest, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> CustomerRead:
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id, Customer.company_id == membership.company_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if payload.name is not None:
        customer.name = payload.name.strip()
    if payload.phone is not None:
        customer.phone = (payload.phone or "").strip() or None
    if payload.email is not None:
        customer.email = payload.email
    if payload.notes is not None:
        customer.notes = (payload.notes or "").strip() or None
    if payload.is_active is not None:
        customer.is_active = payload.is_active
    await db.commit()
    await db.refresh(customer)
    return customer_read(customer)


@router.get("/customers/{customer_id}", response_model=CustomerDetailRead, tags=["customers"])
async def get_customer_detail(customer_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> CustomerDetailRead:
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id, Customer.company_id == membership.company_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    paid_scope = select(Order.id).join(Store, Store.id == Order.store_id).where(Store.company_id == membership.company_id, Order.customer_id == customer_id, Order.status == "paid").subquery()
    agg_result = await db.execute(select(func.count(paid_scope.c.id), func.coalesce(func.sum(Order.total), 0)).select_from(Order).join(paid_scope, paid_scope.c.id == Order.id))
    orders_count, total_spent = agg_result.one()
    orders_result = await db.execute(select(Order).join(Store, Store.id == Order.store_id).where(Store.company_id == membership.company_id, Order.customer_id == customer_id).options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.tenders), selectinload(Order.refunds), selectinload(Order.customer)).order_by(Order.created_at.desc()).limit(100))
    orders = orders_result.scalars().unique().all()
    return CustomerDetailRead(customer=customer_read(customer), orders_count=int(orders_count), total_spent=Decimal(str(total_spent)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), orders=[order_read(order) for order in orders])


@router.post("/orders/{order_id}/email-receipt", tags=["orders"])
async def email_order_receipt(order_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "email_receipts")
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status not in {"paid", "refunded"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed orders can be emailed")
    recipient = order.customer.email if order.customer else None
    if not recipient:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This order has no customer email to send to")
    company_name = (await db.execute(select(Company.name).where(Company.id == context.membership.company_id))).scalar_one()
    subject, body = receipt_body(order, context.store, company_name)
    sent = await send_email(recipient, subject, html_to_text(body), html=body)
    if not sent:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send the receipt email")
    return {"ok": True, "email": recipient}


def shift_read(shift: Shift, cashier_name: str | None = None) -> ShiftRead:
    return ShiftRead(id=shift.id, store_id=shift.store_id, user_id=shift.user_id, cashier_name=cashier_name, status=shift.status, opening_float=shift.opening_float, opened_at=shift.opened_at, closed_at=shift.closed_at, sales_total=shift.sales_total, cash_received=shift.cash_received, cash_refunds=shift.cash_refunds, expected_cash=shift.expected_cash, counted_cash=shift.counted_cash, difference=shift.difference, orders_count=shift.orders_count, notes=shift.notes)


async def apply_shift_totals(db: AsyncSession, shift: Shift, end_at: datetime) -> None:
    orders = (await db.execute(select(Order).where(Order.store_id == shift.store_id, Order.created_by == shift.user_id, Order.status == "paid", Order.paid_at >= shift.opened_at, Order.paid_at < end_at).options(selectinload(Order.tenders)))).scalars().unique().all()
    sales_total = sum((order.total for order in orders), Decimal("0.00"))
    cash_received = sum((tender.base_amount for order in orders for tender in order.tenders if tender.kind == "payment" and tender.method == "cash"), Decimal("0.00"))
    refund_agg = await db.execute(select(func.coalesce(func.sum(Refund.total), 0)).where(Refund.store_id == shift.store_id, Refund.created_by == shift.user_id, Refund.method == "cash", Refund.created_at >= shift.opened_at, Refund.created_at < end_at))
    cash_refunds = Decimal(str(refund_agg.scalar_one()))
    expected = shift.opening_float + cash_received - cash_refunds
    shift.sales_total = sales_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shift.cash_received = cash_received.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shift.cash_refunds = cash_refunds.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shift.expected_cash = expected.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shift.orders_count = len(orders)


@router.get("/shifts", response_model=list[ShiftRead], tags=["shifts"])
async def list_shifts(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)) -> list[ShiftRead]:
    result = await db.execute(select(Shift, User.full_name).join(User, User.id == Shift.user_id).where(Shift.store_id == context.store.id).order_by(Shift.opened_at.desc()).limit(limit))
    return [shift_read(shift, cashier_name) for shift, cashier_name in result.all()]


@router.get("/shifts/open", response_model=ShiftRead | None, tags=["shifts"])
async def get_open_shift(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> ShiftRead | None:
    shift = (await db.execute(select(Shift).where(Shift.store_id == context.store.id, Shift.user_id == context.user.id, Shift.status == "open"))).scalar_one_or_none()
    return shift_read(shift, context.user.full_name) if shift else None


@router.post("/shifts/open", response_model=ShiftRead, status_code=status.HTTP_201_CREATED, tags=["shifts"])
async def open_shift(payload: ShiftOpenRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> ShiftRead:
    await require_plan_feature(db, context.membership.company_id, "shift_management")
    existing = (await db.execute(select(Shift).where(Shift.store_id == context.store.id, Shift.user_id == context.user.id, Shift.status == "open"))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A shift is already open for this register")
    shift = Shift(store_id=context.store.id, user_id=context.user.id, status="open", opening_float=payload.opening_float, opened_at=now_utc())
    db.add(shift)
    await db.commit()
    return shift_read(shift, context.user.full_name)


@router.post("/shifts/{shift_id}/close", response_model=ShiftRead, tags=["shifts"])
async def close_shift(shift_id: UUID, payload: ShiftCloseRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> ShiftRead:
    await require_plan_feature(db, context.membership.company_id, "shift_management")
    shift = (await db.execute(select(Shift).where(Shift.id == shift_id, Shift.store_id == context.store.id))).scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    if shift.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shift is already closed")
    if shift.user_id != context.user.id and context.membership.role not in {"owner", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the cashier or a manager can close this shift")
    closed_at = now_utc()
    await apply_shift_totals(db, shift, closed_at)
    shift.closed_at = closed_at
    shift.status = "closed"
    shift.counted_cash = payload.counted_cash
    shift.difference = (payload.counted_cash - shift.expected_cash).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if payload.counted_cash is not None else None
    shift.notes = (payload.notes or "").strip()[:255] or None
    await db.commit()
    # Best-effort closing summary (Z-report); never fail the close if mail is down.
    try:
        if await queue_shift_closed_note(db, context.store, shift, context.user.full_name):
            await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Could not queue the shift-close report")
    return shift_read(shift, context.user.full_name)


async def notify_company_managers(db: AsyncSession, company_id: UUID, store_id: UUID, kind: str, title: str, body: str) -> None:
    users = (await db.execute(select(User.id).join(Membership, Membership.user_id == User.id).where(Membership.company_id == company_id, Membership.status == "active", Membership.role.in_(["owner", "manager"])))).scalars().all()
    for user_id in users:
        db.add(Notification(store_id=store_id, user_id=user_id, type=kind, title=title, body=body))


@router.get("/notifications", response_model=list[NotificationRead], tags=["notifications"])
async def list_notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), unread_only: bool = False, limit: int = Query(default=50, ge=1, le=200)) -> list[NotificationRead]:
    query = select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(limit)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    rows = (await db.execute(query)).scalars().all()
    return [NotificationRead(id=n.id, type=n.type, title=n.title, body=n.body, is_read=n.is_read, created_at=n.created_at) for n in rows]


@router.patch("/notifications/{notification_id}/read", response_model=NotificationRead, tags=["notifications"])
async def mark_notification_read(notification_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> NotificationRead:
    notification = (await db.execute(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id))).scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    await db.commit()
    return NotificationRead(id=notification.id, type=notification.type, title=notification.title, body=notification.body, is_read=notification.is_read, created_at=notification.created_at)


@router.post("/notifications/read-all", tags=["notifications"])
async def mark_all_notifications_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    rows = (await db.execute(select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False)))).scalars().all()
    for notification in rows:
        notification.is_read = True
    await db.commit()
    return {"ok": True}


@router.patch("/auth/me", response_model=UserRead, tags=["auth"])
async def update_me(payload: ProfileUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> UserRead:
    user.full_name = payload.full_name.strip()
    await db.commit()
    return user_read(user)


@router.patch("/auth/me/preferences", response_model=UserRead, tags=["auth"])
async def update_my_preferences(payload: PreferencesUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> UserRead:
    current_prefs = dict(user.preferences or {})
    current_prefs.update(payload.preferences or {})
    user.preferences = current_prefs
    await db.commit()
    return user_read(user)


@router.post("/auth/change-password", tags=["auth"])
async def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), session_id: UUID = Depends(get_current_session_id), db: AsyncSession = Depends(get_db)) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    # Changing a password ends every other sign-in; this device stays signed in.
    await revoke_user_sessions(db, user.id, keep_session_id=session_id)
    await db.commit()
    # Best-effort security notice; never fail the change if mail is down.
    try:
        await send_password_changed_email(user.email, user.full_name)
    except Exception:
        pass
    return {"ok": True}


async def log_audit(db: AsyncSession, membership: Membership, store_id: UUID | None, action: str, entity_type: str, entity_id: UUID | None = None, details: dict | None = None, user: User | None = None) -> None:
    actor = user
    db.add(TenantAuditLog(company_id=membership.company_id, store_id=store_id, actor_user_id=actor.id, actor_name=actor.full_name, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


async def _company_name(db: AsyncSession, company_id: UUID) -> str | None:
    company = await db.get(Company, company_id)
    return company.name if company else None


@router.get("/audit-logs", tags=["audit"])
async def list_audit_logs(membership: Membership = Depends(require_roles("owner", "manager")), db: AsyncSession = Depends(get_db), limit: int = Query(default=100, ge=1, le=300)) -> list[dict]:
    rows = (await db.execute(select(TenantAuditLog).where(TenantAuditLog.company_id == membership.company_id).order_by(TenantAuditLog.created_at.desc()).limit(limit))).scalars().all()
    return [{"id": str(row.id), "action": row.action, "entity_type": row.entity_type, "entity_id": str(row.entity_id) if row.entity_id else None, "actor": row.actor_name, "details": row.details or {}, "created_at": row.created_at.isoformat()} for row in rows]


@router.post("/customers/{customer_id}/redeem", tags=["customers"])
async def redeem_customer_points(customer_id: UUID, points: int, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "loyalty")
    if points < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="points must be at least 1")
    rate = Decimal(dict(context.store.preferences or {}).get("loyalty_pts_per_usd", 1))
    if rate <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loyalty is not enabled for this store")
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id, Customer.company_id == context.membership.company_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.points < points:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Customer only has {int(customer.points)} points")
    value = (Decimal(points) / rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    customer.points = customer.points - points
    await db.commit()
    return {"points_used": points, "discount_value": str(value), "points_left": int(customer.points)}


@router.get("/reports/gdt-csv", tags=["reports"])
async def export_gdt_csv(context: StoreContext = Depends(get_store_context_read), db: AsyncSession = Depends(get_db), from_date: date | None = Query(default=None), to_date: date | None = Query(default=None)):
    await require_plan_feature(db, context.membership.company_id, "advanced_reports")
    end_date = to_date or now_utc().date()
    start_date = from_date or end_date.replace(day=1)
    start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    orders = (await db.execute(select(Order).where(Order.store_id == context.store.id, Order.status == "paid", Order.created_at >= start_at, Order.created_at < end_at).options(selectinload(Order.customer)).order_by(Order.created_at))).scalars().unique().all()
    company_tax_id = (await db.execute(select(Company.tax_id).where(Company.id == context.membership.company_id))).scalar_one_or_none() or ""
    lines = ["document_number,date,customer,tax_amount,total_amount,currency,tax_id"]
    for order in orders:
        customer = (order.customer.name if order.customer else (order.customer_name or "Walk-in")).replace('"', "'")
        lines.append(f'"{order.order_number}",{order.created_at.date().isoformat()},"{customer}",{order.tax},{order.total},{order.currency_code},"{company_tax_id}"')
    return Response(content="\n".join(lines), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=gdt-invoices.csv"})


@router.get("/suppliers", tags=["purchases"])
async def list_suppliers(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(Supplier).where(Supplier.company_id == membership.company_id).order_by(Supplier.name))).scalars().all()
    return [{"id": str(row.id), "name": row.name, "contact_name": row.contact_name, "phone": row.phone, "email": row.email, "is_active": row.is_active} for row in rows]


@router.post("/suppliers", status_code=status.HTTP_201_CREATED, tags=["purchases"])
async def create_supplier(payload: dict, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, membership.company_id, "purchasing")
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    row = Supplier(company_id=membership.company_id, name=name, contact_name=(payload.get("contact_name") or "").strip() or None, phone=(payload.get("phone") or "").strip() or None, email=(payload.get("email") or "").strip() or None)
    db.add(row)
    await db.commit()
    return {"id": str(row.id), "name": row.name, "contact_name": row.contact_name, "phone": row.phone, "email": row.email, "is_active": row.is_active}


def supplier_price_read(row: SupplierPrice, supplier_name: str | None = None) -> SupplierPriceRead:
    read = SupplierPriceRead.model_validate(row)
    read.supplier_name = supplier_name
    return read


async def load_supplier_prices(db: AsyncSession, company_id: UUID, product_id: UUID) -> list[SupplierPriceRead]:
    rows = (
        await db.execute(
            select(SupplierPrice, Supplier.name)
            .outerjoin(Supplier, Supplier.id == SupplierPrice.supplier_id)
            .where(SupplierPrice.company_id == company_id, SupplierPrice.product_id == product_id)
            .order_by(SupplierPrice.is_preferred.desc(), Supplier.name)
        )
    ).all()
    return [supplier_price_read(row, name) for row, name in rows]


@router.get("/products/{product_id}/supplier-prices", response_model=list[SupplierPriceRead], tags=["purchases"])
async def list_product_supplier_prices(product_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> list[SupplierPriceRead]:
    """Supplier cost quotes for one product, one row per variant/supplier."""
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return await load_supplier_prices(db, membership.company_id, product.id)


@router.put("/products/{product_id}/supplier-prices", response_model=list[SupplierPriceRead], tags=["purchases"])
async def set_product_supplier_prices(product_id: UUID, payload: SupplierPricesSetRequest, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> list[SupplierPriceRead]:
    """Replace the supplier quotes for a product.

    The payload is authoritative: any stored row whose target is absent is
    removed. A product with variants is priced per variant; a product without
    variants is priced at product level (``variant_id`` null). This is how the
    same specification bought from several suppliers is compared without
    duplicating the variant.
    """
    await require_plan_feature(db, membership.company_id, "purchasing")
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    variant_ids = {row.id for row in (await db.execute(select(ProductVariant).where(ProductVariant.product_id == product.id))).scalars().all()}
    supplier_ids = {item.supplier_id for item in payload.prices}
    if supplier_ids:
        found = set((await db.execute(select(Supplier.id).where(Supplier.company_id == membership.company_id, Supplier.id.in_(supplier_ids)))).scalars().all())
        missing = supplier_ids - found
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown supplier: {missing.pop()}")
    seen: set[tuple[UUID, UUID | None]] = set()
    preferred_targets: set[UUID | None] = set()
    for item in payload.prices:
        if item.variant_id is not None and item.variant_id not in variant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant does not belong to this product")
        if item.variant_id is None and variant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This product has variants; set variant_id on every supplier price")
        target = (item.supplier_id, item.variant_id)
        if target in seen:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate supplier price for the same target")
        seen.add(target)
        if item.is_preferred:
            if item.variant_id in preferred_targets:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only one preferred supplier is allowed per variant")
            preferred_targets.add(item.variant_id)
    existing = (await db.execute(select(SupplierPrice).where(SupplierPrice.company_id == membership.company_id, SupplierPrice.product_id == product.id))).scalars().all()
    existing_by_target = {(row.supplier_id, row.variant_id): row for row in existing}
    kept: set[tuple[UUID, UUID | None]] = set()
    for item in payload.prices:
        row = existing_by_target.get((item.supplier_id, item.variant_id))
        if row is None:
            row = SupplierPrice(company_id=membership.company_id, supplier_id=item.supplier_id, product_id=product.id, variant_id=item.variant_id)
            db.add(row)
        row.unit_cost = item.unit_cost
        row.currency_code = item.currency_code.upper() if item.currency_code else None
        row.supplier_sku = item.supplier_sku.strip() if item.supplier_sku else None
        row.lead_time_days = item.lead_time_days
        row.min_order_qty = item.min_order_qty
        row.is_preferred = item.is_preferred
        row.note = item.note.strip() if item.note else None
        kept.add((item.supplier_id, item.variant_id))
    for target, row in existing_by_target.items():
        if target not in kept:
            await db.delete(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate supplier price") from None
    return await load_supplier_prices(db, membership.company_id, product.id)


@router.get("/purchases", tags=["purchases"])
async def list_purchases(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=200)) -> list[dict]:
    result = await db.execute(select(PurchaseOrder, Supplier.name).outerjoin(Supplier, Supplier.id == PurchaseOrder.supplier_id).where(PurchaseOrder.store_id == context.store.id).order_by(PurchaseOrder.created_at.desc()).limit(limit))
    rows = []
    for po, supplier_name in result.all():
        rows.append({"id": str(po.id), "po_number": po.po_number, "status": po.status, "supplier": supplier_name, "note": po.note, "items": po.items or [], "created_at": po.created_at.isoformat(), "ordered_at": po.ordered_at.isoformat() if po.ordered_at else None, "received_at": po.received_at.isoformat() if po.received_at else None})
    return rows


@router.post("/purchases", status_code=status.HTTP_201_CREATED, tags=["purchases"])
async def create_purchase(payload: dict, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "purchasing")
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one item is required")
    product_ids = [UUID(item["product_id"]) for item in items]
    products = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))).scalars().all()
    by_id = {product.id: product for product in products}
    variant_rows = (await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(list(by_id))))).scalars().all() if by_id else []
    variants_by_id = {variant.id: variant for variant in variant_rows}
    variants_by_product: dict[UUID, list[ProductVariant]] = defaultdict(list)
    for variant in variant_rows:
        variants_by_product[variant.product_id].append(variant)
    snapshot = []
    for item in items:
        product = by_id.get(UUID(item["product_id"]))
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        qty = int(item.get("quantity", 0))
        if qty <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="quantity must be positive")
        raw_variant_id = item.get("variant_id")
        variant = None
        if raw_variant_id not in (None, ""):
            variant = variants_by_id.get(UUID(str(raw_variant_id)))
            if not variant or variant.product_id != product.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variant does not belong to this product")
        elif variants_by_product.get(product.id):
            # Mirrors stock receiving: a product sold in variants must be ordered by variant.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Choose a variant for {product.name}")
        raw_unit_cost = item.get("unit_cost")
        unit_cost = Decimal(str(raw_unit_cost)) if raw_unit_cost not in (None, "") else None
        snapshot.append({"product_id": str(product.id), "product_name": product.name, "sku": product.sku, "variant_id": str(variant.id) if variant else None, "variant_name": variant.name if variant else None, "quantity": qty, "unit_cost": str(unit_cost) if unit_cost is not None else None})
    po = PurchaseOrder(company_id=context.membership.company_id, store_id=context.store.id, supplier_id=payload.get("supplier_id"), po_number=await next_document_number(db, store_id=context.store.id, scope="purchase_order", prefix="PO"), status="ordered", note=(payload.get("note") or "").strip()[:255] or None, items=snapshot, created_by=context.user.id, ordered_at=now_utc())
    db.add(po)
    await db.commit()
    return {"id": str(po.id), "po_number": po.po_number, "status": po.status, "items": snapshot}


@router.post("/purchases/{purchase_id}/receive", response_model=None, tags=["purchases"])
async def receive_purchase(purchase_id: UUID, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "purchasing")
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == purchase_id, PurchaseOrder.store_id == context.store.id))).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status != "ordered":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only ordered purchase orders can be received")
    items = po.items or []
    product_ids = [UUID(item["product_id"]) for item in items]
    products = {product.id: product for product in (await db.execute(select(Product).where(Product.id.in_(product_ids)))).scalars().all()} if product_ids else {}
    for item in items:
        product_id = UUID(item["product_id"])
        product = products.get(product_id)
        if product is not None and product.track_serials:
            # A PO line has no serial numbers, so receiving here would break the
            # "one serial per unit" invariant. Send the operator to Inventory.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{product.name} tracks serials; receive it from Stock so each unit gets a serial")
        raw_variant_id = item.get("variant_id")
        variant_id = UUID(str(raw_variant_id)) if raw_variant_id else None
        quantity = int(item["quantity"])
        raw_unit_cost = item.get("unit_cost")
        unit_cost = Decimal(str(raw_unit_cost)) if raw_unit_cost not in (None, "", "0", "0.00") else None
        if variant_id:
            balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id == variant_id).with_for_update())).scalar_one_or_none()
            if not balance:
                balance = VariantInventoryBalance(store_id=context.store.id, variant_id=variant_id, on_hand=0, reorder_point=10)
                db.add(balance)
                await db.flush()
            balance.on_hand += quantity
            db.add(StockMovement(store_id=context.store.id, product_id=product_id, variant_id=variant_id, quantity=quantity, movement_type="purchase", reason="received_po", reference_id=po.po_number, unit_cost=unit_cost, created_by=context.user.id))
        else:
            balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product_id).with_for_update())).scalar_one_or_none()
            if not balance:
                balance = InventoryBalance(store_id=context.store.id, product_id=product_id, on_hand=0, reorder_point=10)
                db.add(balance)
                await db.flush()
            balance.on_hand += quantity
            db.add(StockMovement(store_id=context.store.id, product_id=product_id, quantity=quantity, movement_type="purchase", reason="received_po", reference_id=po.po_number, unit_cost=unit_cost, created_by=context.user.id))
    po.status = "received"
    po.received_at = now_utc()
    await db.commit()
    return {"id": str(po.id), "po_number": po.po_number, "status": po.status}


@router.get("/products/export.csv", include_in_schema=False, tags=["catalog"])
async def export_products_csv(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)):
    products = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.is_active.is_(True)).order_by(Product.name))).scalars().all()
    product_ids = [product.id for product in products]
    balances = {b.product_id: b for b in (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id))).scalars().all()}
    variants_by_product: dict[UUID, list[ProductVariant]] = {}
    variant_balances: dict[UUID, VariantInventoryBalance] = {}
    if product_ids:
        variant_rows = (await db.execute(select(ProductVariant).where(ProductVariant.product_id.in_(product_ids)).order_by(ProductVariant.position, ProductVariant.name))).scalars().all()
        variant_ids = [variant.id for variant in variant_rows]
        variant_balances = {b.variant_id: b for b in (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id.in_(variant_ids)))).scalars().all()} if variant_ids else {}
        for variant in variant_rows:
            variants_by_product.setdefault(variant.product_id, []).append(variant)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["sku", "name", "price", "cost_price", "barcode", "brand", "unit", "stock", "reorder_point", "variants"])
    for product in products:
        balance = balances.get(product.id)
        product_variants = variants_by_product.get(product.id, [])
        variants_payload = json.dumps([{"sku": variant.sku, "name": variant.name, "price": str(variant.price) if variant.price is not None else None, "on_hand": float(variant_balances.get(variant.id).on_hand) if variant_balances.get(variant.id) else 0} for variant in product_variants]) if product_variants else ""
        writer.writerow([product.sku, product.name, str(product.price), str(product.cost_price) if product.cost_price is not None else "", product.barcode or "", product.brand or "", product.unit or "each", balance.on_hand if balance else 0, (balance.reorder_point if balance else 10), variants_payload])
    return Response(content=out.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=products.csv"})


@router.post("/products/import", tags=["catalog"])
async def import_products_csv(payload: dict, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    reader = csv.DictReader(io.StringIO(payload.get("csv") or ""))
    created = updated = 0
    for row in reader:
        sku = (row.get("sku") or "").strip()
        name = (row.get("name") or "").strip()
        if not sku or not name:
            continue
        price = Decimal(str(row.get("price") or "0"))
        cost_raw = (row.get("cost_price") or "").strip()
        cost_price = Decimal(cost_raw) if cost_raw else None
        barcode = (row.get("barcode") or "").strip() or None
        brand = (row.get("brand") or "").strip() or None
        unit = (row.get("unit") or "").strip()
        if unit not in PRODUCT_UNITS:
            unit = "each"
        stock = Decimal(str(row.get("stock") or 0))
        reorder = int(float(row.get("reorder_point") or 10))
        product = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.sku == sku))).scalar_one_or_none()
        if product:
            product.name = name
            product.price = price
            if cost_price is not None:
                product.cost_price = cost_price
            if barcode:
                product.barcode = barcode
            if brand:
                product.brand = brand
            product.unit = unit
            updated += 1
        else:
            product = Product(company_id=context.membership.company_id, name=name, sku=sku, price=price, cost_price=cost_price, barcode=barcode, brand=brand, unit=unit)
            db.add(product)
            await db.flush()
            created += 1
        variants_raw = (row.get("variants") or "").strip()
        if variants_raw:
            try:
                variant_specs = json.loads(variants_raw)
            except ValueError:
                variant_specs = []
            for spec in variant_specs if isinstance(variant_specs, list) else []:
                variant_sku = str(spec.get("sku") or "").strip()
                if not variant_sku:
                    continue
                variant = (await db.execute(select(ProductVariant).where(ProductVariant.product_id == product.id, ProductVariant.sku == variant_sku))).scalar_one_or_none()
                raw_price = spec.get("price")
                variant_price = Decimal(str(raw_price)) if raw_price not in (None, "") else None
                variant_name = str(spec.get("name") or variant_sku).strip()
                if variant is None:
                    variant = ProductVariant(product_id=product.id, sku=variant_sku, name=variant_name, price=variant_price)
                    db.add(variant)
                    await db.flush()
                    db.add(VariantInventoryBalance(store_id=context.store.id, variant_id=variant.id, on_hand=Decimal(str(spec.get("on_hand") or 0)), reorder_point=10))
                else:
                    variant.name = variant_name
                    variant.price = variant_price
                    variant_balance = (await db.execute(select(VariantInventoryBalance).where(VariantInventoryBalance.store_id == context.store.id, VariantInventoryBalance.variant_id == variant.id))).scalar_one_or_none()
                    if variant_balance is None:
                        db.add(VariantInventoryBalance(store_id=context.store.id, variant_id=variant.id, on_hand=Decimal(str(spec.get("on_hand") or 0)), reorder_point=10))
                    elif spec.get("on_hand") is not None:
                        variant_balance.on_hand = Decimal(str(spec.get("on_hand") or 0))
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))).scalar_one_or_none()
        if not balance:
            balance = InventoryBalance(store_id=context.store.id, product_id=product.id, on_hand=0, reorder_point=10)
            db.add(balance)
        balance.reorder_point = reorder
        if stock:
            delta = stock - balance.on_hand
            balance.on_hand = stock
            if delta:
                db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=delta, movement_type="manual_adjustment", reason="csv_import", created_by=context.user.id))
    await db.commit()
    return {"created": created, "updated": updated}

@router.post("/notifications/send-summary", tags=["notifications"])
async def send_daily_summary_email(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    owner_emails = (await db.execute(select(User.email).join(Membership, Membership.user_id == User.id).where(Membership.company_id == context.membership.company_id, Membership.status == "active", Membership.role == "owner"))).scalars().all()
    today = now_utc().date()
    subject = f"Daily summary · {context.store.name}"
    body = await daily_summary_body(db, context.store, today)
    sent_any = False
    for email in owner_emails:
        if await send_email(email, subject, html_to_text(body), html=body):
            sent_any = True
    if not sent_any:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send summary email")
    return {"ok": True, "emails": list(owner_emails)}


@router.post("/notifications/send-low-stock", tags=["notifications"])
async def send_low_stock_email(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    owner_emails = (await db.execute(select(User.email).join(Membership, Membership.user_id == User.id).where(Membership.company_id == context.membership.company_id, Membership.status == "active", Membership.role == "owner"))).scalars().all()
    low = await low_stock_items(db, store_id=context.store.id)
    note = await low_stock_body(db, context.store)
    if note is None:
        subject = f"Low stock alert · {context.store.name}"
        body = transactional_email(
            heading="Low stock alert",
            preview="Nothing needs restocking right now.",
            body='<p style="margin:0;">Nothing is at or below its reorder point right now. You are all set.</p>',
            badge="Inventory",
        )
    else:
        subject, body = note
    for email in owner_emails:
        await send_email(email, subject, html_to_text(body), html=body)
    return {"ok": True, "low_stock_items": len(low), "emails": list(owner_emails)}

@router.patch("/customers/{customer_id}/points", tags=["customers"])
async def adjust_customer_points(customer_id: UUID, payload: dict, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    membership = context.membership
    await require_plan_feature(db, membership.company_id, "loyalty")
    try:
        delta = int(payload.get("delta", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delta must be an integer")
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id, Customer.company_id == membership.company_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    policy = await load_approval_policy(db, membership.company_id)
    rule = policy.rules.get("loyalty_adjust")
    amount = Decimal(abs(delta))
    gate = approval_gate(rule, amount) if policy.enabled else "allow"
    if gate == "request":
        is_approver = rule is not None and membership.role in rule.approvers
        if not (is_approver and not (policy.maker_checker and membership.role != "owner")):
            return await _pending_approval_response(db, membership, store_id=context.store.id, action="loyalty_adjust", amount=amount, payload={"customer_id": str(customer.id), "delta": delta}, user=context.user, reason=payload.get("reason"))
    result = await _apply_points_change(db, membership, customer, delta)
    if gate == "review":
        await log_audit(db, membership, context.store.id, "loyalty_adjust_reviewed", "customer", entity_id=customer.id, details={"customer": customer.name, "delta": delta, "mode": "review"}, user=context.user)
        await notify_company_managers(db, membership.company_id, context.store.id, "loyalty_adjust_review", f"Loyalty adjustment flagged: {customer.name}", f"{delta} points by {context.user.full_name}")
        await db.commit()
    return result


@router.patch("/suppliers/{supplier_id}", tags=["purchases"])
async def update_supplier(supplier_id: UUID, payload: dict, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, membership.company_id, "purchasing")
    supplier = (await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.company_id == membership.company_id))).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    if "name" in payload and payload["name"] is not None:
        supplier.name = str(payload["name"]).strip()[:180] or supplier.name
    supplier.contact_name = (str(payload.get("contact_name") or "").strip()[:160]) or None if "contact_name" in payload else supplier.contact_name
    supplier.phone = (str(payload.get("phone") or "").strip()[:40]) or None if "phone" in payload else supplier.phone
    supplier.email = (str(payload.get("email") or "").strip()[:320]) or None if "email" in payload else supplier.email
    if "is_active" in payload:
        supplier.is_active = bool(payload["is_active"])
    await db.commit()
    return {"id": str(supplier.id), "name": supplier.name, "contact_name": supplier.contact_name, "phone": supplier.phone, "email": supplier.email, "is_active": supplier.is_active}


@router.delete("/suppliers/{supplier_id}", tags=["purchases"])
async def delete_supplier(supplier_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, membership.company_id, "purchasing")
    supplier = (await db.execute(select(Supplier).where(Supplier.id == supplier_id, Supplier.company_id == membership.company_id))).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await db.delete(supplier)
    await db.commit()
    return {"ok": True}


@router.post("/purchases/{purchase_id}/cancel", tags=["purchases"])
async def cancel_purchase(purchase_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "purchasing")
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == purchase_id, PurchaseOrder.store_id == context.store.id))).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status != "ordered":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only ordered purchase orders can be cancelled")
    po.status = "cancelled"
    await db.commit()
    return {"id": str(po.id), "po_number": po.po_number, "status": po.status}


@router.delete("/purchases/{purchase_id}", tags=["purchases"])
async def delete_purchase(purchase_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "purchasing")
    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == purchase_id, PurchaseOrder.store_id == context.store.id))).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    if po.status == "received":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Received purchase orders cannot be deleted")
    await db.delete(po)
    await db.commit()
    return {"ok": True}

@router.get("/team/invitations", tags=["team"])
async def list_team_invitations(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(Invitation).where(Invitation.company_id == membership.company_id, Invitation.accepted_at.is_(None)).order_by(Invitation.created_at.desc()))).scalars().all()
    return [{"id": str(inv.id), "email": inv.email, "role": inv.role, "store_ids": inv.store_ids, "status": "invited", "created_at": inv.created_at.isoformat()} for inv in rows]


@router.delete("/team/invitations/{invitation_id}", tags=["team"])
async def delete_team_invitation(invitation_id: UUID, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> dict:
    invitation = (await db.execute(select(Invitation).where(Invitation.id == invitation_id, Invitation.company_id == membership.company_id, Invitation.accepted_at.is_(None)))).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    await db.delete(invitation)
    await db.commit()
    return {"ok": True}

@router.post("/team/invitations/{invitation_id}/accept-by-owner", status_code=status.HTTP_201_CREATED, tags=["team"])
async def accept_invitation_as_owner(invitation_id: UUID, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> dict:
    invitation = (await db.execute(select(Invitation).where(Invitation.id == invitation_id, Invitation.company_id == membership.company_id, Invitation.accepted_at.is_(None)))).scalar_one_or_none()
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    user = (await db.execute(select(User).where(User.email == invitation.email))).scalar_one_or_none()
    if not user:
        temp_password = f"temp-{uuid.uuid4().hex[:10]}"
        user = User(email=invitation.email, full_name=invitation.email.split("@")[0], password_hash=hash_password(temp_password), is_email_verified=True)
        db.add(user)
        await db.flush()
    existing = (await db.execute(select(Membership).where(Membership.company_id == membership.company_id, Membership.user_id == user.id))).scalar_one_or_none()
    if not existing:
        existing = Membership(company_id=membership.company_id, user_id=user.id, role=invitation.role, status="active")
        db.add(existing)
        await db.flush()
    invitation.accepted_at = now_utc()
    for store_id in invitation.store_ids or []:
        try:
            store_uuid = UUID(store_id)
        except (TypeError, ValueError):
            continue
        link = (await db.execute(select(MembershipStore).where(MembershipStore.membership_id == existing.id, MembershipStore.store_id == store_uuid))).scalar_one_or_none()
        if not link:
            db.add(MembershipStore(membership_id=existing.id, store_id=store_uuid))
    await queue_team_activity(db, membership.company_id, title="Team member added", detail=f"{user.full_name} ({user.email}) was added as {invitation.role}.")
    await db.commit()
    return {"ok": True, "email": user.email, "role": invitation.role}

@router.delete("/products/{product_id}", tags=["catalog"])
async def delete_product(product_id: UUID, membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> dict:
    product = (await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    has_orders = (await db.execute(select(func.count(OrderItem.id)).join(Order, Order.id == OrderItem.order_id).join(Store, Store.id == Order.store_id).where(OrderItem.product_id == product_id, Store.company_id == membership.company_id))).scalar_one()
    if has_orders:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product has order history. Deactivate it instead of deleting.")
    await db.delete(product)
    await db.commit()
    return {"ok": True}


@router.post("/workspace/sample-products/clear", response_model=SampleProductsClearRead, tags=["catalog"])
async def clear_sample_products(membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> SampleProductsClearRead:
    """Remove the seeded demo products from the caller's company.

    An untouched sample is deleted so it leaves the catalogue entirely. A sample
    that was used in a real sale is only deactivated, because order history
    references it and must be preserved.
    """
    samples = (await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.is_sample.is_(True)))).scalars().all()
    deleted = 0
    deactivated = 0
    for product in samples:
        has_orders = (await db.execute(select(func.count(OrderItem.id)).where(OrderItem.product_id == product.id))).scalar_one()
        if has_orders:
            if product.is_active:
                product.is_active = False
                deactivated += 1
        else:
            await db.delete(product)
            deleted += 1
    await db.commit()
    return SampleProductsClearRead(deleted=deleted, deactivated=deactivated)


@router.delete("/customers/{customer_id}", tags=["customers"])
async def delete_customer(customer_id: UUID, membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> dict:
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id, Customer.company_id == membership.company_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    has_orders = (await db.execute(select(func.count(Order.id)).join(Store, Store.id == Order.store_id).where(Order.customer_id == customer_id, Store.company_id == membership.company_id))).scalar_one()
    if has_orders:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer has order history. You can deactivate instead.")
    await db.delete(customer)
    await db.commit()
    return {"ok": True}


def _unsubscribe_page(message: str, *, ok: bool) -> str:
    tone = "#2f7d32" if ok else "#c2564b"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Chmaba email preferences</title></head>"
        "<body style=\"margin:0;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;"
        "background:#fafafd;color:#202128;display:flex;min-height:100vh;align-items:center;justify-content:center\">"
        "<main style=\"max-width:440px;padding:32px;text-align:center\">"
        "<p style=\"font-size:11px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:#92939d;margin:0\">Chmaba</p>"
        f"<h1 style=\"font-size:20px;margin:12px 0 8px\">Email preferences</h1>"
        f"<p style=\"color:{tone};font-weight:600\">{message}</p>"
        "<p style=\"color:#92939d;font-size:12px;margin-top:16px\">You can keep using Chmaba as normal.</p>"
        "</main></body></html>"
    )


@router.get("/email/unsubscribe", tags=["email"], response_class=HTMLResponse)
@router.post("/email/unsubscribe", tags=["email"], response_class=HTMLResponse)
async def unsubscribe_from_email(token: str = Query(default=""), db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    """One-click opt-out target for mailing ``List-Unsubscribe`` links.

    Public and idempotent: a valid token adds the address to the suppression
    list so no further onboarding mail is sent, and returns a small page. An
    invalid token is reported without ever touching the database.
    """
    email = mailing_service.read_unsubscribe_token(token) if token else None
    if email is None:
        return HTMLResponse(_unsubscribe_page("That unsubscribe link is not valid or has expired.", ok=False), status_code=status.HTTP_400_BAD_REQUEST)
    await mailing_service.suppress(db, email, reason="unsubscribed")
    return HTMLResponse(_unsubscribe_page("You will no longer receive onboarding emails from Chmaba.", ok=True))


@router.post("/webhooks/resend", tags=["webhooks"])
async def resend_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Receive Resend delivery events. Public but signature-verified.

    Hard bounces and spam complaints suppress the address so it is never mailed
    again; other events are acknowledged and ignored.
    """
    payload = await request.body()
    settings_map = await mail_service.load_mail_settings(db)
    secret = (settings_map.get("resend_webhook_secret") or "").strip()
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Resend webhooks are not configured")
    if not mail_events.verify_svix_signature(
        secret=secret,
        payload=payload,
        svix_id=request.headers.get("svix-id"),
        svix_timestamp=request.headers.get("svix-timestamp"),
        svix_signature=request.headers.get("svix-signature"),
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
    try:
        body = json.loads(payload or b"{}")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")
    event_type = str(body.get("type") or "")
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    return await mail_events.apply_resend_event(db, event_type, data)

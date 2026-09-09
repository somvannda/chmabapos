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
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.billing import FREE_PLAN_CODE, is_in_force, load_entitlement
from app.config import settings
from app.deps import StoreContext, get_current_membership, get_current_user, get_db, get_store_context, require_roles
from app.email import send_email, send_invitation_email, send_password_reset_email, send_verification_email
from app.models import (
    BillingPayment,
    Category,
    Company,
    CompanyCurrency,
    Currency,
    Customer,
    EmailVerificationToken,
    ExchangeRate,
    HeldOrder,
    InventoryBalance,
    Invitation,
    Membership,
    MembershipStore,
    Notification,
    Order,
    OrderItem,
    OrderTender,
    PasswordResetToken,
    Payment,
    Plan,
    Product,
    PurchaseOrder,
    RecurringSubscription,
    Refund,
    Shift,
    StockMovement,
    Store,
    StoreSequence,
    Supplier,
    TenantAuditLog,
    Subscription,
    User,
    utcnow,
)
from app.schemas import (
    BillingCheckoutRead,
    BillingCheckoutRequest,
    BillingPaymentRead,
    BillingRecurringCheckoutRead,
    BillingRecurringCheckoutRequest,
    BillingRecurringPortalRead,
    BillingScheduleRequest,
    RecurringSubscriptionRead,
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
    CustomerRead,
    CustomerUpdateRequest,
    CutLuyWebhookEvent,
    ExchangeRateCreateRequest,
    ExchangeQuoteRead,
    ExchangeRateRead,
    ExchangeRateUpdateRequest,
    GoogleAuthResponse,
    GoogleSignInRequest,
    HealthResponse,
    HeldItemRead,
    HeldOrderCreateRequest,
    HeldOrderRead,
    InvitationCreateRequest,
    InvitationAcceptRequest,
    InvitationRead,
    InventoryAdjustRequest,
    InventoryRead,
    InventoryRestockRequest,
    LoginRequest,
    MembershipRead,
    MembershipUpdateRequest,
    NotificationRead,
    OrderCreateRequest,
    OrderRead,
    OrderTenderRead,
    OrderTenderRequest,
    PaddleWebhookEvent,
    PaymentRead,
    PlanRead,
    ProductCreateRequest,
    ProductRead,
    ProductUpdateRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    ProfileUpdateRequest,
    PreferencesUpdateRequest,
    ChangePasswordRequest,
    RefundCreateRequest,
    RefundItemRead,
    RefundRead,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ConsolidatedReportRead,
    ConsolidatedStoreReportRead,
    ReportSummary,
    ReportTransactionRead,
    ShiftCloseRequest,
    ShiftOpenRequest,
    ShiftRead,
    StoreCreateRequest,
    StoreRead,
    StoreUpdateRequest,
    StockTransferCreateRequest,
    SubscriptionRead,
    TokenResponse,
    UserRead,
    VerifyEmailRequest,
    WorkspaceRead,
    WorkspaceSetupRequest,
)
from app.security import create_opaque_token, create_token, create_verification_code, hash_opaque_token, hash_password, verify_password
from app.services.billing_lifecycle import enforce_plan_capacity, pause_stores_over_capacity, restore_capacity, revoke_staff_over_capacity
from app.services.cutluy import CutLuyClient, CutLuyError
from app.services.google_auth import GOOGLE_AUTH_URL, exchange_authorization_code, verify_google_id_token
from app.services.orders import complete_order, ensure_transaction_available
from app.services.paddle import PaddleClient, PaddleError, paddle_signature_is_valid
from app.services.platform_config import load_cutluy_settings, load_paddle_settings
from app.services.recurring_paddle import apply_paddle_event, mock_activate

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


def product_read(product: Product, balance: InventoryBalance | None = None) -> ProductRead:
    return ProductRead(
        id=product.id,
        company_id=product.company_id,
        category_id=product.category_id,
        name=product.name,
        sku=product.sku,
        description=product.description,
        image=product.image,
        price=product.price,
        cost_price=product.cost_price,
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
        category=CategoryRead.model_validate(product.category) if product.category else None,
        on_hand=balance.on_hand if balance else 0,
        reorder_point=balance.reorder_point if balance else 10,
    )


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
    if ent.subscription is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ent.denied_reason(action="use this feature"))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"The {ent.plan.name} plan does not include this feature. Upgrade your plan to unlock it.",
    )


_SEQUENCE_MODELS: dict[str, type] = {
    "order": Order,
    "purchase_order": PurchaseOrder,
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


def apply_aba_payway_link(obj: Company | Store, raw_link: str | None) -> str:
    """Set a merchant's ABA PayWay link and its review status.

    Adding or editing the link resets the status to ``pending`` so the platform
    team can manually re-link the merchant's CutLuy store before KHQR checkout
    is enabled. Clearing the link removes the connection entirely.
    """
    cleaned = (raw_link or "").strip() or None
    previous = getattr(obj, "aba_payway_link", None) or None
    changed = cleaned != previous
    obj.aba_payway_link = cleaned
    if not cleaned:
        obj.aba_payway_status = "none"
    elif changed:
        obj.aba_payway_status = "pending"
    return obj.aba_payway_status


async def cutluy_client_for(db: AsyncSession) -> CutLuyClient:
    """Build a CutLuy client using admin-managed platform settings (env fallback)."""
    cfg = await load_cutluy_settings(db)
    return CutLuyClient(mode=cfg["cutluy_mode"] or None, api_url=cfg["cutluy_api_url"] or None, api_key=cfg["cutluy_api_key"] or None)


async def paddle_client_for(db: AsyncSession) -> PaddleClient:
    """Build a Paddle client using admin-managed platform settings (env fallback)."""
    cfg = await load_paddle_settings(db)
    return PaddleClient(
        mode=cfg.get("paddle_mode") or None,
        api_url=cfg.get("paddle_api_url") or None,
        api_key=cfg.get("paddle_api_key") or None,
    )


def recurring_to_subscription_read(row: RecurringSubscription) -> SubscriptionRead:
    """Expose a governing Paddle auto-renew row through the prepaid read shape.

    Keeps the existing ``/billing/subscription`` contract (used by the portal
    and the billing page) working for workspaces on Paddle auto-renew.
    """
    return SubscriptionRead(
        id=row.id,
        company_id=row.company_id,
        plan_code=row.plan_code,
        billing_cycle=row.billing_cycle,
        status="active",
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        scheduled_plan_code=None,
        scheduled_store_ids=None,
        scheduled_member_ids=None,
    )


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
    return WorkspaceRead(
        company=CompanyRead.model_validate(company),
        store=StoreRead.model_validate(store),
        subscription=SubscriptionRead.model_validate(subscription),
        membership_role=membership.role,
        billing_payment=BillingPaymentRead.model_validate(billing_payment).model_dump(mode="json") if billing_payment else None,
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    await db.execute(select(1))
    return HealthResponse(status="ok", service=settings.app_name, version="v1", database="connected")


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    await db.flush()
    code = create_verification_code()
    db.add(EmailVerificationToken(user_id=user.id, token_hash=hash_opaque_token(code), expires_at=now_utc() + timedelta(hours=24)))
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
    await db.execute(
        EmailVerificationToken.__table__.update()
        .where(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
        .values(used_at=now_utc())
    )
    code = create_verification_code()
    db.add(EmailVerificationToken(user_id=user.id, token_hash=hash_opaque_token(code), expires_at=now_utc() + timedelta(hours=24)))
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
    await db.commit()
    await db.refresh(user)
    return user_read(user)


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect")
    if not user.is_email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Confirm your email before signing in")
    ttl_minutes = settings.jwt_remember_ttl_minutes if payload.remember_me else settings.jwt_access_ttl_minutes
    return TokenResponse(access_token=create_token(user.id, ttl_minutes=ttl_minutes), expires_in=ttl_minutes * 60, user=user_read(user))


@router.post("/auth/google", response_model=GoogleAuthResponse, tags=["auth"])
async def google_signin(payload: GoogleSignInRequest, db: AsyncSession = Depends(get_db)) -> GoogleAuthResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    try:
        claims = verify_google_id_token(payload.id_token, settings.google_client_id)
    except Exception:
        logger.exception("Google ID token verification failed during POST /auth/google")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google sign-in failed. Please try again")
    user, is_new_user = await _google_claims_to_user(db, claims)
    await db.commit()
    await db.refresh(user)
    return GoogleAuthResponse(
        access_token=create_token(user.id),
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
async def google_authorize() -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret or not settings.google_redirect_uri:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    state = secrets.token_urlsafe(24)
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
    try:
        token_response = await exchange_authorization_code(
            code, settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri
        )
        claims = verify_google_id_token(token_response["id_token"], settings.google_client_id)
        user, is_new_user = await _google_claims_to_user(db, claims)
        await db.commit()
        await db.refresh(user)
    except HTTPException as exc:
        await db.rollback()
        return redirect_to_login(exc.detail)
    except Exception:
        await db.rollback()
        logger.exception("Google OAuth callback failed after authorization code exchange")
        return redirect_to_login("Google sign-in failed. Please try again")
    access_token = create_token(user.id)
    return redirect_to_login(
        "",
        extra={"access_token": access_token, "is_new_user": "1" if is_new_user else "0"},
    )


@router.post("/auth/request-password-reset", tags=["auth"])
async def request_password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    result = await db.execute(select(User).where(User.email == payload.email.lower(), User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user:
        raw_token = create_opaque_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=hash_opaque_token(raw_token), expires_at=now_utc() + timedelta(minutes=30)))
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
    await db.commit()
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
    company = Company(name=payload.company_name.strip(), country=payload.country, default_currency_code=currency.code)
    db.add(company)
    await db.flush()
    store = Store(company_id=company.id, name=payload.store_name.strip(), address=payload.store_address, phone=payload.store_phone, timezone=payload.timezone, currency_code=currency.code)
    membership = Membership(company_id=company.id, user_id=user.id, role="owner", status="active")
    db.add_all([store, membership])
    await db.flush()
    db.add(MembershipStore(membership_id=membership.id, store_id=store.id))
    db.add(CompanyCurrency(company_id=company.id, currency_code=currency.code, is_enabled=True, is_primary=True))
    subscription = Subscription(company_id=company.id, plan_code=plan.code, billing_cycle=payload.billing_cycle, status="active" if plan.code == "free" else "pending", starts_at=now_utc(), ends_at=None)
    db.add(subscription)
    await db.flush()
    for name in ["Coffee", "Tea", "Bakery", "Cold drinks"]:
        db.add(Category(company_id=company.id, name=name))
    billing_payment = None
    if plan.code != "free":
        billing_cycle = payload.billing_cycle
        cycle_multiplier = {"monthly": 1, "semi_annual": 6, "annual": 12}.get(billing_cycle, 1)
        discount = Decimal("0.00")
        if billing_cycle == "semi_annual":
            discount = Decimal("0.15")
        elif billing_cycle == "annual":
            discount = Decimal("0.20")
        monthly_after_discount = plan.monthly_price * (1 - discount)
        total_amount = (monthly_after_discount * cycle_multiplier).quantize(Decimal("0.01"))
        reference = f"plan-{company.id}-{uuid.uuid4().hex}"
        try:
            provider_payment = await (await cutluy_client_for(db)).create_payment(total_amount, reference, {"type": "subscription", "subscription_id": str(subscription.id), "plan_code": plan.code, "billing_cycle": billing_cycle})
        except CutLuyError as exc:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        billing_payment = BillingPayment(subscription_id=subscription.id, amount=total_amount, currency_code=provider_payment.get("currency", "USD"), external_id=provider_payment.get("id"), reference_id=provider_payment.get("reference_id", reference), status=provider_payment.get("status", "pending"), qr_string=provider_payment.get("qr_string"), checkout_url=provider_payment.get("checkout_url"), provider_metadata=provider_payment.get("metadata"))
        db.add(billing_payment)
    await db.commit()
    await db.refresh(membership)
    await db.refresh(store)
    await db.refresh(subscription)
    return WorkspaceRead(company=CompanyRead.model_validate(company), store=StoreRead.model_validate(store), subscription=SubscriptionRead.model_validate(subscription), membership_role=membership.role, billing_payment=BillingPaymentRead.model_validate(billing_payment).model_dump(mode="json") if billing_payment else None)


@router.get("/workspaces/current", response_model=WorkspaceRead, tags=["workspace"])
async def current_workspace(membership: Membership = Depends(get_current_membership), context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> WorkspaceRead:
    return await workspace_response(db, membership, context.store)


@router.patch("/company", response_model=CompanyRead, tags=["workspace"])
async def update_company(payload: CompanyUpdateRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> CompanyRead:
    company = await get_company(db, membership.company_id)
    if payload.default_currency_code:
        await require_enabled_currency(db, company.id, payload.default_currency_code)
    for field in ("name", "country", "address", "email", "phone", "tax_id", "default_currency_code"):
        value = getattr(payload, field)
        if value is not None:
            if isinstance(value, str) and field in {"name", "country"}:
                setattr(company, field, value.strip())
            elif isinstance(value, str):
                setattr(company, field, value.strip() or None)
            else:
                setattr(company, field, value)
    if "aba_payway_link" in payload.model_fields_set:
        apply_aba_payway_link(company, payload.aba_payway_link)
    await db.commit()
    await db.refresh(company)
    return CompanyRead.model_validate(company)


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
        apply_aba_payway_link(store, payload.aba_payway_link)
    await db.commit()
    await db.refresh(store)
    return StoreRead.model_validate(store)


@router.get("/plans", response_model=list[PlanRead], tags=["billing"])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanRead]:
    result = await db.execute(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.monthly_price))
    return [PlanRead.model_validate(plan) for plan in result.scalars().all()]


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
        query = query.where(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
    if category_id:
        query = query.where(Product.category_id == category_id)
    products = (await db.execute(query)).scalars().all()
    product_ids = [product.id for product in products]
    balances_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids))) if product_ids else None
    balances = {balance.product_id: balance for balance in balances_result.scalars().all()} if balances_result else {}
    return [product_read(product, balances.get(product.id)) for product in products]


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED, tags=["catalog"])
async def create_product(payload: ProductCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> ProductRead:
    await category_for_company(db, payload.category_id, membership.company_id)
    duplicate = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.sku == payload.sku.strip()))
    if duplicate.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")
    product = Product(company_id=membership.company_id, category_id=payload.category_id, name=payload.name.strip(), sku=payload.sku.strip(), description=payload.description, image=payload.image, price=payload.price, cost_price=payload.cost_price)
    db.add(product)
    await db.flush()
    balance = InventoryBalance(store_id=context.store.id, product_id=product.id, on_hand=payload.opening_stock, reorder_point=payload.reorder_point)
    db.add(balance)
    if payload.opening_stock:
        db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=payload.opening_stock, movement_type="opening_balance", reason="product_created", created_by=context.user.id))
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
    for field in ("name", "sku", "price", "cost_price", "category_id", "description", "image", "is_active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(product, field, value.strip() if isinstance(value, str) and field in {"name", "sku"} else value)
    await db.commit()
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id))
    await db.refresh(product)
    return product_read(product, balance_result.scalar_one_or_none())


async def inventory_for_product(db: AsyncSession, store_id: UUID, product: Product) -> InventoryRead:
    result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == store_id, InventoryBalance.product_id == product.id))
    balance = result.scalar_one_or_none()
    on_hand = balance.on_hand if balance else 0
    reorder_point = balance.reorder_point if balance else 10
    state = "out" if on_hand == 0 else "low" if on_hand <= reorder_point else "healthy"
    return InventoryRead(store_id=store_id, product_id=product.id, product_name=product.name, sku=product.sku, price=product.price, on_hand=on_hand, reorder_point=reorder_point, status=state, updated_at=balance.updated_at if balance else product.updated_at)


@router.get("/inventory", response_model=list[InventoryRead], tags=["inventory"])
async def list_inventory(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), low_stock: bool = False) -> list[InventoryRead]:
    products = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.is_active.is_(True)).order_by(Product.name))).scalars().all()
    inventory = [await inventory_for_product(db, context.store.id, product) for product in products]
    return [item for item in inventory if not low_stock or item.status in {"low", "out"}]


@router.patch("/inventory/{product_id}", response_model=InventoryRead, tags=["inventory"])
async def adjust_inventory(product_id: UUID, payload: InventoryAdjustRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> InventoryRead:
    await require_plan_feature(db, membership.company_id, "inventory_management")
    product_result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id, Product.is_active.is_(True)))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id).with_for_update())
    balance = balance_result.scalar_one_or_none()
    if not balance:
        balance = InventoryBalance(store_id=context.store.id, product_id=product.id, on_hand=0, reorder_point=10)
        db.add(balance)
        await db.flush()
    difference = payload.quantity - balance.on_hand
    balance.on_hand = payload.quantity
    if difference:
        db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=difference, movement_type="manual_adjustment", reason=payload.reason, created_by=context.user.id))
    if balance.on_hand <= (balance.reorder_point or 10):
        await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name}", f"Only {balance.on_hand} left (reorder point {balance.reorder_point or 10})")
    await db.commit()
    return await inventory_for_product(db, context.store.id, product)


@router.post("/inventory/{product_id}/restock", response_model=InventoryRead, tags=["inventory"])
async def restock_inventory(product_id: UUID, payload: InventoryRestockRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> InventoryRead:
    await require_plan_feature(db, membership.company_id, "inventory_management")
    product_result = await db.execute(select(Product).where(Product.id == product_id, Product.company_id == membership.company_id, Product.is_active.is_(True)))
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product.id).with_for_update())
    balance = balance_result.scalar_one_or_none()
    if not balance:
        balance = InventoryBalance(store_id=context.store.id, product_id=product.id, on_hand=0, reorder_point=10)
        db.add(balance)
        await db.flush()
    balance.on_hand += payload.quantity
    detail = payload.reason or (f"Received from {payload.supplier}" if payload.supplier else "Stock received")
    db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=payload.quantity, movement_type="restock", reason=detail, reference_id=payload.reference or payload.supplier, created_by=context.user.id))
    if balance.on_hand <= (balance.reorder_point or 10):
        await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name}", f"Only {balance.on_hand} left (reorder point {balance.reorder_point or 10})")
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
    requested = {item.product_id: item for item in payload.items}
    if len(requested) != len(payload.items):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate items in transfer")
    products_result = await db.execute(select(Product).where(Product.company_id == membership.company_id, Product.id.in_(list(requested)), Product.is_active.is_(True)))
    products = {product.id: product for product in products_result.scalars().all()}
    if len(products) != len(requested):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    store_ids = [context.store.id, payload.to_store_id]
    # Lock all affected balances in a consistent order (product, store) to avoid deadlocks
    # between opposite-direction transfers running at the same time.
    balances_result = await db.execute(
        select(InventoryBalance)
        .where(InventoryBalance.store_id.in_(store_ids), InventoryBalance.product_id.in_(list(requested)))
        .order_by(InventoryBalance.product_id, InventoryBalance.store_id)
        .with_for_update()
    )
    balance_map: dict[tuple[UUID, UUID], InventoryBalance] = {}
    for balance in balances_result.scalars().all():
        balance_map[(balance.store_id, balance.product_id)] = balance
    shortage = next((products[item.product_id].name for item in payload.items if (balance_map.get((context.store.id, item.product_id)) or InventoryBalance(on_hand=0)).on_hand < item.quantity), None)
    if shortage:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock at {context.store.name} for {shortage}")
    reference = f"TRF-{now_utc():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    moved = []
    for item in payload.items:
        product = products[item.product_id]
        source = balance_map[(context.store.id, product.id)]
        target = balance_map.get((payload.to_store_id, product.id))
        if target is None:
            target = InventoryBalance(store_id=payload.to_store_id, product_id=product.id, on_hand=0, reorder_point=10)
            db.add(target)
            await db.flush()
        source.on_hand -= item.quantity
        target.on_hand += item.quantity
        db.add(StockMovement(store_id=context.store.id, product_id=product.id, quantity=-item.quantity, movement_type="transfer_out", reason="stock_transfer", reference_id=reference, created_by=context.user.id))
        db.add(StockMovement(store_id=payload.to_store_id, product_id=product.id, quantity=item.quantity, movement_type="transfer_in", reason="stock_transfer", reference_id=reference, created_by=context.user.id))
        if source.on_hand <= (source.reorder_point or 10):
            await notify_company_managers(db, membership.company_id, context.store.id, "low_stock", f"Low stock: {product.name}", f"Only {source.on_hand} left (reorder point {source.reorder_point or 10})")
        moved.append({"product_id": str(product.id), "product_name": product.name, "quantity": item.quantity})
    note = (payload.note or "").strip() or None
    await log_audit(db, membership, context.store.id, "stock_transferred_out", "inventory", entity_id=None, details={"reference": reference, "to_store_id": str(payload.to_store_id), "note": note}, user=context.user)
    await log_audit(db, membership, payload.to_store_id, "stock_transferred_in", "inventory", entity_id=None, details={"reference": reference, "from_store_id": str(context.store.id), "note": note}, user=context.user)
    await notify_company_managers(db, membership.company_id, payload.to_store_id, "stock_transfer", f"Incoming stock transfer", f"{len(moved)} item(s) in transit from {context.store.name}")
    await db.commit()
    return {"reference": reference, "from_store_id": str(context.store.id), "from_store_name": context.store.name, "to_store_id": str(payload.to_store_id), "to_store_name": to_store.name, "items": moved, "note": note}


def order_read(order: Order) -> OrderRead:
    payment_tenders = [tender for tender in order.tenders if tender.kind == "payment"]
    change_tender = next((tender for tender in order.tenders if tender.kind == "change"), None)
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
        created_at=order.created_at,
        paid_at=order.paid_at,
        refunded_amount=sum((refund.total for refund in order.refunds), Decimal("0.00")),
        customer=CustomerBriefRead(id=order.customer.id, name=order.customer.name, phone=order.customer.phone, email=order.customer.email) if order.customer else None,
        items=[{"id": item.id, "product_id": item.product_id, "product_name": item.product_name, "sku": item.sku, "unit_price": item.unit_price, "quantity": item.quantity, "line_total": item.line_total} for item in order.items],
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
    product_ids = [item.product_id for item in payload.items]
    products_result = await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))
    products = {product.id: product for product in products_result.scalars().all()}
    if len(products) != len(set(product_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    base_currency = await require_enabled_currency(db, context.membership.company_id, context.store.currency_code)
    balances_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids)).with_for_update())
    balances = {balance.product_id: balance for balance in balances_result.scalars().all()}
    subtotal = Decimal("0.00")
    item_rows: list[OrderItem] = []
    for requested in payload.items:
        product = products[requested.product_id]
        balance = balances.get(product.id)
        if not balance or balance.on_hand < requested.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name}")
        line_total = (product.price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total
        item_rows.append(OrderItem(product_id=product.id, product_name=product.name, sku=product.sku, unit_price=product.price, quantity=requested.quantity, line_total=line_total))
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
    merchant_scope = "none"
    if has_khqr:
        if len(tender_specs) != 1 or tender_specs[0].currency_code != "USD" or context.store.currency_code != "USD" or tender_specs[0].amount != total:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="KHQR must be one exact USD tender in v1")
        merchant_link = context.store.aba_payway_link if context.store.aba_payway_status == "active" else None
        merchant_scope = "store"
        if not merchant_link:
            company_row = await get_company(db, context.membership.company_id)
            merchant_link = company_row.aba_payway_link if company_row.aba_payway_status == "active" else None
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
    if tendered_base < total:
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
    customer = None
    customer_name = (payload.customer_name or "").strip() or None
    if payload.customer_id:
        customer = (await db.execute(select(Customer).where(Customer.id == payload.customer_id, Customer.company_id == context.membership.company_id))).scalar_one_or_none()
        if not customer or not customer.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        customer_name = customer.name.strip()
    order = Order(store_id=context.store.id, created_by=context.user.id, order_number=await next_document_number(db, store_id=context.store.id, scope="order", prefix=prefix), status="payment_pending", customer_id=customer.id if customer else None, customer_name=customer_name, tip=payload.tip, currency_code=context.store.currency_code, subtotal=subtotal, discount=payload.discount, tax=tax, total=total, items=item_rows, tenders=payment_tenders + ([change_tender] if change_tender else []))
    db.add(order)
    await db.flush()
    payment_method = tender_specs[0].method if len(tender_specs) == 1 else "mixed"
    if not has_khqr:
        db.add(Payment(order_id=order.id, provider=payment_method, status="paid", amount=total, currency_code=order.currency_code, reference_id=order.order_number, approved_at=now_utc()))
        await db.flush()
        await complete_order(db, order.id)
    else:
        merchant_meta: dict = {"type": "pos_order", "store_id": str(context.store.id), "merchant_connection": merchant_scope}
        if merchant_link:
            merchant_meta["merchant_aba_link"] = merchant_link
        try:
            provider_payment = await (await cutluy_client_for(db)).create_payment(total, order.order_number, merchant_meta)
        except CutLuyError as exc:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        db.add(Payment(order_id=order.id, provider="cutluy", status=provider_payment.get("status", "pending"), amount=total, currency_code=provider_payment.get("currency", "USD"), external_id=provider_payment.get("id"), reference_id=provider_payment.get("reference_id", order.order_number), qr_string=provider_payment.get("qr_string"), checkout_url=provider_payment.get("checkout_url"), provider_metadata=provider_payment.get("metadata")))
    await db.commit()
    return order_read(await order_by_id(db, order.id))


@router.get("/orders", response_model=list[OrderRead], tags=["orders"])
async def list_orders(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), order_status: str | None = Query(default=None, alias="status"), limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)) -> list[OrderRead]:
    query = select(Order).where(Order.store_id == context.store.id).options(selectinload(Order.items), selectinload(Order.payments), selectinload(Order.tenders), selectinload(Order.refunds), selectinload(Order.customer)).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    if order_status:
        query = query.where(Order.status == order_status)
    orders = (await db.execute(query)).scalars().unique().all()
    return [order_read(order) for order in orders]


@router.get("/orders/{order_id}", response_model=OrderRead, tags=["orders"])
async def get_order(order_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> OrderRead:
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order_read(order)


@router.post("/orders/{order_id}/cancel", response_model=OrderRead, tags=["orders"])
async def cancel_order(order_id: UUID, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> OrderRead:
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status == "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paid orders require a refund flow")
    order.status = "cancelled"
    await db.commit()
    return order_read(await order_by_id(db, order.id))


def held_order_read(held: HeldOrder, cashier_name: str | None = None, tax_rate: Decimal = Decimal("10.00"), tax_inclusive: bool = False) -> HeldOrderRead:
    items: list[HeldItemRead] = []
    subtotal = Decimal("0.00")
    for raw in held.items or []:
        quantity = int(raw.get("quantity", 0))
        unit_price = Decimal(str(raw.get("unit_price", "0")))
        line_total = Decimal(str(raw.get("line_total", "0")))
        subtotal += line_total
        items.append(HeldItemRead(product_id=UUID(raw["product_id"]), product_name=raw.get("product_name", ""), sku=raw.get("sku", ""), unit_price=unit_price, quantity=quantity, line_total=line_total))
    subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = Decimal("0.00") if tax_inclusive else (subtotal * tax_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return HeldOrderRead(id=held.id, store_id=held.store_id, created_by=held.created_by, cashier_name=cashier_name, label=held.label, created_at=held.created_at, item_count=sum(item.quantity for item in items), subtotal=subtotal, tax=tax, total=subtotal + tax, items=items)


@router.get("/held-orders", response_model=list[HeldOrderRead], tags=["orders"])
async def list_held_orders(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[HeldOrderRead]:
    result = await db.execute(select(HeldOrder, User.full_name).join(User, User.id == HeldOrder.created_by).where(HeldOrder.store_id == context.store.id).order_by(HeldOrder.created_at.desc()))
    return [held_order_read(held, cashier_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False))) for held, cashier_name in result.all()]


@router.post("/held-orders", response_model=HeldOrderRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_held_order(payload: HeldOrderCreateRequest, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> HeldOrderRead:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    product_ids = [item.product_id for item in payload.items]
    products_result = await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.id.in_(product_ids), Product.is_active.is_(True)))
    products = {product.id: product for product in products_result.scalars().all()}
    if len(products) != len(set(product_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more products are not available")
    balances_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id.in_(product_ids)))
    balances = {balance.product_id: balance for balance in balances_result.scalars().all()}
    snapshot: list[dict] = []
    for requested in payload.items:
        product = products[requested.product_id]
        balance = balances.get(product.id)
        if not balance or balance.on_hand < requested.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Insufficient stock for {product.name}")
        line_total = (product.price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        snapshot.append({"product_id": str(product.id), "product_name": product.name, "sku": product.sku, "unit_price": str(product.price), "quantity": requested.quantity, "line_total": str(line_total)})
    held = HeldOrder(store_id=context.store.id, created_by=context.user.id, label=(payload.label or "").strip()[:120] or None, items=snapshot)
    db.add(held)
    await db.commit()
    return held_order_read(held, context.user.full_name, context.store.service_tax_rate, bool(dict(context.store.preferences or {}).get("tax_inclusive", False)))


@router.delete("/held-orders/{held_id}", tags=["orders"])
async def delete_held_order(held_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "held_orders")
    result = await db.execute(select(HeldOrder).where(HeldOrder.id == held_id, HeldOrder.store_id == context.store.id))
    held = result.scalar_one_or_none()
    if not held:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Held order not found")
    await db.delete(held)
    await db.commit()
    return {"ok": True}


def refund_read(refund: Refund, order: Order | None = None, cashier_name: str | None = None) -> RefundRead:
    items: list[RefundItemRead] = []
    subtotal = Decimal("0.00")
    for raw in refund.items or []:
        quantity = int(raw.get("quantity", 0))
        unit_price = Decimal(str(raw.get("unit_price", "0")))
        line_total = Decimal(str(raw.get("line_total", "0")))
        subtotal += line_total
        items.append(RefundItemRead(product_id=UUID(raw["product_id"]), product_name=raw.get("product_name", ""), sku=raw.get("sku", ""), unit_price=unit_price, quantity=quantity, line_total=line_total))
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
        item_count=sum(item.quantity for item in items),
        items=items,
        created_at=refund.created_at,
    )


@router.get("/orders/{order_id}/refunds", response_model=list[RefundRead], tags=["orders"])
async def list_order_refunds(order_id: UUID, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> list[RefundRead]:
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    result = await db.execute(select(Refund, User.full_name).join(User, User.id == Refund.created_by).where(Refund.order_id == order.id).order_by(Refund.created_at.desc()))
    return [refund_read(refund, order, cashier_name) for refund, cashier_name in result.all()]


@router.post("/orders/{order_id}/refund", response_model=RefundRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_order_refund(order_id: UUID, payload: RefundCreateRequest, context: StoreContext = Depends(get_store_context), membership: Membership = catalog_roles, db: AsyncSession = Depends(get_db)) -> RefundRead:
    await require_plan_feature(db, context.membership.company_id, "refunds")
    order = await order_by_id(db, order_id)
    if order.store_id != context.store.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only paid orders can be refunded")
    existing_refunds = (await db.execute(select(Refund).where(Refund.order_id == order.id))).scalars().all()
    refunded_quantity: dict[UUID, int] = defaultdict(int)
    for refund in existing_refunds:
        for raw in refund.items or []:
            refunded_quantity[UUID(raw["product_id"])] += int(raw.get("quantity", 0))
    order_items = {item.product_id: item for item in order.items}
    snapshot: list[dict] = []
    subtotal = Decimal("0.00")
    for requested in payload.items:
        order_item = order_items.get(requested.product_id)
        if not order_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product is not part of this order")
        remaining = order_item.quantity - refunded_quantity.get(requested.product_id, 0)
        if requested.quantity > remaining:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Only {remaining} of {order_item.product_name} can be refunded")
        line_total = (order_item.unit_price * requested.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal += line_total
        snapshot.append({"product_id": str(order_item.product_id), "product_name": order_item.product_name, "sku": order_item.sku, "unit_price": str(order_item.unit_price), "quantity": requested.quantity, "line_total": str(line_total)})
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
        balance_result = await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == UUID(row["product_id"])).with_for_update())
        balance = balance_result.scalar_one_or_none()
        if not balance:
            balance = InventoryBalance(store_id=context.store.id, product_id=UUID(row["product_id"]), on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
        balance.on_hand += row["quantity"]
        db.add(StockMovement(store_id=context.store.id, product_id=UUID(row["product_id"]), quantity=row["quantity"], movement_type="refund", reason="order_refund", reference_id=order.order_number, created_by=context.user.id))
    refund = Refund(store_id=context.store.id, order_id=order.id, created_by=context.user.id, method=method, reason=(payload.reason or "").strip()[:255] or None, currency_code=order.currency_code, subtotal=subtotal, tax=tax, total=total, items=snapshot)
    db.add(refund)
    previously_refunded = sum((existing.total for existing in existing_refunds), Decimal("0.00"))
    if previously_refunded + subtotal >= order.subtotal:
        order.status = "refunded"
    await notify_company_managers(db, context.membership.company_id, context.store.id, "refund", f"Refund on {order.order_number}", f"{method.title()} refund of {total} {order.currency_code}")
    await log_audit(db, context.membership, context.store.id, "refunded", "order", order.id, {"order_number": order.order_number, "total": str(total), "method": method}, context.user)
    await db.commit()
    return refund_read(refund, order, context.user.full_name)


@router.get("/billing/subscription", response_model=SubscriptionRead, tags=["billing"])
async def current_subscription(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> SubscriptionRead:
    ent = await load_entitlement(db, membership.company_id)
    if ent.recurring is not None:
        return recurring_to_subscription_read(ent.recurring)
    result = await db.execute(select(Subscription).where(Subscription.company_id == membership.company_id, Subscription.status.in_(["active", "pending"])).order_by(Subscription.created_at.desc()))
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return SubscriptionRead.model_validate(subscription)


@router.put("/billing/schedule", response_model=SubscriptionRead, tags=["billing"])
async def schedule_plan_change(payload: BillingScheduleRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> SubscriptionRead:
    ent = await load_entitlement(db, membership.company_id)
    if ent.recurring is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are on Paddle auto-renew; change or cancel your plan from the Paddle customer portal")
    current = ent.subscription
    if current is None or current.plan_code == FREE_PLAN_CODE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An active paid plan is required to schedule a change")
    target = await get_plan(db, payload.plan_code)
    if target.code == current.plan_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This plan is already active")
    if target.code != FREE_PLAN_CODE and target.monthly_price >= ent.plan.monthly_price:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This is not a downgrade; use Billing checkout to upgrade")
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
    if ent.recurring is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are on Paddle auto-renew; change or cancel your plan from the Paddle customer portal")
    current = ent.subscription
    if current is None:
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
    if ent.recurring is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are on Paddle auto-renew; cancel it from the Paddle customer portal before paying prepaid")
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
    cycle_multiplier = {"monthly": 1, "semi_annual": 6, "annual": 12}.get(billing_cycle, 1)
    discount = Decimal("0.00")
    if billing_cycle == "semi_annual":
        discount = Decimal("0.15")
    elif billing_cycle == "annual":
        discount = Decimal("0.20")
    monthly_after_discount = plan.monthly_price * (1 - discount)
    total_amount = (monthly_after_discount * cycle_multiplier).quantize(Decimal("0.01"))
    subscription = Subscription(company_id=membership.company_id, plan_code=plan.code, billing_cycle=billing_cycle, status="pending", starts_at=now_utc())
    db.add(subscription)
    await db.flush()
    reference = f"plan-{membership.company_id}-{uuid.uuid4().hex}"
    provider = "paddle" if payload.payment_method == "card" else "cutluy"
    provider_metadata = {"type": "subscription", "subscription_id": str(subscription.id), "plan_code": plan.code, "billing_cycle": billing_cycle, "provider": provider}
    try:
        if provider == "paddle":
            paddle_cfg = await load_paddle_settings(db)
            price_id = (paddle_cfg.get("paddle_price_ids") or {}).get(f"{plan.code}:{billing_cycle}")
            if not price_id and paddle_cfg.get("paddle_mode") not in (None, "", "mock"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Paddle price is not configured for {plan.code} {billing_cycle}; set a price id in the Paddle settings",
                )
            provider_payment = await (await paddle_client_for(db)).create_transaction(
                price_id=price_id or f"pri_mock_{plan.code}_{billing_cycle}",
                reference_id=reference,
                metadata=provider_metadata,
                currency_code="USD",
            )
        else:
            provider_payment = await (await cutluy_client_for(db)).create_payment(total_amount, reference, provider_metadata)
    except (CutLuyError, PaddleError) as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    payment = BillingPayment(subscription_id=subscription.id, provider=provider, amount=total_amount, currency_code=provider_payment.get("currency", "USD"), external_id=provider_payment.get("id"), reference_id=provider_payment.get("reference_id", reference), status=provider_payment.get("status", "pending"), qr_string=provider_payment.get("qr_string"), checkout_url=provider_payment.get("checkout_url"), provider_metadata=provider_metadata)
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
    if ent.subscription is not None:
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
    await db.commit()
    await db.refresh(governing)
    return SubscriptionRead.model_validate(governing)


@router.get("/billing/payments", response_model=list[BillingPaymentRead], tags=["billing"])
async def billing_payments(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db), limit: int = Query(default=50, ge=1, le=100)) -> list[BillingPaymentRead]:
    query = select(BillingPayment).join(Subscription, Subscription.id == BillingPayment.subscription_id).where(Subscription.company_id == membership.company_id).order_by(BillingPayment.created_at.desc()).limit(limit)
    return [BillingPaymentRead.model_validate(payment) for payment in (await db.execute(query)).scalars().all()]


async def recurring_row_for_display(db: AsyncSession, company_id: UUID) -> RecurringSubscription | None:
    governing = (await load_entitlement(db, company_id)).recurring
    if governing is not None:
        return governing
    result = await db.execute(select(RecurringSubscription).where(RecurringSubscription.company_id == company_id).order_by(RecurringSubscription.created_at.desc()).limit(1))
    return result.scalars().first()


@router.get("/billing/recurring", response_model=RecurringSubscriptionRead | None, tags=["billing"])
async def current_recurring_subscription(membership: Membership = Depends(get_current_membership), db: AsyncSession = Depends(get_db)) -> RecurringSubscriptionRead | None:
    row = await recurring_row_for_display(db, membership.company_id)
    if row is None:
        return None
    return RecurringSubscriptionRead.model_validate(row)


@router.post("/billing/recurring/checkout", response_model=BillingRecurringCheckoutRead, status_code=status.HTTP_201_CREATED, tags=["billing"])
async def create_recurring_checkout(payload: BillingRecurringCheckoutRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> BillingRecurringCheckoutRead:
    plan = await get_plan(db, payload.plan_code)
    if plan.monthly_price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The Free plan is not billable")
    ent = await load_entitlement(db, membership.company_id)
    if ent.recurring is not None and ent.recurring.plan_code == payload.plan_code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This plan is already on Paddle auto-renew")
    cfg = await load_paddle_settings(db)
    mode = cfg.get("paddle_mode") or "mock"
    price_id = (cfg.get("paddle_price_ids") or {}).get(f"recurring:{payload.plan_code}:{payload.billing_cycle}")
    client_token = cfg.get("paddle_client_token")
    if mode != "mock":
        if not price_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Paddle recurring price is not configured for {payload.plan_code} {payload.billing_cycle}")
        if not client_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paddle client token is not configured; set PADDLE_CLIENT_TOKEN")
    return BillingRecurringCheckoutRead(
        plan_code=payload.plan_code,
        billing_cycle=payload.billing_cycle,
        client_token=client_token,
        price_id=price_id,
        checkout_url=None,
        mode=mode,
    )


@router.post("/billing/recurring/portal", response_model=BillingRecurringPortalRead, tags=["billing"])
async def create_recurring_portal_session(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> BillingRecurringPortalRead:
    ent = await load_entitlement(db, membership.company_id)
    row = ent.recurring
    if row is None:
        row = await db.scalar(select(RecurringSubscription).where(RecurringSubscription.company_id == membership.company_id).order_by(RecurringSubscription.created_at.desc()).limit(1))
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Paddle subscription to manage")
    customer_id = row.paddle_customer_id or (await get_company(db, membership.company_id)).paddle_customer_id
    client = await paddle_client_for(db)
    if client.mode == "mock" or not customer_id:
        return BillingRecurringPortalRead(url=None)
    try:
        url = await client.create_portal_session(customer_id=customer_id, subscription_id=row.paddle_subscription_id)
    except PaddleError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return BillingRecurringPortalRead(url=url)


@router.post("/billing/recurring/mock-activate", response_model=RecurringSubscriptionRead, status_code=status.HTTP_201_CREATED, tags=["development"])
async def mock_activate_recurring(payload: BillingRecurringCheckoutRequest, membership: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> RecurringSubscriptionRead:
    cfg = await load_paddle_settings(db)
    if settings.environment == "production" or (cfg.get("paddle_mode") or settings.paddle_mode) != "mock":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock Paddle activation is disabled")
    row = await mock_activate(db, membership.company_id, payload.plan_code, payload.billing_cycle)
    return RecurringSubscriptionRead.model_validate(row)


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
        valid_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == membership.company_id, Store.id.in_(payload.store_ids), Store.is_active.is_(True)))
        if valid_count != len(set(payload.store_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more stores are not available")
    raw_token = create_opaque_token()
    invitation = Invitation(company_id=membership.company_id, email=payload.email.lower(), role=payload.role, store_ids=[str(store_id) for store_id in payload.store_ids], token_hash=hash_opaque_token(raw_token), expires_at=now_utc() + timedelta(days=7), invited_by=membership.user_id)
    db.add(invitation)
    company = await get_company(db, membership.company_id)
    await db.commit()
    await db.refresh(invitation)
    await send_invitation_email(invitation.email, raw_token, company.name)
    return InvitationRead.model_validate({**invitation.__dict__, "dev_invitation_token": raw_token if settings.environment in {"development", "test"} else None})


@router.post("/team/invitations/accept", response_model=TokenResponse, tags=["team"])
async def accept_team_invitation(payload: InvitationAcceptRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
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
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_token(user.id), expires_in=settings.jwt_access_ttl_minutes * 60, user=user_read(user))


@router.patch("/team/{membership_id}", response_model=MembershipRead, tags=["team"])
async def update_team_member(membership_id: UUID, payload: MembershipUpdateRequest, actor: Membership = owner_roles, db: AsyncSession = Depends(get_db)) -> MembershipRead:
    result = await db.execute(select(Membership).where(Membership.id == membership_id, Membership.company_id == actor.company_id).options(selectinload(Membership.user)))
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    if member.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner role cannot be changed")
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
    member.status = "revoked"
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def signature_is_valid(raw_body: bytes, signature: str, secret: str | None, mode: str, environment: str) -> bool:
    if not secret:
        return mode == "mock" and environment != "production"
    pieces = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in signature.split(",") if "=" in part}
    timestamp = pieces.get("t")
    received = pieces.get("v1")
    if not timestamp or not received:
        return False
    try:
        fresh = abs(now_utc().timestamp() - int(timestamp)) < 300
    except ValueError:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return fresh and hmac.compare_digest(received, expected)


async def fulfill_billing_payment(provider_id: str, reference_id: str | None, approved_at: datetime | None, db: AsyncSession) -> bool:
    query = select(BillingPayment).where(BillingPayment.external_id == provider_id)
    if reference_id:
        query = select(BillingPayment).where((BillingPayment.external_id == provider_id) | (BillingPayment.reference_id == reference_id))
    payment = (await db.execute(query)).scalars().first()
    if not payment:
        return False
    subscription_result = await db.execute(select(Subscription).where(Subscription.id == payment.subscription_id).with_for_update())
    subscription = subscription_result.scalar_one()
    if subscription.status != "pending":
        return True
    approved = approved_at or now_utc()
    payment.status = "paid"
    payment.approved_at = approved
    active_result = await db.execute(select(Subscription).where(Subscription.company_id == subscription.company_id, Subscription.status == "active"))
    actives = active_result.scalars().all()
    governing = next((active for active in actives if active.id != subscription.id and is_in_force(active)), None)
    cycle_days = {"monthly": 30, "semi_annual": 182, "annual": 365}.get(subscription.billing_cycle, 30)
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
            queued.ends_at = queued.ends_at + timedelta(days=cycle_days)
            payment.subscription_id = queued.id
            subscription.status = "canceled"
            subscription.ends_at = approved
        else:
            boundary = governing.ends_at
            subscription.status = "active"
            subscription.starts_at = boundary
            subscription.ends_at = boundary + timedelta(days=cycle_days)
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
        subscription.ends_at = boundary + timedelta(days=cycle_days)
        subscription.scheduled_store_ids = governing.scheduled_store_ids
        subscription.scheduled_member_ids = governing.scheduled_member_ids
        governing.scheduled_plan_code = None
        governing.scheduled_store_ids = None
        governing.scheduled_member_ids = None
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
    subscription.ends_at = approved + timedelta(days=cycle_days)
    if subscription.plan_code != FREE_PLAN_CODE:
        plan = await db.get(Plan, subscription.plan_code)
        if plan:
            if paused_store_ids or paused_member_ids:
                await restore_capacity(db, subscription.company_id, plan=plan, store_ids=paused_store_ids, member_ids=paused_member_ids)
            await enforce_plan_capacity(
                db,
                subscription.company_id,
                subscription=subscription,
                plan=plan,
                keep_store_ids=keep_store_ids,
                keep_member_ids=keep_member_ids,
            )
    return True


@router.post("/webhooks/cutluy", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=True, tags=["payments"])
async def cutluy_webhook(request: Request, db: AsyncSession = Depends(get_db), x_cutluy_signature: Annotated[str, Header(alias="X-CutLuy-Signature")] = "") -> Response:
    raw_body = await request.body()
    cfg = await load_cutluy_settings(db)
    if not signature_is_valid(raw_body, x_cutluy_signature, cfg.get("cutluy_webhook_secret"), cfg.get("cutluy_mode") or settings.cutluy_mode, settings.environment):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CutLuy signature")
    try:
        event = CutLuyWebhookEvent.model_validate(json.loads(raw_body))
    except (ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid CutLuy event") from exc
    provider_payment = event.data.payment
    provider_id = provider_payment.id
    provider_status = provider_payment.status
    reference_id = provider_payment.reference_id
    if not provider_id or not provider_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incomplete CutLuy payment")
    billing_query = select(BillingPayment).where((BillingPayment.external_id == provider_id) | (BillingPayment.reference_id == reference_id if reference_id else BillingPayment.external_id == provider_id))
    billing_payment = (await db.execute(billing_query)).scalars().first()
    if billing_payment and (billing_payment.amount != provider_payment.amount or billing_payment.currency_code != provider_payment.currency):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CutLuy payment amount does not match billing record")
    if billing_payment:
        billing_payment.status = provider_status
    if provider_status == "paid":
        await fulfill_billing_payment(provider_id, reference_id, provider_payment.approved_at, db)
    payment_query = select(Payment).where((Payment.external_id == provider_id) | (Payment.reference_id == reference_id if reference_id else Payment.external_id == provider_id)).options(selectinload(Payment.order))
    payment = (await db.execute(payment_query)).scalars().first()
    if payment and (payment.amount != provider_payment.amount or payment.currency_code != provider_payment.currency):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CutLuy payment amount does not match order record")
    if payment:
        payment.status = provider_status
        if provider_status == "paid":
            await complete_order(db, payment.order_id, now_utc())
        elif provider_status in {"expired", "failed"}:
            payment.order.status = f"payment_{provider_status}"
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mock/cutluy/{provider_payment_id}/complete", status_code=status.HTTP_204_NO_CONTENT, tags=["development"])
async def complete_mock_payment(provider_payment_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    cfg = await load_cutluy_settings(db)
    if settings.environment == "production" or (cfg.get("cutluy_mode") or settings.cutluy_mode) != "mock":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock payment endpoint is disabled")
    order_payment_result = await db.execute(select(Payment).where(Payment.external_id == provider_payment_id))
    order_payment = order_payment_result.scalar_one_or_none()
    if order_payment:
        order_payment.status = "paid"
        await complete_order(db, order_payment.order_id)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    billing_result = await db.execute(select(BillingPayment).where(BillingPayment.external_id == provider_payment_id))
    billing_payment = billing_result.scalar_one_or_none()
    if billing_payment:
        await fulfill_billing_payment(provider_payment_id, billing_payment.reference_id, now_utc(), db)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")


@router.post("/webhooks/paddle", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=True, tags=["payments"])
async def paddle_webhook(request: Request, db: AsyncSession = Depends(get_db), paddle_signature: Annotated[str, Header(alias="Paddle-Signature")] = "") -> Response:
    raw_body = await request.body()
    cfg = await load_paddle_settings(db)
    if not paddle_signature_is_valid(raw_body, paddle_signature, cfg.get("paddle_webhook_secret"), cfg.get("paddle_mode") or settings.paddle_mode, settings.environment):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Paddle signature")
    try:
        event = PaddleWebhookEvent.model_validate(json.loads(raw_body))
    except (ValueError, TypeError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Paddle event") from exc
    if event.event_type.startswith("subscription."):
        async def _resolve_customer_email(cid: str) -> str | None:
            if not cid:
                return None
            try:
                cfg = await load_paddle_settings(db)
                if (cfg.get("paddle_mode") or settings.paddle_mode) == "mock":
                    return None
                client = PaddleClient(
                    mode=cfg.get("paddle_mode") or None,
                    api_url=cfg.get("paddle_api_url") or None,
                    api_key=cfg.get("paddle_api_key") or None,
                )
                customer = await client.get_customer(cid)
                return customer.get("email")
            except PaddleError:
                return None

        await apply_paddle_event(db, event.event_type, event.data, event.occurred_at, _resolve_customer_email)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if event.event_type not in {"transaction.completed"}:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    data = event.data or {}
    custom_data = data.get("custom_data") or {}
    transaction_id = data.get("id")
    reference_id = custom_data.get("reference_id")
    currency = data.get("currency_code")
    status_value = data.get("status")
    totals = (data.get("details") or {}).get("totals") or {}
    subtotal = totals.get("subtotal")
    if not transaction_id or not reference_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incomplete Paddle transaction")
    billing_query = select(BillingPayment).where((BillingPayment.external_id == transaction_id) | (BillingPayment.reference_id == reference_id))
    billing_payment = (await db.execute(billing_query)).scalars().first()
    if billing_payment:
        try:
            charged = Decimal(str(subtotal)) if subtotal is not None else None
        except Exception:
            charged = None
        # Paddle is merchant of record: it adds country tax on top of the quoted
        # (net) price, so compare the line subtotal, never the gross total.
        if charged is not None and billing_payment.amount != charged:
            logger.error("Paddle amount mismatch for %s: record=%s charged=%s", reference_id, billing_payment.amount, charged)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paddle payment amount does not match billing record")
        if currency and billing_payment.currency_code != currency:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paddle payment currency does not match billing record")
    if status_value == "completed":
        if billing_payment:
            billing_payment.status = "paid"
        await fulfill_billing_payment(transaction_id, reference_id, event.occurred_at, db)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mock/paddle/{provider_payment_id}/complete", status_code=status.HTTP_204_NO_CONTENT, tags=["development"])
async def complete_mock_paddle_payment(provider_payment_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    cfg = await load_paddle_settings(db)
    if settings.environment == "production" or (cfg.get("paddle_mode") or settings.paddle_mode) != "mock":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mock Paddle endpoint is disabled")
    billing_result = await db.execute(select(BillingPayment).where(BillingPayment.external_id == provider_payment_id))
    billing_payment = billing_result.scalar_one_or_none()
    if billing_payment:
        await fulfill_billing_payment(provider_payment_id, billing_payment.reference_id, now_utc(), db)
        await db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")


@router.get("/reports/summary", response_model=ReportSummary, tags=["reports"])
async def report_summary(
    context: StoreContext = Depends(get_store_context),
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
    items_sold = 0
    product_ids = {item.product_id for order in orders for item in order.items}
    product_rows = (await db.execute(select(Product.id, Category.name).outerjoin(Category, Category.id == Product.category_id).where(Product.id.in_(product_ids)))).all() if product_ids else []
    category_names = {product_id: category_name or "Uncategorized" for product_id, category_name in product_rows}
    for order in orders:
        daily[order.created_at.date().isoformat()] += order.total
        for item in order.items:
            category[category_names.get(item.product_id, "Uncategorized")] += item.line_total
            row = products.setdefault(item.product_name, {"name": item.product_name, "quantity": 0, "amount": Decimal("0.00")})
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
    top_products = sorted(({"name": data["name"], "quantity": data["quantity"], "amount": str(data["amount"].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))} for data in products.values()), key=lambda row: Decimal(row["amount"]), reverse=True)[:10]
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
        top_products=top_products,
        daily_sales=[{"date": key, "amount": amount} for key, amount in sorted(daily.items())],
        category_sales=[{"category": key, "amount": amount} for key, amount in sorted(category.items(), key=lambda item: item[1], reverse=True)],
        payment_methods=[{"method": key, "amount": amount} for key, amount in sorted(methods.items(), key=lambda item: item[1], reverse=True)],
        transactions_detail=transaction_rows,
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
    items_sold = 0
    per_store: dict[UUID, dict] = {store.id: {"transactions": 0, "net_sales": Decimal("0.00"), "gross_sales": Decimal("0.00"), "items_sold": 0} for store in stores}
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
            row = products.setdefault(item.product_name, {"name": item.product_name, "quantity": 0, "amount": Decimal("0.00")})
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
        top_products=[{"name": data["name"], "quantity": data["quantity"], "amount": str(data["amount"].quantize(quantum, rounding=ROUND_HALF_UP))} for data in sorted(products.values(), key=lambda row: row["amount"], reverse=True)[:10]],
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


def _money(value: Decimal, code: str) -> str:
    amount = Decimal(str(value))
    if code == "KHR":
        return f"KHR {int(amount.quantize(Decimal('1'))):,}"
    return f"{code} {amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


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
    store = context.store
    code = order.currency_code
    payment_lines = [f"- {tender.method.title()} {_money(tender.amount, tender.currency_code)} ({tender.currency_code})" for tender in order.tenders if tender.kind == "payment"]
    change_line = ""
    change_tender = next((tender for tender in order.tenders if tender.kind == "change"), None)
    if change_tender:
        change_line = f"Change: {_money(change_tender.amount, change_tender.currency_code)}"
    lines = [
        f"{company_name}",
        f"{store.name}",
        *( [store.address] if store.address else [] ),
        "",
        f"Receipt {order.order_number}",
        f"Customer: {order.customer.name}",
        f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Items:",
        *(f"  {item.quantity} x {item.product_name} @ {_money(item.unit_price, code)} = {_money(item.line_total, code)}" for item in order.items),
        "",
        f"Subtotal: {_money(order.subtotal, code)}",
        *( [f"Discount: -{_money(order.discount, code)}"] if order.discount else [] ),
        f"Tax: {_money(order.tax, code)}",
        f"Total: {_money(order.total, code)}",
        "",
        "Paid by:",
        *payment_lines,
        *( [change_line] if change_line else [] ),
        "",
        "Thank you for shopping with us!",
        "Sent by Chmaba",
    ]
    sent = await send_email(recipient, f"Your receipt for {order.order_number}", "\n".join(lines))
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
async def change_password(payload: ChangePasswordRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return {"ok": True}


async def log_audit(db: AsyncSession, membership: Membership, store_id: UUID | None, action: str, entity_type: str, entity_id: UUID | None = None, details: dict | None = None, user: User | None = None) -> None:
    actor = user
    db.add(TenantAuditLog(company_id=membership.company_id, store_id=store_id, actor_user_id=actor.id, actor_name=actor.full_name, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


@router.get("/audit-logs", tags=["audit"])
async def list_audit_logs(membership: Membership = owner_roles, db: AsyncSession = Depends(get_db), limit: int = Query(default=100, ge=1, le=300)) -> list[dict]:
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
async def export_gdt_csv(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db), from_date: date | None = Query(default=None), to_date: date | None = Query(default=None)):
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
    snapshot = []
    for item in items:
        product = by_id.get(UUID(item["product_id"]))
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        qty = int(item.get("quantity", 0))
        if qty <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="quantity must be positive")
        snapshot.append({"product_id": str(product.id), "product_name": product.name, "sku": product.sku, "quantity": qty, "unit_cost": str(Decimal(str(item.get("unit_cost", 0))))})
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
    for item in po.items or []:
        product_id = UUID(item["product_id"])
        balance = (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id, InventoryBalance.product_id == product_id).with_for_update())).scalar_one_or_none()
        if not balance:
            balance = InventoryBalance(store_id=context.store.id, product_id=product_id, on_hand=0, reorder_point=10)
            db.add(balance)
            await db.flush()
        balance.on_hand += int(item["quantity"])
        db.add(StockMovement(store_id=context.store.id, product_id=product_id, quantity=int(item["quantity"]), movement_type="purchase", reason="received_po", reference_id=po.po_number, created_by=context.user.id))
    po.status = "received"
    po.received_at = now_utc()
    await db.commit()
    return {"id": str(po.id), "po_number": po.po_number, "status": po.status}


@router.get("/products/export.csv", include_in_schema=False, tags=["catalog"])
async def export_products_csv(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)):
    products = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.is_active.is_(True)).order_by(Product.name))).scalars().all()
    balances = {b.product_id: b for b in (await db.execute(select(InventoryBalance).where(InventoryBalance.store_id == context.store.id))).scalars().all()}
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["sku", "name", "price", "stock", "reorder_point"])
    for product in products:
        balance = balances.get(product.id)
        writer.writerow([product.sku, product.name, str(product.price), balance.on_hand if balance else 0, (balance.reorder_point if balance else 10)])
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
        stock = int(float(row.get("stock") or 0))
        reorder = int(float(row.get("reorder_point") or 10))
        product = (await db.execute(select(Product).where(Product.company_id == context.membership.company_id, Product.sku == sku))).scalar_one_or_none()
        if product:
            product.name = name
            product.price = price
            updated += 1
        else:
            product = Product(company_id=context.membership.company_id, name=name, sku=sku, price=price)
            db.add(product)
            await db.flush()
            created += 1
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
    start_at = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    paid = (await db.execute(select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(Order.store_id == context.store.id, Order.status == "paid", Order.created_at >= start_at))).one()
    refund_total = (await db.execute(select(func.coalesce(func.sum(Refund.total), 0)).where(Refund.store_id == context.store.id, Refund.created_at >= start_at))).scalar_one()
    body = (f"Daily summary for {context.store.name} on {today.isoformat()}\n\n"
            f"Orders: {int(paid[0])}\nGross sales: {paid[1]}\nRefunds: {refund_total}\n\nSent by Chmaba")
    sent_any = False
    for email in owner_emails:
        if await send_email(email, f"Daily summary · {context.store.name}", body):
            sent_any = True
    if not sent_any:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send summary email")
    return {"ok": True, "emails": list(owner_emails)}


@router.post("/notifications/send-low-stock", tags=["notifications"])
async def send_low_stock_email(context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    owner_emails = (await db.execute(select(User.email).join(Membership, Membership.user_id == User.id).where(Membership.company_id == context.membership.company_id, Membership.status == "active", Membership.role == "owner"))).scalars().all()
    low = (await db.execute(select(InventoryBalance, Product.name).join(Product, Product.id == InventoryBalance.product_id).where(InventoryBalance.store_id == context.store.id, InventoryBalance.on_hand <= InventoryBalance.reorder_point).order_by(InventoryBalance.on_hand))).all()
    lines = [f"Low stock for {context.store.name}:"] + [f"- {name}: {balance.on_hand} left (reorder {balance.reorder_point})" for balance, name in low] or ["No low stock right now."]
    body = "\n".join(lines) + "\n\nSent by Chmaba"
    for email in owner_emails:
        await send_email(email, f"Low stock alert · {context.store.name}", body)
    return {"ok": True, "low_stock_items": len(low), "emails": list(owner_emails)}

@router.patch("/customers/{customer_id}/points", tags=["customers"])
async def adjust_customer_points(customer_id: UUID, payload: dict, context: StoreContext = Depends(get_store_context), db: AsyncSession = Depends(get_db)) -> dict:
    await require_plan_feature(db, context.membership.company_id, "loyalty")
    try:
        delta = int(payload.get("delta", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="delta must be an integer")
    customer = (await db.execute(select(Customer).where(Customer.id == customer_id, Customer.company_id == context.membership.company_id))).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    updated = int(customer.points) + delta
    if updated < 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Customer only has {int(customer.points)} points")
    customer.points = updated
    await db.commit()
    return {"customer_id": str(customer.id), "points": updated}

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
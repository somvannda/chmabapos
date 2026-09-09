from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db, get_platform_admin, require_super_admin
from app.models import AuditLog, Company, Membership, Plan, Store, Subscription, User
from app.schemas import (
    AdminAuditLogRead,
    AdminCompanyRead,
    AdminOverviewRead,
    AdminPaymentLinkCompanyRead,
    AdminPaymentLinksRead,
    AdminPaymentLinkStatusRead,
    AdminPaymentLinkStoreRead,
    AdminPaymentLinkUpdateRequest,
    AdminPlanCreateRequest,
    AdminPlanUpdateRequest,
    AdminStatusUpdateRequest,
    AdminStoreRead,
    AdminSubscriptionRead,
    AdminUserRead,
    AdminUserUpdateRequest,
    CutLuySettingsRead,
    CutLuySettingsUpdateRequest,
    PaddleSettingsRead,
    PaddleSettingsUpdateRequest,
    PlanRead,
)
from app.services.platform_config import load_cutluy_settings, load_paddle_settings, save_cutluy_settings, save_paddle_settings


router = APIRouter(prefix="/admin", tags=["platform-admin"])


async def audit(db: AsyncSession, actor: User, action: str, entity_type: str, entity_id: UUID | None, details: dict | None = None) -> None:
    db.add(AuditLog(actor_user_id=actor.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details))


def validate_limit(limit: int) -> int:
    return min(max(limit, 1), 100)


@router.get("/overview", response_model=AdminOverviewRead)
async def overview(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminOverviewRead:
    users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(select(func.count(User.id)).where(User.is_active.is_(True)))
    companies = await db.scalar(select(func.count(Company.id)))
    active_companies = await db.scalar(select(func.count(Company.id)).where(Company.is_active.is_(True)))
    stores = await db.scalar(select(func.count(Store.id)))
    active_stores = await db.scalar(select(func.count(Store.id)).where(Store.is_active.is_(True)))
    now = datetime.now(timezone.utc)
    paid_subscriptions = await db.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active",
            Subscription.plan_code != "free",
            or_(Subscription.ends_at.is_(None), Subscription.ends_at > now),
        )
    )
    pending_subscriptions = await db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "pending"))
    return AdminOverviewRead(users=users or 0, active_users=active_users or 0, companies=companies or 0, active_companies=active_companies or 0, stores=stores or 0, active_stores=active_stores or 0, paid_subscriptions=paid_subscriptions or 0, pending_subscriptions=pending_subscriptions or 0)


@router.get("/users", response_model=list[AdminUserRead])
async def list_users(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=120),
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AdminUserRead]:
    query = select(User).order_by(User.created_at.desc()).limit(validate_limit(limit))
    if active_only:
        query = query.where(User.is_active.is_(True))
    if search:
        query = query.where(User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%"))
    users = (await db.execute(query)).scalars().all()
    output = []
    for user in users:
        company_count = await db.scalar(select(func.count(Membership.id)).where(Membership.user_id == user.id, Membership.status == "active"))
        output.append(AdminUserRead(id=user.id, email=user.email, full_name=user.full_name, is_active=user.is_active, is_email_verified=user.is_email_verified, platform_role=user.platform_role, created_at=user.created_at, company_count=company_count or 0))
    return output


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(user_id: UUID, payload: AdminUserUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> AdminUserRead:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == actor.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
    changes = {}
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.platform_role is not None:
        user.platform_role = payload.platform_role
        changes["platform_role"] = payload.platform_role
    await audit(db, actor, "admin.user_updated", "user", user.id, changes)
    await db.commit()
    await db.refresh(user)
    company_count = await db.scalar(select(func.count(Membership.id)).where(Membership.user_id == user.id, Membership.status == "active"))
    return AdminUserRead(id=user.id, email=user.email, full_name=user.full_name, is_active=user.is_active, is_email_verified=user.is_email_verified, platform_role=user.platform_role, created_at=user.created_at, company_count=company_count or 0)


@router.get("/companies", response_model=list[AdminCompanyRead])
async def list_companies(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=120),
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AdminCompanyRead]:
    query = select(Company).order_by(Company.created_at.desc()).limit(validate_limit(limit))
    if active_only:
        query = query.where(Company.is_active.is_(True))
    if search:
        query = query.where(Company.name.ilike(f"%{search}%"))
    companies = (await db.execute(query)).scalars().all()
    output = []
    for company in companies:
        store_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company.id))
        member_count = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company.id, Membership.status == "active"))
        subscription = (await db.execute(select(Subscription).where(Subscription.company_id == company.id).order_by(Subscription.created_at.desc()).limit(1))).scalars().first()
        output.append(AdminCompanyRead(id=company.id, name=company.name, country=company.country, default_currency_code=company.default_currency_code, aba_payway_link=company.aba_payway_link, aba_payway_status=company.aba_payway_status, is_active=company.is_active, created_at=company.created_at, store_count=store_count or 0, member_count=member_count or 0, plan_code=subscription.plan_code if subscription else None, subscription_status=subscription.status if subscription else None))
    return output


@router.patch("/companies/{company_id}", response_model=AdminCompanyRead)
async def update_company_status(company_id: UUID, payload: AdminStatusUpdateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminCompanyRead:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    company.is_active = payload.is_active
    await audit(db, actor, "admin.company_status_changed", "company", company.id, {"is_active": payload.is_active})
    await db.commit()
    store_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company.id))
    member_count = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company.id, Membership.status == "active"))
    subscription = (await db.execute(select(Subscription).where(Subscription.company_id == company.id).order_by(Subscription.created_at.desc()).limit(1))).scalars().first()
    return AdminCompanyRead(id=company.id, name=company.name, country=company.country, default_currency_code=company.default_currency_code, aba_payway_link=company.aba_payway_link, aba_payway_status=company.aba_payway_status, is_active=company.is_active, created_at=company.created_at, store_count=store_count or 0, member_count=member_count or 0, plan_code=subscription.plan_code if subscription else None, subscription_status=subscription.status if subscription else None)


@router.get("/stores", response_model=list[AdminStoreRead])
async def list_stores(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=120),
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AdminStoreRead]:
    query = select(Store, Company.name).join(Company, Company.id == Store.company_id).order_by(Store.created_at.desc()).limit(validate_limit(limit))
    if active_only:
        query = query.where(Store.is_active.is_(True))
    if search:
        query = query.where(Store.name.ilike(f"%{search}%") | Company.name.ilike(f"%{search}%"))
    return [AdminStoreRead(id=store.id, company_id=store.company_id, company_name=company_name, name=store.name, address=store.address, phone=store.phone, timezone=store.timezone, currency_code=store.currency_code, aba_payway_link=store.aba_payway_link, aba_payway_status=store.aba_payway_status, is_active=store.is_active, created_at=store.created_at) for store, company_name in (await db.execute(query)).all()]


@router.patch("/stores/{store_id}", response_model=AdminStoreRead)
async def update_store_status(store_id: UUID, payload: AdminStatusUpdateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminStoreRead:
    result = await db.execute(select(Store, Company.name).join(Company, Company.id == Store.company_id).where(Store.id == store_id))
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    store, company_name = row
    store.is_active = payload.is_active
    await audit(db, actor, "admin.store_status_changed", "store", store.id, {"is_active": payload.is_active})
    await db.commit()
    return AdminStoreRead(id=store.id, company_id=store.company_id, company_name=company_name, name=store.name, address=store.address, phone=store.phone, timezone=store.timezone, currency_code=store.currency_code, aba_payway_link=store.aba_payway_link, aba_payway_status=store.aba_payway_status, is_active=store.is_active, created_at=store.created_at)


@router.get("/payment-links", response_model=AdminPaymentLinksRead)
async def list_payment_links(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    aba_payway_status: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=200),
) -> AdminPaymentLinksRead:
    company_query = select(Company).where(Company.aba_payway_link.is_not(None)).order_by(Company.created_at.desc()).limit(validate_limit(limit))
    if aba_payway_status:
        company_query = company_query.where(Company.aba_payway_status == aba_payway_status)
    if search:
        company_query = company_query.where(Company.name.ilike(f"%{search}%"))
    companies = (await db.execute(company_query)).scalars().all()
    company_rows = []
    for company in companies:
        store_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company.id))
        company_rows.append(AdminPaymentLinkCompanyRead(id=company.id, name=company.name, aba_payway_link=company.aba_payway_link, aba_payway_status=company.aba_payway_status, store_count=store_count or 0, created_at=company.created_at))

    store_query = (
        select(Store, Company.name)
        .join(Company, Company.id == Store.company_id)
        .where(Store.aba_payway_link.is_not(None))
        .order_by(Store.created_at.desc())
        .limit(validate_limit(limit))
    )
    if aba_payway_status:
        store_query = store_query.where(Store.aba_payway_status == aba_payway_status)
    if search:
        store_query = store_query.where(Store.name.ilike(f"%{search}%") | Company.name.ilike(f"%{search}%"))
    store_rows = [
        AdminPaymentLinkStoreRead(id=store.id, company_id=store.company_id, company_name=company_name, name=store.name, aba_payway_link=store.aba_payway_link, aba_payway_status=store.aba_payway_status, created_at=store.created_at)
        for store, company_name in (await db.execute(store_query)).all()
    ]
    return AdminPaymentLinksRead(companies=company_rows, stores=store_rows)


@router.patch("/payment-links/{scope}/{entity_id}", response_model=AdminPaymentLinkStatusRead)
async def update_payment_link_status(scope: str, entity_id: UUID, payload: AdminPaymentLinkUpdateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminPaymentLinkStatusRead:
    if scope == "company":
        company = await db.get(Company, entity_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
        company.aba_payway_status = payload.aba_payway_status
        await audit(db, actor, "admin.payment_link_status_changed", "company", company.id, {"aba_payway_status": payload.aba_payway_status})
        await db.commit()
        return AdminPaymentLinkStatusRead(scope="company", id=company.id, name=company.name, aba_payway_link=company.aba_payway_link, aba_payway_status=company.aba_payway_status)
    if scope == "store":
        result = await db.execute(select(Store, Company.name).join(Company, Company.id == Store.company_id).where(Store.id == entity_id))
        row = result.first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
        store, company_name = row
        store.aba_payway_status = payload.aba_payway_status
        await audit(db, actor, "admin.payment_link_status_changed", "store", store.id, {"aba_payway_status": payload.aba_payway_status})
        await db.commit()
        return AdminPaymentLinkStatusRead(scope="store", id=store.id, name=f"{company_name} / {store.name}", aba_payway_link=store.aba_payway_link, aba_payway_status=store.aba_payway_status)
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="scope must be 'company' or 'store'")


@router.get("/cutluy-settings", response_model=CutLuySettingsRead)
async def get_cutluy_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> CutLuySettingsRead:
    cfg = await load_cutluy_settings(db)
    return CutLuySettingsRead(
        mode=cfg.get("cutluy_mode") or "mock",
        api_url=cfg.get("cutluy_api_url") or "https://cutluy.com/v1",
        store_link=cfg.get("cutluy_store_link"),
        callback_url=cfg.get("cutluy_callback_url"),
        checkout_success_url=cfg.get("cutluy_checkout_success_url"),
        checkout_failure_url=cfg.get("cutluy_checkout_failure_url"),
        api_key_set=bool(cfg.get("cutluy_api_key")),
        webhook_secret_set=bool(cfg.get("cutluy_webhook_secret")),
        environment=settings.environment,
    )


@router.patch("/cutluy-settings", response_model=CutLuySettingsRead)
async def update_cutluy_settings(payload: CutLuySettingsUpdateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> CutLuySettingsRead:
    updates: dict[str, str | None] = {}
    field_map = {
        "mode": "cutluy_mode",
        "api_url": "cutluy_api_url",
        "api_key": "cutluy_api_key",
        "webhook_secret": "cutluy_webhook_secret",
        "store_link": "cutluy_store_link",
        "callback_url": "cutluy_callback_url",
        "checkout_success_url": "cutluy_checkout_success_url",
        "checkout_failure_url": "cutluy_checkout_failure_url",
    }
    for field_name, key in field_map.items():
        if field_name in payload.model_fields_set:
            updates[key] = getattr(payload, field_name)
    if updates:
        await save_cutluy_settings(db, updates)
        await audit(db, actor, "admin.cutluy_settings_updated", "platform", None, {"fields": sorted(updates.keys())})
        await db.commit()
    return await get_cutluy_settings(_=None, db=db)


@router.get("/paddle-settings", response_model=PaddleSettingsRead)
async def get_paddle_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> PaddleSettingsRead:
    cfg = await load_paddle_settings(db)
    return PaddleSettingsRead(
        mode=cfg.get("paddle_mode") or "mock",
        api_url=cfg.get("paddle_api_url"),
        checkout_success_url=cfg.get("paddle_checkout_success_url"),
        checkout_failure_url=cfg.get("paddle_checkout_failure_url"),
        price_ids=cfg.get("paddle_price_ids") or {},
        api_key_set=bool(cfg.get("paddle_api_key")),
        webhook_secret_set=bool(cfg.get("paddle_webhook_secret")),
        environment=settings.environment,
    )


@router.patch("/paddle-settings", response_model=PaddleSettingsRead)
async def update_paddle_settings(payload: PaddleSettingsUpdateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> PaddleSettingsRead:
    updates: dict[str, str | None] = {}
    field_map = {
        "mode": "paddle_mode",
        "api_url": "paddle_api_url",
        "api_key": "paddle_api_key",
        "webhook_secret": "paddle_webhook_secret",
        "checkout_success_url": "paddle_checkout_success_url",
        "checkout_failure_url": "paddle_checkout_failure_url",
        "price_ids": "paddle_price_ids",
    }
    for field_name, key in field_map.items():
        if field_name in payload.model_fields_set:
            updates[key] = getattr(payload, field_name)
    if updates:
        await save_paddle_settings(db, updates)
        await audit(db, actor, "admin.paddle_settings_updated", "platform", None, {"fields": sorted(updates.keys())})
        await db.commit()
    return await get_paddle_settings(_=None, db=db)


@router.get("/subscriptions", response_model=list[AdminSubscriptionRead])
async def list_subscriptions(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    subscription_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AdminSubscriptionRead]:
    query = select(Subscription, Company.name).join(Company, Company.id == Subscription.company_id).order_by(Subscription.created_at.desc()).limit(validate_limit(limit))
    if subscription_status:
        query = query.where(Subscription.status == subscription_status)
    return [AdminSubscriptionRead(id=subscription.id, company_id=subscription.company_id, company_name=company_name, plan_code=subscription.plan_code, billing_cycle=subscription.billing_cycle, status=subscription.status, starts_at=subscription.starts_at, ends_at=subscription.ends_at, created_at=subscription.created_at) for subscription, company_name in (await db.execute(query)).all()]


@router.get("/plans", response_model=list[PlanRead])
async def list_plans(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = True,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[PlanRead]:
    query = select(Plan).order_by(Plan.monthly_price, Plan.code).limit(validate_limit(limit))
    if not include_inactive:
        query = query.where(Plan.is_active.is_(True))
    return [PlanRead.model_validate(plan) for plan in (await db.execute(query)).scalars().all()]


@router.post("/plans", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
async def create_plan(payload: AdminPlanCreateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> PlanRead:
    existing = await db.get(Plan, payload.code)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plan code already exists")
    plan = Plan(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        monthly_price=payload.monthly_price,
        max_stores=payload.max_stores,
        max_members=payload.max_members,
        transaction_limit=payload.transaction_limit,
        capabilities=payload.capabilities,
        is_active=payload.is_active,
    )
    db.add(plan)
    await audit(db, actor, "admin.plan_created", "plan", None, {"code": plan.code, "name": plan.name, "monthly_price": str(plan.monthly_price)})
    await db.commit()
    await db.refresh(plan)
    return PlanRead.model_validate(plan)


@router.patch("/plans/{plan_code}", response_model=PlanRead)
async def update_plan(plan_code: str, payload: AdminPlanUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> PlanRead:
    plan = await db.get(Plan, plan_code)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    changes: dict = {}
    fields = {
        "name": payload.name,
        "description": payload.description,
        "monthly_price": payload.monthly_price,
        "max_stores": payload.max_stores,
        "max_members": payload.max_members,
        "transaction_limit": payload.transaction_limit,
        "capabilities": payload.capabilities,
        "is_active": payload.is_active,
    }
    for attr, value in fields.items():
        if value is not None:
            setattr(plan, attr, value)
            changes[attr] = value if attr != "monthly_price" else str(value)
    await audit(db, actor, "admin.plan_updated", "plan", None, {**changes, "code": plan.code})
    await db.commit()
    await db.refresh(plan)
    return PlanRead.model_validate(plan)


@router.get("/audit-logs", response_model=list[AdminAuditLogRead])
async def list_audit_logs(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AdminAuditLogRead]:
    query = select(AuditLog, User.email).join(User, User.id == AuditLog.actor_user_id).order_by(AuditLog.created_at.desc()).limit(validate_limit(limit))
    return [AdminAuditLogRead(id=log.id, actor_user_id=log.actor_user_id, actor_email=email, action=log.action, entity_type=log.entity_type, entity_id=log.entity_id, details=log.details, created_at=log.created_at) for log, email in (await db.execute(query)).all()]

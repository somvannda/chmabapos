from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from html import escape
from statistics import median
from decimal import Decimal
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db, get_platform_admin, require_super_admin
from app.email import html_to_text, send_email
from app.services.email_layout import data_table, transactional_email
from app.models import AuditLog, AuthSession, BillingPayment, BillingRefund, Company, Customer, EmailSend, EmailSuppression, EmailTemplate, HelpArticle, InventoryBalance, MailingDripDelivery, Membership, Order, OrderItem, OrderTender, Plan, PlatformActivity, Product, ProductVariant, Refund, Store, Subscription, SupportTicket, SupportTicketAttachment, SupportTicketMessage, User, VariantInventoryBalance
from app.schemas import (
    AdminActivityRead,
    AdminAttentionItemRead,
    AdminAttentionRead,
    AdminAuditLogRead,
    AdminBillingAnalyticsRead,
    AdminBillingCycleMixRead,
    AdminBillingPaymentRead,
    AdminBillingPlanMixRead,
    AdminBillingStatusCountRead,
    AdminCompanyDetailRead,
    AdminCompanyMemberRead,
    AdminCompanyRead,
    AdminCompanyStoreRead,
    AdminFunnelEmailRead,
    AdminFunnelRead,
    AdminFunnelStageRead,
    AdminTimeToFirstSaleRead,
    AdminInventorySummaryRead,
    AdminMembershipRead,
    AdminOverviewRead,
    AdminPaymentLinkCompanyRead,
    AdminPaymentLinksRead,
    AdminPaymentLinkStatusRead,
    AdminPaymentLinkStoreRead,
    AdminPaymentLinkUpdateRequest,
    AdminPlanCreateRequest,
    AdminPlanUpdateRequest,
    AdminRetentionCohortRead,
    AdminRetentionRead,
    AdminRetentionWeekRead,
    AdminSalesAnalyticsRead,
    AdminSalesMethodRead,
    AdminSalesProductRead,
    AdminSalesRankRead,
    AdminSalesSummaryRead,
    AdminSearchCompanyRead,
    AdminSearchRead,
    AdminSearchStoreRead,
    AdminSearchUserRead,
    AdminStatusUpdateRequest,
    AdminStoreRead,
    AdminSubscriptionRead,
    AdminUserDetailRead,
    AdminUserRead,
    AdminUserSessionRead,
    AdminUserUpdateRequest,
    AIDraftRead,
    AIDraftRequest,
    AISecretRevealRead,
    AISettingsRead,
    AISettingsUpdateRequest,
    AITestRead,
    BillingRefundCreateRequest,
    BillingRefundRead,
    ChmabaPaySecretRevealRead,
    ChmabaPaySecretRevealRequest,
    ChmabaPaySettingsRead,
    ChmabaPaySettingsUpdateRequest,
    EmailSendRead,
    EmailSuppressionRead,
    EmailTemplateCreateRequest,
    EmailTemplateRead,
    EmailTemplateUpdateRequest,
    HelpArticleCreateRequest,
    HelpArticleRead,
    HelpArticleUpdateRequest,
    MailingAudienceRead,
    MailingAudienceSegmentRead,
    MailingDripRead,
    MailingDripRunRead,
    MailingDripUpdateRequest,
    MailingImageRead,
    MailingQueueRunRead,
    MailingRecipientRead,
    MailingSendRequest,
    MailingSendResultRead,
    MailingTokenRead,
    MailSecretRevealRead,
    MailSecretRevealRequest,
    MailSettingsRead,
    MailSettingsUpdateRequest,
    MailTestRead,
    MailTestRequest,
    PlanRead,
    SessionSettingsRead,
    SessionSettingsUpdateRequest,
    SupportInsightsRead,
    SupportTicketAiDraftRead,
    SupportTicketAiDraftRequest,
    SupportTicketAiSuggestRead,
    SupportTicketAttachmentRead,
    SupportTicketDetailRead,
    SupportTicketMessageRead,
    SupportTicketRead,
    SupportTicketReplyRequest,
    SupportTicketUpdateRequest,
)
from app.services import ai as ai_service
from app.services import ai_pricing
from app.services import mail as mail_service
from app.services import mailing as mailing_service
from app.services import session_policy as session_policy_service
from app.services import support_tickets as support_tickets_service
from app.services.richtext import sanitize_html
from app.services.activity import activity_title
from app.services.platform_config import load_payment_settings, save_payment_settings
from app.media import read_image_upload, store_image, store_platform_image
from app.api.v1 import active_payment_provider, resolve_platform_store_id


_MASK_PREFIXES = ("ck_live_", "ck_test_", "pk_live_", "sk_live_", "whsec_")


def _mask_secret(value: str | None) -> str | None:
    """Partially mask a stored secret for admin display, keeping its known prefix."""
    if not value:
        return None
    head = next((prefix for prefix in _MASK_PREFIXES if value.startswith(prefix)), None)
    if head is None:
        head = value[:6]
    if len(value) <= len(head) + 4:
        return "*" * len(value)
    return f"{head}...{value[-4:]}"


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
            Subscription.starts_at <= now,
            or_(Subscription.ends_at.is_(None), Subscription.ends_at > now),
        )
    )
    pending_subscriptions = await db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "pending"))

    # Business KPIs. Signups, sales and engagement for the last 30 days, plus
    # the platform's own plan revenue. Tenant sales are reported for the single
    # busiest currency so amounts in different currencies are never summed.
    since_30d = now - timedelta(days=30)
    since_7d = now - timedelta(days=7)
    new_users_7d = await db.scalar(select(func.count(User.id)).where(User.created_at >= since_7d)) or 0
    new_users_30d = await db.scalar(select(func.count(User.id)).where(User.created_at >= since_30d)) or 0
    new_companies_30d = await db.scalar(select(func.count(Company.id)).where(Company.created_at >= since_30d)) or 0
    active_users_30d = await db.scalar(
        select(func.count(func.distinct(PlatformActivity.user_id))).where(
            PlatformActivity.created_at >= since_30d,
            PlatformActivity.user_id.is_not(None),
        )
    ) or 0

    orders_total = await db.scalar(select(func.count(Order.id)).where(Order.status == "paid")) or 0
    orders_30d = await db.scalar(select(func.count(Order.id)).where(Order.status == "paid", Order.created_at >= since_30d)) or 0
    gmv_30d = Decimal("0.00")
    gmv_currency = "USD"
    gmv_rows = (
        await db.execute(
            select(Order.currency_code, func.coalesce(func.sum(Order.total), 0))
            .where(Order.status == "paid", Order.created_at >= since_30d)
            .group_by(Order.currency_code)
        )
    ).all()
    for code, amount in gmv_rows:
        amount = Decimal(amount or 0)
        if amount > gmv_30d:
            gmv_30d, gmv_currency = amount, code
    gmv_30d = gmv_30d.quantize(Decimal("0.01"))

    # Platform revenue is the plan fees Chmaba itself collects, counted when the
    # payment was approved/fulfilled rather than when the checkout was created.
    paid_at = func.coalesce(BillingPayment.fulfilled_at, BillingPayment.approved_at, BillingPayment.created_at)
    platform_revenue_total = await db.scalar(
        select(func.coalesce(func.sum(BillingPayment.amount), 0)).where(BillingPayment.status == "paid")
    ) or Decimal("0")
    platform_revenue_30d = await db.scalar(
        select(func.coalesce(func.sum(BillingPayment.amount), 0)).where(BillingPayment.status == "paid", paid_at >= since_30d)
    ) or Decimal("0")

    # List-price MRR across active, non-free subscriptions.
    mrr = await db.scalar(
        select(func.coalesce(func.sum(Plan.monthly_price), 0))
        .select_from(Subscription)
        .join(Plan, Plan.code == Subscription.plan_code)
        .where(
            Subscription.status == "active",
            Subscription.plan_code != "free",
            Subscription.starts_at <= now,
            or_(Subscription.ends_at.is_(None), Subscription.ends_at > now),
        )
    ) or Decimal("0")

    return AdminOverviewRead(
        users=users or 0,
        active_users=active_users or 0,
        companies=companies or 0,
        active_companies=active_companies or 0,
        stores=stores or 0,
        active_stores=active_stores or 0,
        paid_subscriptions=paid_subscriptions or 0,
        pending_subscriptions=pending_subscriptions or 0,
        new_users_7d=new_users_7d,
        new_users_30d=new_users_30d,
        new_companies_30d=new_companies_30d,
        active_users_30d=active_users_30d,
        orders_total=orders_total,
        orders_30d=orders_30d,
        gmv_30d=gmv_30d,
        gmv_currency=gmv_currency,
        platform_revenue_total=Decimal(platform_revenue_total).quantize(Decimal("0.01")),
        platform_revenue_30d=Decimal(platform_revenue_30d).quantize(Decimal("0.01")),
        mrr=Decimal(mrr).quantize(Decimal("0.01")),
    )


@router.get("/funnel", response_model=AdminFunnelRead)
async def activation_funnel(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    days: int | None = Query(default=None, ge=1, le=3650),
    email_window_days: int = Query(default=7, ge=1, le=90),
) -> AdminFunnelRead:
    """Where merchants drop off between signing up and their first sale.

    Counts are platform-wide. ``stalled_signups`` are accounts with no workspace
    and ``stalled_workspaces`` are tenants that have never recorded a paid sale.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    user_scope = (User.created_at >= since,) if since else ()
    signups = await db.scalar(select(func.count(User.id)).where(*user_scope)) or 0
    verified = await db.scalar(select(func.count(User.id)).where(User.is_email_verified.is_(True), *user_scope)) or 0

    workspace_query = select(func.count(func.distinct(Company.id)))
    if since:
        workspace_query = workspace_query.where(Company.created_at >= since)
    workspaces = await db.scalar(workspace_query) or 0

    product_query = select(func.count(func.distinct(Product.company_id))).select_from(Product).where(Product.is_sample.is_(False))
    if since:
        product_query = product_query.join(Company, Company.id == Product.company_id).where(Company.created_at >= since)
    with_product = await db.scalar(product_query) or 0

    sale_query = (
        select(func.count(func.distinct(Store.company_id)))
        .select_from(Order)
        .join(Store, Store.id == Order.store_id)
        .where(Order.status == "paid")
    )
    if since:
        sale_query = sale_query.where(Order.created_at >= since)
    with_sale = await db.scalar(sale_query) or 0

    has_membership = select(Membership.id).where(Membership.user_id == User.id).exists()
    stalled_signups = await db.scalar(select(func.count(User.id)).where(~has_membership)) or 0
    has_sale = (
        select(Order.id)
        .join(Store, Store.id == Order.store_id)
        .where(Store.company_id == Company.id, Order.status == "paid")
        .exists()
    )
    stalled_workspaces = await db.scalar(select(func.count(Company.id)).where(~has_sale)) or 0

    stage_defs = [
        ("registered", "Signed up", signups),
        ("verified", "Email verified", verified),
        ("workspace", "Workspace created", workspaces),
        ("first_product", "Added first product", with_product),
        ("first_sale", "Made first sale", with_sale),
    ]
    stages: list[AdminFunnelStageRead] = []
    start = signups
    previous: int | None = None
    for key, label, count in stage_defs:
        stages.append(
            AdminFunnelStageRead(
                key=key,
                label=label,
                count=count,
                conversion_from_previous=(count / previous) if previous else None,
                conversion_from_start=(count / start) if start else None,
            )
        )
        previous = count

    # Per-step email performance. A delivery row means the user was in that
    # stage when the step was sent, so a current match means they moved on.
    drip_config = await mailing_service.load_drip_config(db)
    email_stats: list[AdminFunnelEmailRead] = []
    for step in drip_config["steps"]:
        delivered = await db.scalar(select(func.count(MailingDripDelivery.id)).where(MailingDripDelivery.step_id == step["id"])) or 0
        advanced = 0
        advance = mailing_service.audience_advance_subquery(step["audience"])
        if delivered and advance is not None:
            advanced = await db.scalar(
                select(func.count())
                .select_from(MailingDripDelivery)
                .join(advance, advance.c.user_id == MailingDripDelivery.user_id)
                .where(
                    MailingDripDelivery.step_id == step["id"],
                    advance.c.advance_at > MailingDripDelivery.sent_at,
                    advance.c.advance_at <= MailingDripDelivery.sent_at + func.make_interval(0, 0, 0, email_window_days),
                )
            ) or 0
        email_stats.append(
            AdminFunnelEmailRead(
                step_id=step["id"],
                audience=step["audience"],
                subject=step["subject"],
                delivered=delivered,
                advanced=advanced,
                rate=(advanced / delivered) if delivered else None,
                window_days=email_window_days,
            )
        )

    # Time from workspace creation to the first paid sale, over companies created
    # in the selected window that have sold at least once.
    ttf_scope = (Company.created_at >= since,) if since else ()
    ttf_rows = await db.execute(
        select(Company.created_at, func.min(Order.created_at))
        .select_from(Company)
        .join(Store, Store.company_id == Company.id)
        .join(Order, (Order.store_id == Store.id) & (Order.status == "paid"))
        .where(*ttf_scope)
        .group_by(Company.id, Company.created_at)
    )
    durations = sorted(
        (first_sale - created).total_seconds() / 3600
        for created, first_sale in ttf_rows.all()
        if created is not None and first_sale is not None
    )
    time_to_first_sale = AdminTimeToFirstSaleRead(
        sample=len(durations),
        median_hours=round(median(durations), 2) if durations else None,
        p90_hours=round(durations[int(0.9 * (len(durations) - 1))], 2) if durations else None,
    )

    return AdminFunnelRead(window_days=days, stages=stages, stalled_signups=stalled_signups, stalled_workspaces=stalled_workspaces, time_to_first_sale=time_to_first_sale, email=email_stats)


@router.get("/sales-analytics", response_model=AdminSalesAnalyticsRead)
async def sales_analytics(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=3650),
) -> AdminSalesAnalyticsRead:
    """Platform-wide sales and inventory analytics for a rolling window.

    Sales figures are reported for the single busiest currency in the window so
    amounts in different currencies are never summed together.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    currency_rows = (
        await db.execute(
            select(Order.currency_code, func.coalesce(func.sum(Order.total), 0))
            .where(Order.status == "paid", Order.created_at >= since)
            .group_by(Order.currency_code)
        )
    ).all()
    gmv_currency = "USD"
    best = Decimal("0")
    for code, amount in currency_rows:
        amount = Decimal(amount or 0)
        if amount > best:
            best, gmv_currency = amount, code

    paid_in_window = (Order.status == "paid", Order.currency_code == gmv_currency, Order.created_at >= since)
    paid_all = (Order.status == "paid", Order.currency_code == gmv_currency)

    orders_total = await db.scalar(select(func.count(Order.id)).where(*paid_all)) or 0
    orders_window = await db.scalar(select(func.count(Order.id)).where(*paid_in_window)) or 0
    gmv_total = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*paid_all)) or Decimal("0")
    gmv_window = await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*paid_in_window)) or Decimal("0")
    average_order_value = (Decimal(gmv_window) / orders_window) if orders_window else Decimal("0")
    refunds_window = await db.scalar(select(func.coalesce(func.sum(Refund.total), 0)).where(Refund.currency_code == gmv_currency, Refund.created_at >= since)) or Decimal("0")
    refund_count_window = await db.scalar(select(func.count(Refund.id)).where(Refund.currency_code == gmv_currency, Refund.created_at >= since)) or 0

    company_rows = (
        await db.execute(
            select(Store.company_id, Company.name, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
            .select_from(Order)
            .join(Store, Store.id == Order.store_id)
            .join(Company, Company.id == Store.company_id)
            .where(*paid_in_window)
            .group_by(Store.company_id, Company.name)
            .order_by(func.coalesce(func.sum(Order.total), 0).desc())
            .limit(5)
        )
    ).all()
    top_companies = [
        AdminSalesRankRead(id=company_id, name=name, orders=count or 0, gmv=Decimal(amount or 0).quantize(Decimal("0.01")))
        for company_id, name, count, amount in company_rows
    ]

    store_rows = (
        await db.execute(
            select(Store.id, Store.name, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
            .select_from(Order)
            .join(Store, Store.id == Order.store_id)
            .where(*paid_in_window)
            .group_by(Store.id, Store.name)
            .order_by(func.coalesce(func.sum(Order.total), 0).desc())
            .limit(5)
        )
    ).all()
    top_stores = [
        AdminSalesRankRead(id=store_id, name=name, orders=count or 0, gmv=Decimal(amount or 0).quantize(Decimal("0.01")))
        for store_id, name, count, amount in store_rows
    ]

    product_rows = (
        await db.execute(
            select(OrderItem.product_name, OrderItem.sku, func.coalesce(func.sum(OrderItem.quantity), 0), func.coalesce(func.sum(OrderItem.line_total), 0))
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*paid_in_window)
            .group_by(OrderItem.product_name, OrderItem.sku)
            .order_by(func.coalesce(func.sum(OrderItem.line_total), 0).desc())
            .limit(10)
        )
    ).all()
    top_products = [
        AdminSalesProductRead(product_name=name, sku=sku, quantity=Decimal(quantity or 0), revenue=Decimal(revenue or 0).quantize(Decimal("0.01")))
        for name, sku, quantity, revenue in product_rows
    ]

    method_rows = (
        await db.execute(
            select(OrderTender.method, func.count(func.distinct(OrderTender.order_id)), func.coalesce(func.sum(OrderTender.base_amount), 0))
            .select_from(OrderTender)
            .join(Order, Order.id == OrderTender.order_id)
            .where(*paid_in_window)
            .group_by(OrderTender.method)
            .order_by(func.count(func.distinct(OrderTender.order_id)).desc())
        )
    ).all()
    payment_methods = [
        AdminSalesMethodRead(method=method, orders=count or 0, amount=Decimal(amount or 0).quantize(Decimal("0.01")))
        for method, count, amount in method_rows
    ]

    inventory_value = await db.scalar(
        select(func.coalesce(func.sum(InventoryBalance.on_hand * Product.cost_price), 0))
        .select_from(InventoryBalance)
        .join(Product, Product.id == InventoryBalance.product_id)
        .where(Product.is_active.is_(True), Product.is_sample.is_(False))
    ) or Decimal("0")
    # Seeded demo rows are excluded so platform-wide stock figures reflect real
    # merchant inventory, not sample items no one actually stocked. Variant
    # products keep their stock in variant_inventory_balances and leave the
    # product-level row at zero, so count simple products and variants separately.
    simple_product = ~select(ProductVariant.id).where(ProductVariant.product_id == Product.id).exists()
    low_stock_count = (
        await db.scalar(
            select(func.count(InventoryBalance.product_id))
            .join(Product, Product.id == InventoryBalance.product_id)
            .where(
                Product.is_sample.is_(False),
                simple_product,
                InventoryBalance.on_hand > 0,
                InventoryBalance.on_hand <= InventoryBalance.reorder_point,
            )
        )
        or 0
    ) + (
        await db.scalar(
            select(func.count(VariantInventoryBalance.variant_id))
            .join(ProductVariant, ProductVariant.id == VariantInventoryBalance.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(
                Product.is_sample.is_(False),
                VariantInventoryBalance.on_hand > 0,
                VariantInventoryBalance.on_hand <= VariantInventoryBalance.reorder_point,
            )
        )
        or 0
    )
    out_of_stock_count = (
        await db.scalar(
            select(func.count(InventoryBalance.product_id))
            .join(Product, Product.id == InventoryBalance.product_id)
            .where(Product.is_sample.is_(False), simple_product, InventoryBalance.on_hand <= 0)
        )
        or 0
    ) + (
        await db.scalar(
            select(func.count(VariantInventoryBalance.variant_id))
            .join(ProductVariant, ProductVariant.id == VariantInventoryBalance.variant_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .where(Product.is_sample.is_(False), VariantInventoryBalance.on_hand <= 0)
        )
        or 0
    )
    active_products = await db.scalar(select(func.count(Product.id)).where(Product.is_active.is_(True), Product.is_sample.is_(False))) or 0

    return AdminSalesAnalyticsRead(
        window_days=days,
        summary=AdminSalesSummaryRead(
            orders_total=orders_total,
            orders_window=orders_window,
            gmv_total=Decimal(gmv_total).quantize(Decimal("0.01")),
            gmv_window=Decimal(gmv_window).quantize(Decimal("0.01")),
            gmv_currency=gmv_currency,
            average_order_value=Decimal(average_order_value).quantize(Decimal("0.01")),
            refunds_window=Decimal(refunds_window).quantize(Decimal("0.01")),
            refund_count_window=refund_count_window,
        ),
        top_companies=top_companies,
        top_stores=top_stores,
        top_products=top_products,
        payment_methods=payment_methods,
        inventory=AdminInventorySummaryRead(
            inventory_value=Decimal(inventory_value).quantize(Decimal("0.01")),
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
            active_products=active_products,
        ),
    )


@router.get("/search", response_model=AdminSearchRead)
async def global_search(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=5, ge=1, le=25),
) -> AdminSearchRead:
    """Search users, companies and stores by name or email."""
    term = q.strip()
    if len(term) < 2:
        return AdminSearchRead(query=term)
    like = f"%{term}%"

    user_rows = (
        await db.execute(select(User).where(or_(User.email.ilike(like), User.full_name.ilike(like))).order_by(User.created_at.desc()).limit(limit))
    ).scalars().all()
    users = [AdminSearchUserRead(id=user.id, email=user.email, full_name=user.full_name, platform_role=user.platform_role, is_active=user.is_active) for user in user_rows]

    company_rows = (await db.execute(select(Company).where(Company.name.ilike(like)).order_by(Company.created_at.desc()).limit(limit))).scalars().all()
    companies = []
    for company in company_rows:
        subscription = (await db.execute(select(Subscription).where(Subscription.company_id == company.id).order_by(Subscription.created_at.desc()).limit(1))).scalars().first()
        companies.append(AdminSearchCompanyRead(id=company.id, name=company.name, country=company.country, is_active=company.is_active, plan_code=subscription.plan_code if subscription else None))

    store_rows = (
        await db.execute(
            select(Store, Company.name)
            .join(Company, Company.id == Store.company_id)
            .where(or_(Store.name.ilike(like), Company.name.ilike(like)))
            .order_by(Store.created_at.desc())
            .limit(limit)
        )
    ).all()
    stores = [AdminSearchStoreRead(id=store.id, name=store.name, company_id=store.company_id, company_name=company_name, is_active=store.is_active) for store, company_name in store_rows]

    return AdminSearchRead(query=term, users=users, companies=companies, stores=stores)


@router.get("/export/users.csv")
async def export_users_csv(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> Response:
    """Download every account as CSV."""
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "email", "full_name", "is_active", "is_email_verified", "platform_role", "created_at"])
    for user in users:
        writer.writerow([user.id, user.email, user.full_name, user.is_active, user.is_email_verified, user.platform_role or "", user.created_at.isoformat() if user.created_at else ""])
    return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="users.csv"'})


@router.get("/export/companies.csv")
async def export_companies_csv(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> Response:
    """Download every tenant with its plan state as CSV."""
    companies = (await db.execute(select(Company).order_by(Company.created_at.desc()))).scalars().all()
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "name", "country", "vertical", "default_currency_code", "is_active", "store_count", "member_count", "plan_code", "subscription_status", "created_at"])
    for company in companies:
        store_count = await db.scalar(select(func.count(Store.id)).where(Store.company_id == company.id)) or 0
        member_count = await db.scalar(select(func.count(Membership.id)).where(Membership.company_id == company.id, Membership.status == "active")) or 0
        subscription = (await db.execute(select(Subscription).where(Subscription.company_id == company.id).order_by(Subscription.created_at.desc()).limit(1))).scalars().first()
        writer.writerow([company.id, company.name, company.country, company.vertical, company.default_currency_code, company.is_active, store_count, member_count, subscription.plan_code if subscription else "", subscription.status if subscription else "", company.created_at.isoformat() if company.created_at else ""])
    return Response(content=buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="companies.csv"'})


@router.get("/retention", response_model=AdminRetentionRead)
async def retention(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    weeks: int = Query(default=8, ge=2, le=52),
) -> AdminRetentionRead:
    """Weekly engagement and signup-cohort activation.

    Activation is a first paid sale within 28 days of the workspace being
    created. GMV is reported for the busiest currency in the window.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    current_week_start = today - timedelta(days=today.weekday())
    week_dates = [current_week_start - timedelta(weeks=index) for index in range(weeks - 1, -1, -1)]
    earliest = datetime.combine(week_dates[0], datetime.min.time(), tzinfo=timezone.utc)

    currency_rows = (
        await db.execute(
            select(Order.currency_code, func.coalesce(func.sum(Order.total), 0))
            .where(Order.status == "paid", Order.created_at >= earliest)
            .group_by(Order.currency_code)
        )
    ).all()
    gmv_currency = "USD"
    best = Decimal("0")
    for code, amount in currency_rows:
        amount = Decimal(amount or 0)
        if amount > best:
            best, gmv_currency = amount, code

    order_week = func.date_trunc("week", Order.created_at)
    order_rows = (
        await db.execute(
            select(order_week, func.count(func.distinct(Order.store_id)), func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
            .where(Order.status == "paid", Order.currency_code == gmv_currency, Order.created_at >= earliest)
            .group_by(order_week)
        )
    ).all()
    stores_by_week: dict = {}
    orders_by_week: dict = {}
    gmv_by_week: dict = {}
    for week_value, store_count, order_count, amount in order_rows:
        key = week_value.date()
        stores_by_week[key] = store_count or 0
        orders_by_week[key] = order_count or 0
        gmv_by_week[key] = Decimal(amount or 0).quantize(Decimal("0.01"))

    user_week = func.date_trunc("week", PlatformActivity.created_at)
    user_rows = (
        await db.execute(
            select(user_week, func.count(func.distinct(PlatformActivity.user_id)))
            .where(PlatformActivity.created_at >= earliest, PlatformActivity.user_id.is_not(None))
            .group_by(user_week)
        )
    ).all()
    users_by_week = {week_value.date(): count or 0 for week_value, count in user_rows}

    weekly = [
        AdminRetentionWeekRead(
            week_start=week_date,
            active_stores=stores_by_week.get(week_date, 0),
            active_users=users_by_week.get(week_date, 0),
            orders=orders_by_week.get(week_date, 0),
            gmv=gmv_by_week.get(week_date, Decimal("0.00")),
        )
        for week_date in week_dates
    ]

    first_order = (
        select(Store.company_id.label("company_id"), func.min(Order.created_at).label("first_paid"))
        .select_from(Order)
        .join(Store, Store.id == Order.store_id)
        .where(Order.status == "paid")
        .group_by(Store.company_id)
        .subquery()
    )
    cohort_week = func.date_trunc("week", Company.created_at)
    activated_expr = func.count(Company.id).filter(first_order.c.first_paid <= Company.created_at + timedelta(days=28))
    cohort_rows = (
        await db.execute(
            select(cohort_week, func.count(Company.id), activated_expr)
            .select_from(Company)
            .outerjoin(first_order, first_order.c.company_id == Company.id)
            .where(Company.created_at >= earliest)
            .group_by(cohort_week)
            .order_by(cohort_week)
        )
    ).all()
    cohorts = [
        AdminRetentionCohortRead(
            cohort_start=week_value.date(),
            companies=companies or 0,
            activated=activated or 0,
            activation_rate=((activated or 0) / companies) if companies else None,
        )
        for week_value, companies, activated in cohort_rows
    ]

    company_orders = (
        select(Store.company_id.label("company_id"), func.count(Order.id).label("orders"))
        .select_from(Order)
        .join(Store, Store.id == Order.store_id)
        .where(Order.status == "paid")
        .group_by(Store.company_id)
        .subquery()
    )
    active_companies = await db.scalar(select(func.count()).select_from(company_orders)) or 0
    repeat_companies = await db.scalar(select(func.count()).select_from(company_orders).where(company_orders.c.orders >= 2)) or 0
    total_orders = await db.scalar(select(func.count(Order.id)).where(Order.status == "paid")) or 0
    repeat_rate = (repeat_companies / active_companies) if active_companies else None
    average_orders = (total_orders / active_companies) if active_companies else 0.0

    return AdminRetentionRead(
        weeks=weeks,
        gmv_currency=gmv_currency,
        active_companies=active_companies,
        repeat_rate=repeat_rate,
        average_orders_per_active_company=average_orders,
        weekly=weekly,
        cohorts=cohorts,
    )


@router.get("/attention", response_model=AdminAttentionRead)
async def attention(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminAttentionRead:
    """Snapshot of items that likely need the platform team's attention."""
    now = datetime.now(timezone.utc)
    since_30d = now - timedelta(days=30)
    soon = now + timedelta(days=7)

    failed_payments = await db.scalar(
        select(func.count(BillingPayment.id)).where(BillingPayment.status.in_(("failed", "expired")), BillingPayment.created_at >= since_30d)
    ) or 0
    stuck_payments = await db.scalar(
        select(func.count(BillingPayment.id)).where(BillingPayment.status == "pending", BillingPayment.created_at < now - timedelta(hours=24))
    ) or 0
    expiring = await db.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == "active",
            Subscription.ends_at.is_not(None),
            Subscription.ends_at > now,
            Subscription.ends_at <= soon,
        )
    ) or 0

    has_sale = select(Order.id).join(Store, Store.id == Order.store_id).where(Store.company_id == Company.id, Order.status == "paid").exists()
    never_sold = await db.scalar(select(func.count(Company.id)).where(~has_sale, Company.created_at <= since_30d)) or 0

    recent_activity = select(PlatformActivity.id).where(PlatformActivity.company_id == Company.id, PlatformActivity.created_at >= since_30d).exists()
    inactive = await db.scalar(select(func.count(Company.id)).where(~recent_activity, Company.created_at <= since_30d)) or 0

    items = [
        AdminAttentionItemRead(
            kind="failed_payments",
            label="Failed or expired plan payments (30 days)",
            count=failed_payments,
            severity="critical" if failed_payments else "warning",
            page="billing-payments",
        ),
        AdminAttentionItemRead(kind="stuck_payments", label="Checkouts pending over 24 hours", count=stuck_payments, severity="warning", page="billing-payments"),
        AdminAttentionItemRead(kind="expiring_subscriptions", label="Subscriptions ending within 7 days", count=expiring, severity="warning", page="subscriptions"),
        AdminAttentionItemRead(kind="never_sold", label="Workspaces older than 30 days with no sale", count=never_sold, severity="warning", page="companies"),
        AdminAttentionItemRead(kind="inactive", label="Workspaces with no activity in 30 days", count=inactive, severity="warning", page="companies"),
    ]
    return AdminAttentionRead(generated_at=now, items=items)


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
    user_ids = [user.id for user in users]
    last_logins: dict = {}
    if user_ids:
        last_logins = {
            row_user_id: last_used
            for row_user_id, last_used in (
                await db.execute(
                    select(AuthSession.user_id, func.max(AuthSession.last_used_at))
                    .where(AuthSession.user_id.in_(user_ids))
                    .group_by(AuthSession.user_id)
                )
            ).all()
        }
    output = []
    for user in users:
        company_count = await db.scalar(select(func.count(Membership.id)).where(Membership.user_id == user.id, Membership.status == "active"))
        output.append(AdminUserRead(id=user.id, email=user.email, full_name=user.full_name, is_active=user.is_active, is_email_verified=user.is_email_verified, platform_role=user.platform_role, created_at=user.created_at, company_count=company_count or 0, last_login=last_logins.get(user.id)))
    return output


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(user_id: UUID, payload: AdminUserUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> AdminUserRead:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == actor.id and payload.is_active is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate your own account")
    demoting = payload.platform_role is not None and payload.platform_role != "super_admin"
    deactivating = payload.is_active is False
    if user.platform_role == "super_admin" and (demoting or deactivating):
        remaining = await db.scalar(select(func.count(User.id)).where(User.platform_role == "super_admin", User.is_active.is_(True), User.id != user.id)) or 0
        if remaining == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one active super admin must remain")
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


@router.get("/users/{user_id}", response_model=AdminUserDetailRead)
async def get_user_detail(user_id: UUID, _: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminUserDetailRead:
    """Full profile of one account: roles, live sessions and recent activity."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership_rows = (
        await db.execute(
            select(Membership, Company.name)
            .join(Company, Company.id == Membership.company_id)
            .where(Membership.user_id == user.id)
            .order_by(Membership.created_at.desc())
        )
    ).all()
    memberships = [
        AdminMembershipRead(company_id=membership.company_id, company_name=company_name, role=membership.role, status=membership.status, created_at=membership.created_at)
        for membership, company_name in membership_rows
    ]
    company_count = sum(1 for membership in memberships if membership.status == "active")

    now = datetime.now(timezone.utc)
    session_rows = (
        await db.execute(
            select(AuthSession)
            .where(AuthSession.user_id == user.id)
            .order_by(AuthSession.last_used_at.desc())
            .limit(10)
        )
    ).scalars().all()
    sessions = [
        AdminUserSessionRead(
            id=session.id,
            user_agent=session.user_agent,
            ip_address=session.ip_address,
            created_at=session.created_at,
            last_used_at=session.last_used_at,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
            active=session.revoked_at is None and session.expires_at > now,
        )
        for session in session_rows
    ]
    last_login = sessions[0].last_used_at if sessions else None

    activity_rows = (
        await db.execute(
            select(PlatformActivity)
            .where(PlatformActivity.user_id == user.id)
            .order_by(PlatformActivity.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    recent_activity = [
        AdminActivityRead(
            id=activity.id,
            source="platform",
            event_type=activity.event_type,
            title=activity_title(activity.event_type),
            actor_email=activity.email,
            user_id=activity.user_id,
            company_id=activity.company_id,
            store_id=activity.store_id,
            details=activity.details,
            created_at=activity.created_at,
        )
        for activity in activity_rows
    ]

    return AdminUserDetailRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        platform_role=user.platform_role,
        created_at=user.created_at,
        last_login=last_login,
        company_count=company_count,
        memberships=memberships,
        sessions=sessions,
        recent_activity=recent_activity,
    )


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


@router.get("/companies/{company_id}", response_model=AdminCompanyDetailRead)
async def get_company_detail(company_id: UUID, _: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminCompanyDetailRead:
    """Business health of one tenant: people, plan, money and activity."""
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    store_rows = (await db.execute(select(Store).where(Store.company_id == company.id).order_by(Store.created_at))).scalars().all()
    stores = [AdminCompanyStoreRead(id=store.id, name=store.name, is_active=store.is_active, currency_code=store.currency_code, created_at=store.created_at) for store in store_rows]

    member_rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.company_id == company.id)
            .order_by(Membership.created_at)
        )
    ).all()
    members = [
        AdminCompanyMemberRead(user_id=membership.user_id, email=user.email, full_name=user.full_name, role=membership.role, status=membership.status, created_at=membership.created_at)
        for membership, user in member_rows
    ]

    customer_count = await db.scalar(select(func.count(Customer.id)).where(Customer.company_id == company.id)) or 0
    product_count = await db.scalar(select(func.count(Product.id)).where(Product.company_id == company.id)) or 0

    subscription = (await db.execute(select(Subscription).where(Subscription.company_id == company.id).order_by(Subscription.created_at.desc()).limit(1))).scalars().first()

    revenue_total = await db.scalar(
        select(func.coalesce(func.sum(BillingPayment.amount), 0)).where(BillingPayment.company_id == company.id, BillingPayment.status == "paid")
    ) or Decimal("0")

    orders_total = await db.scalar(
        select(func.count(Order.id)).join(Store, Store.id == Order.store_id).where(Store.company_id == company.id, Order.status == "paid")
    ) or 0
    gmv_total = Decimal("0.00")
    gmv_currency = company.default_currency_code
    gmv_rows = (
        await db.execute(
            select(Order.currency_code, func.coalesce(func.sum(Order.total), 0))
            .join(Store, Store.id == Order.store_id)
            .where(Store.company_id == company.id, Order.status == "paid")
            .group_by(Order.currency_code)
        )
    ).all()
    for code, amount in gmv_rows:
        amount = Decimal(amount or 0)
        if amount > gmv_total:
            gmv_total, gmv_currency = amount, code
    gmv_total = gmv_total.quantize(Decimal("0.01"))

    activity_rows = (
        await db.execute(
            select(PlatformActivity)
            .where(PlatformActivity.company_id == company.id)
            .order_by(PlatformActivity.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    recent_activity = [
        AdminActivityRead(
            id=activity.id,
            source="platform",
            event_type=activity.event_type,
            title=activity_title(activity.event_type),
            actor_email=activity.email,
            user_id=activity.user_id,
            company_id=activity.company_id,
            store_id=activity.store_id,
            details=activity.details,
            created_at=activity.created_at,
        )
        for activity in activity_rows
    ]

    return AdminCompanyDetailRead(
        id=company.id,
        name=company.name,
        country=company.country,
        vertical=company.vertical,
        default_currency_code=company.default_currency_code,
        is_active=company.is_active,
        created_at=company.created_at,
        store_count=len(stores),
        active_store_count=sum(1 for store in stores if store.is_active),
        member_count=len(members),
        active_member_count=sum(1 for member in members if member.status == "active"),
        customer_count=customer_count,
        product_count=product_count,
        plan_code=subscription.plan_code if subscription else None,
        subscription_status=subscription.status if subscription else None,
        billing_cycle=subscription.billing_cycle if subscription else None,
        subscription_ends_at=subscription.ends_at if subscription else None,
        revenue_total=Decimal(revenue_total).quantize(Decimal("0.01")),
        orders_total=orders_total,
        gmv_total=gmv_total,
        gmv_currency=gmv_currency,
        last_activity=activity_rows[0].created_at if activity_rows else None,
        stores=stores,
        members=members,
        recent_activity=recent_activity,
    )


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


@router.get("/chamabapay-settings", response_model=ChmabaPaySettingsRead)
async def get_chamabapay_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> ChmabaPaySettingsRead:
    cfg = await load_payment_settings(db)
    configured = cfg.get("chamabapay_platform_store_id")
    resolved = configured
    if resolved is None:
        try:
            provider = await active_payment_provider(db)
            resolved = await resolve_platform_store_id(db, provider)
        except Exception:  # a provider problem must never break the admin settings panel
            resolved = None
    return ChmabaPaySettingsRead(
        mode=cfg.get("chamabapay_mode") or "mock",
        api_url=cfg.get("chamabapay_api_url") or "https://pay.chmaba.com",
        platform_store_id=configured,
        resolved_platform_store_id=resolved,
        api_key_set=bool(cfg.get("chamabapay_api_key")),
        webhook_secret_set=bool(cfg.get("chamabapay_webhook_secret")),
        api_key_preview=_mask_secret(cfg.get("chamabapay_api_key")),
        webhook_secret_preview=_mask_secret(cfg.get("chamabapay_webhook_secret")),
        environment=settings.environment,
    )


@router.patch("/chamabapay-settings", response_model=ChmabaPaySettingsRead)
async def update_chamabapay_settings(payload: ChmabaPaySettingsUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> ChmabaPaySettingsRead:
    field_map = {
        "mode": "chamabapay_mode",
        "api_url": "chamabapay_api_url",
        "api_key": "chamabapay_api_key",
        "webhook_secret": "chamabapay_webhook_secret",
        "platform_store_id": "chamabapay_platform_store_id",
    }
    updates: dict[str, str | None] = {}
    for field_name, key in field_map.items():
        if field_name in payload.model_fields_set:
            updates[key] = getattr(payload, field_name)
    if updates:
        await save_payment_settings(db, updates)
        await audit(db, actor, "admin.chamabapay_settings_updated", "platform", None, {"fields": sorted(updates.keys())})
        await db.commit()
    return await get_chamabapay_settings(_=None, db=db)


@router.post("/chamabapay-settings/reveal", response_model=ChmabaPaySecretRevealRead)
async def reveal_chamabapay_secret(payload: ChmabaPaySecretRevealRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> ChmabaPaySecretRevealRead:
    """Return the stored secret for a platform admin. Audited."""
    cfg = await load_payment_settings(db)
    key = "chamabapay_api_key" if payload.field == "api_key" else "chamabapay_webhook_secret"
    value = cfg.get(key)
    await audit(db, actor, "admin.chamabapay_secret_revealed", "platform", None, {"field": payload.field})
    await db.commit()
    return ChmabaPaySecretRevealRead(field=payload.field, value=value)


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


@router.get("/billing-payments", response_model=list[AdminBillingPaymentRead])
async def list_billing_payments(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    payment_status: str | None = Query(default=None, alias="status"),
    company_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[AdminBillingPaymentRead]:
    """Read-only view of plan-fee payments for support. Never returns secrets."""
    query = (
        select(BillingPayment, Company.name)
        .outerjoin(Company, Company.id == BillingPayment.company_id)
        .order_by(BillingPayment.created_at.desc())
        .limit(validate_limit(limit))
    )
    if payment_status:
        query = query.where(BillingPayment.status == payment_status)
    if company_id:
        query = query.where(BillingPayment.company_id == company_id)
    rows = (await db.execute(query)).all()
    return [
        AdminBillingPaymentRead(
            id=payment.id,
            company_id=payment.company_id,
            company_name=company_name,
            subscription_id=payment.subscription_id,
            plan_code=payment.plan_code,
            billing_cycle=payment.billing_cycle,
            amount=payment.amount,
            currency_code=payment.currency_code,
            provider=payment.provider,
            status=payment.status,
            external_id=payment.external_id,
            reference_id=payment.reference_id,
            created_at=payment.created_at,
            approved_at=payment.approved_at,
            fulfilled_at=payment.fulfilled_at,
            period_start=payment.period_start,
            period_end=payment.period_end,
        )
        for payment, company_name in rows
    ]


@router.get("/billing-analytics", response_model=AdminBillingAnalyticsRead)
async def billing_analytics(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AdminBillingAnalyticsRead:
    """Revenue and plan health for the platform's own plan billing.

    MRR is list price across active, non-free subscriptions; ARR is 12x that.
    Revenue is counted when a payment was approved/fulfilled, and the success
    rate ignores still-pending checkouts.
    """
    now = datetime.now(timezone.utc)
    since_30d = now - timedelta(days=30)
    active_filter = (
        Subscription.status == "active",
        Subscription.plan_code != "free",
        Subscription.starts_at <= now,
        or_(Subscription.ends_at.is_(None), Subscription.ends_at > now),
    )

    mrr = await db.scalar(
        select(func.coalesce(func.sum(Plan.monthly_price), 0))
        .select_from(Subscription)
        .join(Plan, Plan.code == Subscription.plan_code)
        .where(*active_filter)
    ) or Decimal("0")
    mrr = Decimal(mrr).quantize(Decimal("0.01"))

    active_subscriptions = await db.scalar(select(func.count(Subscription.id)).where(*active_filter)) or 0
    pending_subscriptions = await db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "pending")) or 0

    paid_at = func.coalesce(BillingPayment.fulfilled_at, BillingPayment.approved_at, BillingPayment.created_at)
    revenue_total = await db.scalar(select(func.coalesce(func.sum(BillingPayment.amount), 0)).where(BillingPayment.status == "paid")) or Decimal("0")
    revenue_30d = await db.scalar(select(func.coalesce(func.sum(BillingPayment.amount), 0)).where(BillingPayment.status == "paid", paid_at >= since_30d)) or Decimal("0")
    refunds_total = await db.scalar(select(func.coalesce(func.sum(BillingRefund.amount), 0))) or Decimal("0")

    status_rows = (
        await db.execute(
            select(BillingPayment.status, func.count(BillingPayment.id), func.coalesce(func.sum(BillingPayment.amount), 0)).group_by(BillingPayment.status)
        )
    ).all()
    status_breakdown = [
        AdminBillingStatusCountRead(status=row_status, payments=count or 0, amount=Decimal(amount or 0).quantize(Decimal("0.01")))
        for row_status, count, amount in status_rows
    ]
    status_counts = {row.status: row.payments for row in status_breakdown}
    payments_total = sum(status_counts.values())
    payments_paid = status_counts.get("paid", 0)
    payments_pending = status_counts.get("pending", 0)
    terminal = sum(status_counts.get(code, 0) for code in ("paid", "failed", "expired", "canceled"))
    payment_success_rate = (payments_paid / terminal) if terminal else None

    plan_rows = (
        await db.execute(
            select(Subscription.plan_code, func.count(Subscription.id), func.coalesce(func.sum(Plan.monthly_price), 0))
            .join(Plan, Plan.code == Subscription.plan_code)
            .where(*active_filter)
            .group_by(Subscription.plan_code)
            .order_by(func.count(Subscription.id).desc())
        )
    ).all()
    plan_mix = [
        AdminBillingPlanMixRead(plan_code=plan_code, subscriptions=count or 0, mrr=Decimal(amount or 0).quantize(Decimal("0.01")))
        for plan_code, count, amount in plan_rows
    ]

    cycle_rows = (
        await db.execute(
            select(Subscription.billing_cycle, func.count(Subscription.id)).where(*active_filter).group_by(Subscription.billing_cycle)
        )
    ).all()
    cycle_mix = [AdminBillingCycleMixRead(billing_cycle=billing_cycle, subscriptions=count or 0) for billing_cycle, count in cycle_rows]

    return AdminBillingAnalyticsRead(
        mrr=mrr,
        arr=(mrr * 12).quantize(Decimal("0.01")),
        revenue_total=Decimal(revenue_total).quantize(Decimal("0.01")),
        revenue_30d=Decimal(revenue_30d).quantize(Decimal("0.01")),
        refunds_total=Decimal(refunds_total).quantize(Decimal("0.01")),
        payments_total=payments_total,
        payments_paid=payments_paid,
        payments_pending=payments_pending,
        payment_success_rate=payment_success_rate,
        active_subscriptions=active_subscriptions,
        pending_subscriptions=pending_subscriptions,
        plan_mix=plan_mix,
        cycle_mix=cycle_mix,
        status_breakdown=status_breakdown,
    )


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


@router.get("/activity", response_model=list[AdminActivityRead])
async def list_activity(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    source: str = Query(default="all", pattern="^(all|platform|admin)$"),
    event_type: str | None = Query(default=None, max_length=60),
    user_id: UUID | None = Query(default=None),
    company_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    days: int | None = Query(default=None, ge=1, le=3650),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AdminActivityRead]:
    """Unified, newest-first feed of everything happening on the platform.

    Combines cross-tenant ``PlatformActivity`` events (signups, logins, sales,
    refunds, transfers, invitations) with platform-admin ``AuditLog``
    actuations, so the control room is no longer limited to admin changes.
    ``company_id`` and ``store_id`` narrow the platform feed only; admin
    actuations carry an ``entity_type`` instead.
    """
    capped = validate_limit(limit)
    rows: list[AdminActivityRead] = []
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    if source in ("all", "platform"):
        query = select(PlatformActivity).order_by(PlatformActivity.created_at.desc()).limit(capped)
        if event_type:
            query = query.where(PlatformActivity.event_type == event_type)
        if user_id:
            query = query.where(PlatformActivity.user_id == user_id)
        if company_id:
            query = query.where(PlatformActivity.company_id == company_id)
        if store_id:
            query = query.where(PlatformActivity.store_id == store_id)
        if since:
            query = query.where(PlatformActivity.created_at >= since)
        if search:
            like = f"%{search}%"
            query = query.where(or_(PlatformActivity.email.ilike(like), PlatformActivity.event_type.ilike(like)))
        for activity in (await db.execute(query)).scalars().all():
            rows.append(
                AdminActivityRead(
                    id=activity.id,
                    source="platform",
                    event_type=activity.event_type,
                    title=activity_title(activity.event_type),
                    actor_email=activity.email,
                    user_id=activity.user_id,
                    company_id=activity.company_id,
                    store_id=activity.store_id,
                    details=activity.details,
                    created_at=activity.created_at,
                )
            )

    if source in ("all", "admin"):
        query = (
            select(AuditLog, User.email)
            .join(User, User.id == AuditLog.actor_user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(capped)
        )
        if event_type:
            query = query.where(AuditLog.action == event_type)
        if since:
            query = query.where(AuditLog.created_at >= since)
        if search:
            like = f"%{search}%"
            query = query.where(or_(AuditLog.action.ilike(like), AuditLog.entity_type.ilike(like), User.email.ilike(like)))
        for log, email in (await db.execute(query)).all():
            rows.append(
                AdminActivityRead(
                    id=log.id,
                    source="admin",
                    event_type=log.action,
                    title=activity_title(log.action),
                    actor_email=email,
                    entity_type=log.entity_type,
                    entity_id=log.entity_id,
                    details=log.details,
                    created_at=log.created_at,
                )
            )

    rows.sort(key=lambda row: row.created_at, reverse=True)
    return rows[:capped]


@router.post("/billing-payments/{payment_id}/refund", response_model=BillingRefundRead, status_code=status.HTTP_201_CREATED)
async def create_billing_refund(payment_id: UUID, payload: BillingRefundCreateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> BillingRefundRead:
    """Record a support correction against a billing payment.

    Prepaid payments are non-refundable by policy; this only records the
    correction (audited) and never mutates the payment or changes entitlement.
    """
    payment = await db.get(BillingPayment, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing payment not found")
    if payload.amount > payment.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refund cannot exceed the payment amount")
    company_id = payment.company_id
    if company_id is None:
        subscription = await db.get(Subscription, payment.subscription_id)
        company_id = subscription.company_id if subscription else None
    if company_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment is not linked to a company")
    refund = BillingRefund(
        billing_payment_id=payment.id,
        company_id=company_id,
        amount=payload.amount,
        currency_code=payment.currency_code,
        reason=payload.reason,
        provider_reference=payload.provider_reference,
        refunded_by=actor.id,
    )
    db.add(refund)
    await audit(db, actor, "admin.billing_refund_recorded", "billing_payment", payment.id, {"amount": str(payload.amount), "reason": payload.reason})
    await db.commit()
    await db.refresh(refund)
    return BillingRefundRead.model_validate(refund)


# ---------------------------------------------------------------------------
# Outbound mail: SMTP relay or Resend, switchable without a redeploy.
# ---------------------------------------------------------------------------


async def _mail_settings_read(db: AsyncSession) -> MailSettingsRead:
    cfg = await mail_service.load_mail_settings(db)
    raw_key = cfg.get("resend_api_key")
    raw_webhook = cfg.get("resend_webhook_secret")
    return MailSettingsRead(
        provider=mail_service.resolve_provider(cfg),
        providers=mail_service.mail_provider_catalog(),
        from_address=(cfg.get("mail_from") or settings.smtp_from),
        from_name=(cfg.get("mail_from_name") or None),
        reply_to=(cfg.get("mail_reply_to") or None),
        support_inbox=(cfg.get("mail_support_inbox") or None),
        api_key_set=bool(raw_key),
        api_key_preview=_mask_secret(raw_key),
        webhook_secret_set=bool(raw_webhook),
        webhook_secret_preview=_mask_secret(raw_webhook),
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_use_ssl=settings.smtp_use_ssl,
        smtp_username_set=bool(settings.smtp_username),
    )


@router.get("/mail-settings", response_model=MailSettingsRead)
async def get_mail_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> MailSettingsRead:
    return await _mail_settings_read(db)


@router.patch("/mail-settings", response_model=MailSettingsRead)
async def update_mail_settings(payload: MailSettingsUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailSettingsRead:
    field_map = {
        "provider": "mail_provider",
        "resend_api_key": "resend_api_key",
        "resend_webhook_secret": "resend_webhook_secret",
        "from_address": "mail_from",
        "from_name": "mail_from_name",
        "reply_to": "mail_reply_to",
        "support_inbox": "mail_support_inbox",
    }
    updates: dict[str, str | None] = {}
    for field_name, key in field_map.items():
        if field_name in payload.model_fields_set:
            value = getattr(payload, field_name)
            updates[key] = str(value) if value is not None else None
    if updates:
        await mail_service.save_mail_settings(db, updates)
        await audit(db, actor, "admin.mail_settings_updated", "platform", None, {"fields": sorted(updates.keys())})
        await db.commit()
    return await _mail_settings_read(db)


@router.post("/mail-settings/reveal", response_model=MailSecretRevealRead)
async def reveal_mail_secret(payload: MailSecretRevealRequest | None = None, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailSecretRevealRead:
    field = payload.field if payload else "api_key"
    cfg = await mail_service.load_mail_settings(db)
    key = "resend_webhook_secret" if field == "webhook_secret" else "resend_api_key"
    await audit(db, actor, "admin.mail_secret_revealed", "platform", None, {"field": field})
    await db.commit()
    return MailSecretRevealRead(field=field, value=cfg.get(key))


@router.post("/mail-settings/test", response_model=MailTestRead)
async def send_mail_test(payload: MailTestRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailTestRead:
    """Send a test message through the configured provider, reporting the error."""
    cfg = await mail_service.load_mail_settings(db)
    provider = mail_service.resolve_provider(cfg)
    sent = True
    detail: str | None = None
    try:
        html = transactional_email(
            heading="Chmaba test email",
            preview="A test message from the Chmaba admin panel.",
            body=(
                '<p style="margin:0 0 12px 0;">This is a test email from the Chmaba admin panel.</p>'
                '<p style="margin:0;">If you can read it, sending works.</p>'
            ),
            badge="Test",
        )
        await mail_service.send_with_settings(
            cfg,
            recipient=str(payload.to),
            subject="Chmaba test email",
            text=html_to_text(html),
            html=html,
        )
    except Exception as exc:  # surface the provider's error to the operator
        sent, detail = False, str(exc)[:300]
    await audit(db, actor, "admin.mail_test_sent", "platform", None, {"provider": provider, "to": str(payload.to), "sent": sent})
    await db.commit()
    return MailTestRead(sent=sent, provider=provider, detail=detail)


# ---------------------------------------------------------------------------
# Sign-in session length: the platform default and ceiling. Company owners may
# override the default for their own team, always bounded by this maximum.
# ---------------------------------------------------------------------------


async def _session_settings_read(db: AsyncSession) -> SessionSettingsRead:
    default_ttl, max_ttl = await session_policy_service.load_platform_session_policy(db)
    return SessionSettingsRead(
        default_ttl_minutes=default_ttl,
        max_ttl_minutes=max_ttl,
        absolute_max_ttl_minutes=session_policy_service.ABSOLUTE_MAX_TTL_MINUTES,
    )


@router.get("/session-settings", response_model=SessionSettingsRead)
async def get_session_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> SessionSettingsRead:
    return await _session_settings_read(db)


@router.patch("/session-settings", response_model=SessionSettingsRead)
async def update_session_settings(payload: SessionSettingsUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> SessionSettingsRead:
    current_default, current_max = await session_policy_service.load_platform_session_policy(db)
    new_max = payload.max_ttl_minutes if payload.max_ttl_minutes is not None else current_max
    new_default = payload.default_ttl_minutes if payload.default_ttl_minutes is not None else current_default
    if new_max > session_policy_service.ABSOLUTE_MAX_TTL_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum session length cannot exceed {session_policy_service.ABSOLUTE_MAX_TTL_MINUTES} minutes",
        )
    if new_default > new_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Default session length cannot exceed the maximum")
    await session_policy_service.save_platform_session_policy(
        db, default_minutes=payload.default_ttl_minutes, max_minutes=payload.max_ttl_minutes
    )
    await audit(db, actor, "admin.session_settings_updated", "platform", None, {"fields": sorted(payload.model_fields_set)})
    await db.commit()
    return await _session_settings_read(db)


# ---------------------------------------------------------------------------
# Mailing: AI drafting and manual email campaigns for stalled merchants.
# ---------------------------------------------------------------------------


async def _ai_settings_read(db: AsyncSession) -> AISettingsRead:
    cfg = await ai_service.load_ai_settings(db)
    provider, model = ai_service.resolve_provider(cfg)
    raw_key = cfg.get("ai_api_key")
    prices = await ai_pricing.load_prices(db)
    return AISettingsRead(
        provider=provider.code if provider else None,
        model=model or None,
        base_url=(cfg.get("ai_base_url") or (provider.base_url if provider else None)),
        api_key_set=bool(raw_key),
        api_key_preview=_mask_secret(raw_key),
        providers=ai_service.provider_catalog(),
        prices={key: list(value) for key, value in prices.items()},
    )


@router.get("/ai-settings", response_model=AISettingsRead)
async def get_ai_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AISettingsRead:
    return await _ai_settings_read(db)


@router.patch("/ai-settings", response_model=AISettingsRead)
async def update_ai_settings(payload: AISettingsUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> AISettingsRead:
    field_map = {"provider": "ai_provider", "model": "ai_model", "base_url": "ai_base_url", "api_key": "ai_api_key"}
    updates: dict[str, str | None] = {}
    for field_name, key in field_map.items():
        if field_name in payload.model_fields_set:
            updates[key] = getattr(payload, field_name)
    if updates:
        await ai_service.save_ai_settings(db, updates)
    if "prices" in payload.model_fields_set:
        await ai_pricing.save_prices(db, payload.prices)
    if updates or "prices" in payload.model_fields_set:
        await audit(db, actor, "admin.ai_settings_updated", "platform", None, {"fields": sorted(payload.model_fields_set)})
        await db.commit()
    return await _ai_settings_read(db)


@router.post("/ai-settings/reveal", response_model=AISecretRevealRead)
async def reveal_ai_secret(actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> AISecretRevealRead:
    cfg = await ai_service.load_ai_settings(db)
    await audit(db, actor, "admin.ai_secret_revealed", "platform", None, {"field": "api_key"})
    await db.commit()
    return AISecretRevealRead(value=cfg.get("ai_api_key"))


@router.post("/mailing/draft", response_model=AIDraftRead)
async def draft_mailing(payload: AIDraftRequest, _: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AIDraftRead:
    """Turn a short operator instruction into a subject + HTML body to review."""
    audience_note = mailing_service.AUDIENCES.get(payload.audience or "")
    try:
        draft = await ai_service.draft_email(db, instruction=payload.instruction, audience_note=audience_note, tone=payload.tone)
    except ai_service.AINotConfiguredError as exc:
        # A setup problem the operator can fix, not an upstream failure.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return AIDraftRead(**draft)


@router.post("/ai-settings/test", response_model=AITestRead)
async def test_ai_settings(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> AITestRead:
    """Send a tiny prompt to the configured provider and report the outcome."""
    try:
        result = await ai_service.test_ai(db)
    except ai_service.AINotConfiguredError as exc:
        return AITestRead(ok=False, provider=None, model=None, detail=str(exc))
    except ai_service.AIError as exc:
        return AITestRead(ok=False, provider=None, model=None, detail=str(exc))
    return AITestRead(ok=True, provider=result.get("provider"), model=result.get("model"), detail=None)


@router.get("/mailing/audience", response_model=MailingAudienceRead)
async def mailing_audience(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    audience: str = Query(default="no_workspace", max_length=40),
    min_age_hours: int | None = Query(default=24, ge=0, le=8760),
    max_age_days: int | None = Query(default=None, ge=0, le=3650),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
) -> MailingAudienceRead:
    breakdown = await mailing_service.audience_breakdown(db, min_age_hours=min_age_hours, max_age_days=max_age_days)
    recipients = await mailing_service.resolve_recipients(
        db, audience=audience, min_age_hours=min_age_hours, max_age_days=max_age_days, search=search, limit=limit
    )
    rows = []
    for user in recipients:
        company_count = await db.scalar(select(func.count(Membership.id)).where(Membership.user_id == user.id, Membership.status == "active"))
        rows.append(
            MailingRecipientRead(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_email_verified=user.is_email_verified,
                created_at=user.created_at,
                company_count=company_count or 0,
            )
        )
    return MailingAudienceRead(
        segments=[MailingAudienceSegmentRead(**segment) for segment in breakdown["segments"]],
        recipients=rows,
    )


_MAILING_IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
_MAILING_IMAGE_MAX_BYTES = 5 * 1024 * 1024


@router.post("/mailing/images", response_model=MailingImageRead, status_code=status.HTTP_201_CREATED)
async def upload_mailing_image(file: UploadFile = File(...), actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> MailingImageRead:
    """Store an image for use in a mailing and return an absolute URL to embed."""
    content_type = (file.content_type or "").lower()
    suffix = _MAILING_IMAGE_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload a PNG, JPEG, GIF or WebP image")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The uploaded file is empty")
    if len(content) > _MAILING_IMAGE_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Images must be 5 MB or smaller")
    path = store_platform_image(content, suffix)
    base = (settings.api_public_url or settings.frontend_url).rstrip("/")
    await audit(db, actor, "admin.mailing_image_uploaded", "platform", None, {"content_type": content_type, "bytes": len(content)})
    await db.commit()
    return MailingImageRead(url=f"{base}{path}", path=path, content_type=content_type, byte_size=len(content))


@router.get("/mailing/drip", response_model=MailingDripRead)
async def get_mailing_drip(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> MailingDripRead:
    return MailingDripRead(**await mailing_service.load_drip_config(db))


@router.put("/mailing/drip", response_model=MailingDripRead)
async def update_mailing_drip(payload: MailingDripUpdateRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailingDripRead:
    saved = await mailing_service.save_drip_config(db, payload.model_dump())
    await audit(
        db,
        actor,
        "admin.mailing_drip_updated",
        "platform",
        None,
        {"steps": len(saved["steps"]), "enabled": sum(1 for step in saved["steps"] if step["enabled"]), "max_age_days": saved["max_age_days"]},
    )
    await db.commit()
    return MailingDripRead(**saved)


@router.post("/mailing/drip/run", response_model=MailingDripRunRead)
async def run_mailing_drip_now(actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailingDripRunRead:
    """Run the drip now, so an operator can verify it without waiting for cron."""
    result = await mailing_service.run_mailing_drip(db, force=True)
    await audit(db, actor, "admin.mailing_drip_run", "platform", None, result)
    await db.commit()
    return MailingDripRunRead(**result)


@router.post("/mailing/queue/run", response_model=MailingQueueRunRead)
async def run_mailing_queue_now(actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailingQueueRunRead:
    """Flush part of the send queue now instead of waiting for the worker."""
    result = await mailing_service.send_pending_emails(db)
    await audit(db, actor, "admin.mailing_queue_run", "platform", None, result)
    await db.commit()
    return MailingQueueRunRead(**result)


@router.get("/mailing/tokens", response_model=list[MailingTokenRead])
async def list_mailing_tokens(_: User = Depends(get_platform_admin)) -> list[MailingTokenRead]:
    """Personalization placeholders the composer can insert into a message."""
    return [MailingTokenRead(**token) for token in mailing_service.MERGE_TOKENS]


@router.get("/mailing/templates", response_model=list[EmailTemplateRead])
async def list_email_templates(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> list[EmailTemplateRead]:
    rows = (await db.execute(select(EmailTemplate).order_by(EmailTemplate.updated_at.desc()))).scalars().all()
    return [EmailTemplateRead.model_validate(row) for row in rows]


@router.post("/mailing/templates", response_model=EmailTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_email_template(payload: EmailTemplateCreateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> EmailTemplateRead:
    template = EmailTemplate(name=payload.name, subject=payload.subject, body_html=payload.body_html, created_by=actor.id)
    db.add(template)
    await audit(db, actor, "admin.email_template_created", "email_template", None, {"name": template.name})
    await db.commit()
    await db.refresh(template)
    return EmailTemplateRead.model_validate(template)


@router.patch("/mailing/templates/{template_id}", response_model=EmailTemplateRead)
async def update_email_template(template_id: UUID, payload: EmailTemplateUpdateRequest, actor: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db)) -> EmailTemplateRead:
    template = await db.get(EmailTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    for attr in ("name", "subject", "body_html"):
        value = getattr(payload, attr)
        if value is not None:
            setattr(template, attr, value)
    await audit(db, actor, "admin.email_template_updated", "email_template", template.id, {"name": template.name})
    await db.commit()
    await db.refresh(template)
    return EmailTemplateRead.model_validate(template)


@router.delete("/mailing/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_template(template_id: UUID, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> Response:
    template = await db.get(EmailTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    await audit(db, actor, "admin.email_template_deleted", "email_template", template.id, {"name": template.name})
    await db.delete(template)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mailing/send", response_model=MailingSendResultRead)
async def send_mailing(payload: MailingSendRequest, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> MailingSendResultRead:
    if payload.audience not in mailing_service.AUDIENCES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown audience")
    result = await mailing_service.send_campaign(
        db,
        actor_id=actor.id,
        subject=payload.subject,
        body_html=payload.body_html,
        audience=payload.audience,
        template_id=payload.template_id,
        min_age_hours=payload.min_age_hours,
        max_age_days=payload.max_age_days,
        search=payload.search,
        limit=payload.limit,
        only_email=str(payload.test_email) if payload.test_email else None,
    )
    await audit(
        db,
        actor,
        "admin.mailing_sent",
        "platform",
        None,
        {
            "scope": "test" if payload.test_email else "segment",
            "audience": payload.audience,
            "subject": payload.subject[:120],
            "queued": result["queued"],
            "sent": result["sent"],
            "failed": result["failed"],
            "skipped": result["skipped"],
        },
    )
    await db.commit()
    return MailingSendResultRead(**result)


@router.get("/mailing/sends", response_model=list[EmailSendRead])
async def list_email_sends(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db), limit: int = Query(default=100, ge=1, le=200)) -> list[EmailSendRead]:
    rows = (await db.execute(select(EmailSend).order_by(EmailSend.created_at.desc()).limit(validate_limit(limit)))).scalars().all()
    return [EmailSendRead.model_validate(row) for row in rows]


@router.get("/mailing/suppressions", response_model=list[EmailSuppressionRead])
async def list_email_suppressions(_: User = Depends(get_platform_admin), db: AsyncSession = Depends(get_db), limit: int = Query(default=200, ge=1, le=500)) -> list[EmailSuppressionRead]:
    rows = (await db.execute(select(EmailSuppression).order_by(EmailSuppression.created_at.desc()).limit(min(max(limit, 1), 500)))).scalars().all()
    return [EmailSuppressionRead.model_validate(row) for row in rows]


@router.delete("/mailing/suppressions/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_suppression(suppression_id: UUID, actor: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)) -> Response:
    row = await db.get(EmailSuppression, suppression_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression not found")
    await audit(db, actor, "admin.email_suppression_removed", "platform", None, {"email": row.email})
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/support/insights", response_model=SupportInsightsRead)
async def support_insights(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    window_days: int = Query(default=30, ge=1, le=365),
) -> SupportInsightsRead:
    """Roll up support feedback, escalations, content gaps and AI usage.

    Reads the ``support.feedback``, ``support.escalated``, ``support.no_match``
    and ``ai.usage`` activity rows the assistant writes. A run of down-votes, a
    cluster of questions no guide matched, or a spike in token usage is a signal
    for the team.
    """
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        await db.execute(
            select(PlatformActivity)
            .where(PlatformActivity.event_type.in_(("support.feedback", "support.escalated", "support.no_match", "ai.usage")))
            .where(PlatformActivity.created_at >= since)
            .order_by(PlatformActivity.created_at.desc())
        )
    ).scalars().all()

    feedback_up = 0
    feedback_down = 0
    escalations = 0
    counts: dict[str, dict[str, int]] = {}
    uncovered: dict[str, int] = {}
    ai_calls = 0
    ai_prompt = 0
    ai_completion = 0
    ai_cost = 0.0
    ai_by_model: dict[tuple[str, str], dict[str, int]] = {}
    prices = await ai_pricing.load_prices(db)
    recent = []
    for row in rows:
        details = row.details or {}
        if row.event_type == "support.escalated":
            escalations += 1
            continue
        question = str(details.get("question") or "").strip()
        if row.event_type == "support.no_match":
            if question:
                uncovered[question] = uncovered.get(question, 0) + 1
            continue
        if row.event_type == "ai.usage":
            prompt_tokens = int(details.get("prompt_tokens") or 0)
            completion_tokens = int(details.get("completion_tokens") or 0)
            ai_calls += 1
            ai_prompt += prompt_tokens
            ai_completion += completion_tokens
            ai_cost += ai_pricing.estimate_cost_usd(details.get("model"), prompt_tokens, completion_tokens, prices)
            key = (str(details.get("provider") or "unknown"), str(details.get("model") or "unknown"))
            bucket = ai_by_model.setdefault(key, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0})
            bucket["calls"] += 1
            bucket["prompt_tokens"] += prompt_tokens
            bucket["completion_tokens"] += completion_tokens
            continue
        rating = details.get("rating")
        if rating == "up":
            feedback_up += 1
        elif rating == "down":
            feedback_down += 1
        if question:
            bucket = counts.setdefault(question, {"total": 0, "down": 0})
            bucket["total"] += 1
            if rating == "down":
                bucket["down"] += 1
        if len(recent) < 20:
            recent.append({"rating": rating or "unknown", "question": question, "created_at": row.created_at})

    total_feedback = feedback_up + feedback_down
    top_questions = sorted(
        ({"question": question, **bucket} for question, bucket in counts.items()),
        key=lambda item: (item["down"], item["total"]),
        reverse=True,
    )[:10]
    uncovered_questions = sorted(
        ({"question": question, "total": total, "down": 0} for question, total in uncovered.items()),
        key=lambda item: item["total"],
        reverse=True,
    )[:10]
    ai_models = sorted(
        (
            {"provider": provider_name, "model": model_name, **bucket}
            for (provider_name, model_name), bucket in ai_by_model.items()
        ),
        key=lambda item: item["calls"],
        reverse=True,
    )[:10]
    return SupportInsightsRead(
        window_days=window_days,
        feedback_up=feedback_up,
        feedback_down=feedback_down,
        satisfaction_rate=(feedback_up / total_feedback) if total_feedback else None,
        escalations=escalations,
        top_questions=top_questions,
        uncovered_questions=uncovered_questions,
        recent_feedback=recent,
        ai_calls=ai_calls,
        ai_prompt_tokens=ai_prompt,
        ai_completion_tokens=ai_completion,
        ai_estimated_cost_usd=round(ai_cost, 6),
        ai_by_model=ai_models,
    )


@router.get("/help/articles", response_model=list[HelpArticleRead])
async def admin_help_articles(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[HelpArticleRead]:
    """List every help article (including inactive) for the editor."""
    rows = (
        await db.execute(select(HelpArticle).order_by(HelpArticle.section_id, HelpArticle.position, HelpArticle.id))
    ).scalars().all()
    return [HelpArticleRead.model_validate(row) for row in rows]


@router.post("/help/articles", response_model=HelpArticleRead, status_code=status.HTTP_201_CREATED)
async def admin_create_help_article(
    payload: HelpArticleCreateRequest,
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> HelpArticleRead:
    """Create a help article. The id is the stable slug used by citations."""
    if await db.get(HelpArticle, payload.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An article with this id already exists")
    row = HelpArticle(**payload.model_dump(), updated_by=actor.id)
    db.add(row)
    await audit(db, actor, "admin.help_article_created", "help_article", None, {"id": payload.id})
    await db.commit()
    await db.refresh(row)
    return HelpArticleRead.model_validate(row)


@router.patch("/help/articles/{article_id}", response_model=HelpArticleRead)
async def admin_update_help_article(
    article_id: str,
    payload: HelpArticleUpdateRequest,
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> HelpArticleRead:
    """Update fields on a help article. Only provided fields are changed."""
    row = await db.get(HelpArticle, article_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help article not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.updated_by = actor.id
    await audit(db, actor, "admin.help_article_updated", "help_article", None, {"id": article_id, "fields": sorted(payload.model_fields_set)})
    await db.commit()
    await db.refresh(row)
    return HelpArticleRead.model_validate(row)


@router.delete("/help/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_help_article(
    article_id: str,
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft-delete a help article so it stops being served but is recoverable."""
    row = await db.get(HelpArticle, article_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Help article not found")
    row.is_active = False
    row.updated_by = actor.id
    await audit(db, actor, "admin.help_article_deleted", "help_article", None, {"id": article_id})
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/support/tickets", response_model=list[SupportTicketRead])
async def admin_support_tickets(
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
) -> list[SupportTicketRead]:
    """List support tickets for the operations team, newest first."""
    query = select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(200)
    if status_filter:
        query = query.where(SupportTicket.status == status_filter)
    rows = (await db.execute(query)).scalars().all()
    return [SupportTicketRead.model_validate(row) for row in rows]


@router.post("/support/attachments", response_model=SupportTicketAttachmentRead, status_code=status.HTTP_201_CREATED)
async def admin_upload_support_attachment(
    ticket_id: UUID = Form(...),
    file: UploadFile = File(...),
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketAttachmentRead:
    """Stage a reference image for an agent reply; claimed when the reply is sent."""
    ticket = await db.get(SupportTicket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    suffix, content = await read_image_upload(file)
    url = store_image(content, suffix, ticket.company_id)
    attachment = SupportTicketAttachment(
        company_id=ticket.company_id,
        url=url,
        content_type=file.content_type,
        byte_size=len(content),
        original_filename=file.filename,
        created_by=actor.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return SupportTicketAttachmentRead.model_validate(attachment)


@router.patch("/support/tickets/{ticket_id}", response_model=SupportTicketRead)
async def admin_update_support_ticket(
    ticket_id: UUID,
    payload: SupportTicketUpdateRequest,
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketRead:
    """Change a ticket's status (open/pending/resolved/closed) and notify the merchant.

    Tickets are never deleted: resolving or closing only changes the status, so the
    history stays visible and a ticket can be reopened.
    """
    row = await db.get(SupportTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    previous = row.status
    row.status = payload.status
    if payload.resolution_note is not None:
        row.resolution_note = payload.resolution_note
    row.resolved_at = datetime.now(timezone.utc) if payload.status == "resolved" else None
    if previous != row.status:
        await support_tickets_service.notify_ticket_merchants(
            db,
            ticket=row,
            kind="support_update",
            title=f"Your support request {row.reference} is now {row.status}",
            body=(payload.resolution_note or "").strip() or None,
        )
    await audit(db, actor, "admin.support_ticket_updated", "support_ticket", None, {"reference": row.reference, "from": previous, "to": row.status})
    await db.commit()
    await db.refresh(row)

    # Best-effort status email to the merchant (skip a no-op change).
    if previous != payload.status and row.user_id is not None:
        merchant = await db.get(User, row.user_id)
        if merchant is not None:
            note = (payload.resolution_note or "").strip()
            subjects = {
                "resolved": f"Your support request {row.reference} is resolved",
                "closed": f"Your support request {row.reference} is closed",
                "pending": f"Update on your support request {row.reference}",
                "open": f"Your support request {row.reference} has been reopened",
            }
            lead = {
                "resolved": "Your support request has been resolved.",
                "closed": "Your support request has been closed. Reply if you still need help and we will reopen it.",
                "pending": "We are still working on your support request.",
                "open": "Your support request has been reopened and is being looked at again.",
            }[payload.status]
            try:
                body_html = (
                    f'<p style="margin:0 0 4px 0;">{lead}</p>'
                    + data_table(["", ""], [["Reference", escape(row.reference)]], aligns=["left", "right"], show_header=False)
                    + '<p style="margin:16px 0 0 0;"><strong>Your question</strong></p>'
                    + f'<p style="margin:6px 0 0 0;">{escape(row.question)}</p>'
                    + (
                        '<p style="margin:16px 0 0 0;"><strong>Note from our team</strong></p>'
                        f'<p style="margin:6px 0 0 0;">{escape(note).replace(chr(10), "<br />")}</p>'
                        if note
                        else ""
                    )
                    + '<p style="margin:18px 0 0 0;">The in-app help and assistant are always available.</p>'
                )
                html = transactional_email(
                    heading=subjects[payload.status],
                    preview=lead,
                    body=body_html,
                    badge="Support",
                )
                await send_email(merchant.email, subjects[payload.status], html_to_text(html), html=html)
            except Exception:
                pass
    return SupportTicketRead.model_validate(row)


@router.get("/support/tickets/{ticket_id}", response_model=SupportTicketDetailRead)
async def admin_support_ticket_detail(
    ticket_id: UUID,
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailRead:
    """One ticket with its full thread, for the operations inbox."""
    row = await db.get(SupportTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    return await support_tickets_service.ticket_detail_read(db, row, include_system=True)


@router.post("/support/tickets/{ticket_id}/reply", response_model=SupportTicketDetailRead, status_code=status.HTTP_201_CREATED)
async def admin_reply_support_ticket(
    ticket_id: UUID,
    payload: SupportTicketReplyRequest,
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketDetailRead:
    """Add an agent reply to a ticket and email it to the merchant.

    Replying also moves an open ticket to ``pending`` (waiting on the merchant).
    """
    row = await db.get(SupportTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    body = sanitize_html(payload.body.strip())
    message = SupportTicketMessage(ticket_id=ticket_id, author_type="agent", author_user_id=actor.id, body=body)
    db.add(message)
    await db.flush()
    if payload.attachment_ids:
        try:
            await support_tickets_service.bind_attachments(
                db,
                company_id=row.company_id,
                ticket_id=ticket_id,
                message_id=message.id,
                attachment_ids=payload.attachment_ids,
            )
        except ValueError as exc:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if row.status == "open":
        row.status = "pending"
    await support_tickets_service.notify_ticket_merchants(
        db,
        ticket=row,
        kind="support_reply",
        title=f"Support replied to {row.reference}",
        body=html_to_text(body)[:600],
    )
    await audit(db, actor, "admin.support_ticket_replied", "support_ticket", None, {"reference": row.reference})
    await db.commit()

    # Best-effort email so the merchant sees the reply without opening the app.
    if row.user_id is not None:
        merchant = await db.get(User, row.user_id)
        if merchant is not None:
            try:
                body_html = (
                    '<p style="margin:0 0 4px 0;">Our team replied to your support request.</p>'
                    + data_table(["", ""], [["Reference", escape(row.reference)]], aligns=["left", "right"], show_header=False)
                    + f'<div style="margin:16px 0 0 0;">{body}</div>'
                    + '<p style="margin:18px 0 0 0;">You can reply from the Help page under Your support requests.</p>'
                )
                html = transactional_email(
                    heading=f"New reply on {row.reference}",
                    preview=f"Support replied to your request {row.reference}.",
                    body=body_html,
                    badge="Support",
                )
                await send_email(
                    merchant.email,
                    f"New reply on your support request {row.reference}",
                    html_to_text(html),
                    html=html,
                )
            except Exception:
                pass

    await db.refresh(row)
    return await support_tickets_service.ticket_detail_read(db, row, include_system=True)


@router.post("/support/tickets/{ticket_id}/ai-draft", response_model=SupportTicketAiDraftRead)
async def admin_ai_draft_support_ticket(
    ticket_id: UUID,
    payload: SupportTicketAiDraftRequest,
    actor: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketAiDraftRead:
    """Rewrite (or start) an agent reply with AI. Returns a draft to review."""
    row = await db.get(SupportTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    try:
        result = await support_tickets_service.rewrite_reply(
            db, ticket=row, draft=payload.body, instruction=payload.instruction, tone=payload.tone
        )
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await audit(db, actor, "admin.support_ticket_ai_drafted", "support_ticket", None, {"reference": row.reference})
    await db.commit()
    return SupportTicketAiDraftRead(**result)


@router.post("/support/tickets/{ticket_id}/ai-suggest", response_model=SupportTicketAiSuggestRead)
async def admin_ai_suggest_support_ticket(
    ticket_id: UUID,
    _: User = Depends(get_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> SupportTicketAiSuggestRead:
    """Suggest a reply grounded in the help corpus when the assistant knows it.

    ``matched`` is false when no guide covered the merchant's issue; the agent
    then knows the suggestion is a best effort and the corpus needs a new guide.
    """
    row = await db.get(SupportTicket, ticket_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found")
    company = await db.get(Company, row.company_id)
    try:
        result = await support_tickets_service.suggest_reply(
            db, ticket=row, vertical=getattr(company, "vertical", None), role=None
        )
    except ai_service.AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ai_service.AIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    await db.commit()
    return SupportTicketAiSuggestRead(**result)

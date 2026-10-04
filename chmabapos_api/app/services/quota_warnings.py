"""Owner warnings when a workspace nears its plan limits.

This is company-level, not per-store: a recurring pass compares active stores and
active team members against the governing plan's limits and queues one email to
owners per resource per level, with a cooldown, so an inbox is not spammed.
Workspaces on the Free plan are skipped entirely: Free is the baseline fallback
whose limits are already met on signup, so warning would email every free owner.
The per-company marker lives in ``Company.settings['quota_warning_state']`` so no
new table is needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import FREE_PLAN_CODE, load_entitlement
from app.models import Company, EmailSend, Membership, Store, User
from app.services.email_layout import data_table, transactional_email

QUOTA_WARNING_SOURCE = "quota_warning"
WARNING_RATIO = 0.9
COOLDOWN = timedelta(days=7)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _owner_emails(db: AsyncSession, company_id) -> list[str]:
    rows = (
        await db.execute(
            select(User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == company_id,
                Membership.status == "active",
                Membership.role == "owner",
                User.is_active.is_(True),
            )
        )
    ).scalars().all()
    return [email for email in rows if email]


def _level(used: int, limit: int) -> str | None:
    if limit <= 0:
        return None
    if used >= limit:
        return "full"
    if used >= limit * WARNING_RATIO:
        return "near"
    return None


def _due(previous: dict, level: str, now: datetime) -> bool:
    """True when this level has not already been warned within the cooldown."""
    if previous.get("level") != level:
        return True
    sent_at = previous.get("sent_at")
    if not sent_at:
        return True
    try:
        return now - datetime.fromisoformat(sent_at) >= COOLDOWN
    except ValueError:
        return True


async def run_quota_warnings(db: AsyncSession, *, now: datetime | None = None) -> dict:
    """Email owners of workspaces at or near a plan limit. Idempotent per level."""
    now = now or utc_now()
    stats = {"companies": 0, "warned": 0}
    for company in (await db.execute(select(Company))).scalars().all():
        try:
            entitlement = await load_entitlement(db, company.id)
        except Exception:
            continue
        plan = entitlement.plan
        if plan is None:
            continue
        if plan.code == FREE_PLAN_CODE:
            # Free is the baseline every workspace falls back to, and its
            # limits (1 store, 1 seat) are already met on signup. Warning on
            # them would email every free owner, so reserve this nudge for
            # paying plans (Starter/Pro) that can actually upgrade.
            continue
        stores_used = await db.scalar(
            select(func.count(Store.id)).where(Store.company_id == company.id, Store.is_active.is_(True))
        ) or 0
        members_used = await db.scalar(
            select(func.count(Membership.id)).where(Membership.company_id == company.id, Membership.status == "active")
        ) or 0
        state = dict((company.settings or {}).get("quota_warning_state") or {})
        warnings: list[tuple[str, int, int, str]] = []
        for resource, used, limit in (("stores", int(stores_used), int(plan.max_stores)), ("members", int(members_used), int(plan.max_members))):
            level = _level(used, limit)
            if level is None:
                continue
            if not _due(state.get(resource) or {}, level, now):
                continue
            warnings.append((resource, used, limit, level))
        if not warnings:
            continue
        recipients = await _owner_emails(db, company.id)
        if not recipients:
            continue
        item_rows = [
            [
                escape(resource.title()),
                f"{used:,}",
                f"{limit:,}",
                "At limit" if level == "full" else f"{round(used / limit * 100)}% used",
            ]
            for resource, used, limit, level in warnings
        ]
        body = (
            f'<p style="margin:0 0 4px 0;">Your workspace is getting close to its '
            f"<strong>{escape(plan.name)}</strong> plan limits.</p>"
            + data_table(["Resource", "Used", "Limit", "Status"], item_rows, aligns=["left", "right", "right", "left"])
            + '<p style="margin:18px 0 0 0;">Upgrade in Billing &amp; plans to add more, or remove what you no longer use.</p>'
        )
        html = transactional_email(
            heading="Approaching your plan limits",
            preview=f"Your {plan.name} plan is nearing its limits.",
            body=body,
            badge="Billing",
        )
        for email in recipients:
            db.add(
                EmailSend(
                    recipient_email=email,
                    subject=f"Approaching your plan limits · {plan.name}",
                    body_html=html,
                    status="queued",
                    source=QUOTA_WARNING_SOURCE,
                )
            )
        for resource, _used, _limit, level in warnings:
            state[resource] = {"level": level, "sent_at": now.isoformat()}
        settings = dict(company.settings or {})
        settings["quota_warning_state"] = state
        company.settings = settings
        stats["companies"] += 1
        stats["warned"] += len(warnings)
    await db.commit()
    return stats

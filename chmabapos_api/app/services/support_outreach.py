"""Stage-aware AI help for proactive support outreach.

The ops inbox can start a conversation with any merchant, but a blank composer
puts the burden on the agent to work out where that merchant actually is. This
module reads the same rows the product already treats as truth (products, paid
orders, shifts, subscription, support history) and turns them into:

* a short, factual "where they are now" context for the agent, and
* 3-5 suggested subjects, then one drafted first message for the chosen subject.

The AI is never allowed to invent facts: it receives a plain-text context built
from the database and is told to stay inside it. When the provider is not
configured or fails, the subject step falls back to deterministic, stage-based
suggestions so the composer is still useful; drafting requires the provider and
returns a normal API error instead of a guessed message.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Company,
    Guide,
    GuideCategory,
    Membership,
    MembershipStore,
    Order,
    Product,
    Shift,
    Store,
    Subscription,
    SupportChatConversation,
    SupportTicket,
    User,
    utcnow,
)
from app.services import ai as ai_service
from app.services import support as support_service
from app.verticals import VERTICAL_LABELS

MIN_SUBJECTS = 3
MAX_SUBJECTS = 5
MAX_SUBJECT_CHARS = 90
MAX_BODY_CHARS = 4000

logger = logging.getLogger(__name__)

# Public guide category that matches each company business type. The "every-shop"
# category is added to every merchant because those four setups apply to all of
# them (online orders, KHQR, staff access and buying stock).
GUIDE_CATEGORY_BY_VERTICAL = {
    "coffee": "coffee-shop",
    "restaurant": "restaurant",
    "mart": "mart",
    "electronics": "electronics",
    "shop": "general-retail",
    "general": "general-retail",
}


class OutreachTargetNotFound(Exception):
    """The person/workspace is not an active merchant the ops inbox can message."""


class OutreachStoreMismatch(Exception):
    """A supplied store does not belong to the supplied company."""


@dataclass
class OutreachContext:
    user: User
    membership: Membership
    company: Company
    store: Store | None
    product_count: int
    paid_orders: int
    paid_orders_30d: int
    last_sale_at: datetime | None
    shift_count: int
    store_count: int
    member_count: int
    subscription: Subscription | None
    last_conversation: SupportChatConversation | None
    open_tickets: int
    onboarding: dict = field(default_factory=dict)
    stage: str = "active"
    stage_label: str = "Active seller"
    stage_detail: str = ""
    next_step: str | None = None

    def lines(self) -> list[str]:
        """The compact facts shown above the subject suggestions."""
        lines = [
            f"{self.company.name} · {VERTICAL_LABELS.get(self.company.vertical, self.company.vertical)}"
            f" · signed up {_days_since(self.company.created_at)} day(s) ago"
        ]
        if self.store is not None:
            lines.append(f"Store: {self.store.name}")
        lines.append(
            f"Catalogue: {self.product_count} active product(s)"
            + (" · no real products yet" if self.product_count == 0 else "")
        )
        if self.last_sale_at is not None:
            lines.append(
                f"Sales: {self.paid_orders} paid · last {_days_since(self.last_sale_at)} day(s) ago"
            )
        else:
            lines.append("Sales: no paid sale yet")
        if self.subscription is not None:
            lines.append(f"Plan: {self.subscription.plan_code} · {self.subscription.status}")
        else:
            lines.append("Plan: free")
        lines.append(f"Team: {self.member_count} active · {self.store_count} store(s)")
        store_band = str(self.onboarding.get("store_count_band") or "").strip()
        team_band = str(self.onboarding.get("team_size_band") or "").strip()
        if store_band or team_band:
            lines.append(
                "Onboarding said: "
                f"{store_band or '?'} store(s), {team_band or '?'} team member(s)"
            )
        if self.last_conversation is not None:
            topic = self.last_conversation.subject or self.last_conversation.last_message_preview or "no subject"
            lines.append(
                f"Last chat: {self.last_conversation.reference} · "
                f"{self.last_conversation.status} · {topic[:80]}"
            )
        if self.open_tickets:
            lines.append(f"Open support ticket(s): {self.open_tickets}")
        if self.next_step:
            lines.append(f"Next setup step: {self.next_step}")
        else:
            lines.append("Setup: complete")
        return lines

    def as_text(self) -> str:
        """The context block handed to the model, one fact per line."""
        return "\n".join(
            [
                f"Merchant: {self.user.full_name or self.user.email} <{self.user.email}>",
                f"Company: {self.company.name}",
                f"Business type: {VERTICAL_LABELS.get(self.company.vertical, self.company.vertical)}",
                f"Country: {self.company.country}",
                *self.lines(),
                f"Current stage: {self.stage_label} — {self.stage_detail}",
            ]
        )


def _days_since(value: datetime | None) -> int:
    if value is None:
        return 0
    now = utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=now.tzinfo)
    return max((now - value).days, 0)


async def _store_for_membership(
    db: AsyncSession,
    membership: Membership,
    company_id: UUID,
) -> Store | None:
    store_id = await db.scalar(
        select(MembershipStore.store_id)
        .join(Store, Store.id == MembershipStore.store_id)
        .where(MembershipStore.membership_id == membership.id)
        .order_by(Store.created_at.asc())
        .limit(1)
    )
    if store_id is None:
        store_id = await db.scalar(
            select(Store.id)
            .where(Store.company_id == company_id)
            .order_by(Store.created_at.asc())
            .limit(1)
        )
    return await db.get(Store, store_id) if store_id is not None else None


def _first_step_title(vertical: str | None) -> str:
    return {
        "coffee": "Add your menu items",
        "restaurant": "Add your menu items",
        "mart": "Add products with barcodes",
        "electronics": "Add products with serial numbers",
        "shop": "Add your first product",
        "general": "Add your first product",
    }.get(vertical or "general", "Add your first product")


async def build_context(
    db: AsyncSession,
    *,
    user_id: UUID,
    company_id: UUID,
    store_id: UUID | None = None,
) -> OutreachContext:
    """Read the merchant's real stage without assuming the caller is right.

    Membership and store ownership are re-checked here so both AI endpoints have
    the same gate as the conversation-start endpoint.
    """
    membership = (
        await db.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None or membership.status != "active" or membership.role not in {"owner", "manager"}:
        raise OutreachTargetNotFound("Store owner not found")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise OutreachTargetNotFound("Store owner not found")
    company = await db.get(Company, company_id)
    if company is None:
        raise OutreachTargetNotFound("Store owner not found")

    store: Store | None = None
    if store_id is not None:
        store = await db.get(Store, store_id)
        if store is None or store.company_id != company_id:
            raise OutreachStoreMismatch("Store does not belong to this company")
    else:
        store = await _store_for_membership(db, membership, company_id)

    store_ids = list(
        (await db.execute(select(Store.id).where(Store.company_id == company_id))).scalars().all()
    )
    product_count = await db.scalar(
        select(func.count(Product.id)).where(
            Product.company_id == company_id,
            Product.is_active.is_(True),
            Product.is_sample.is_(False),
        )
    ) or 0
    paid_orders = 0
    paid_orders_30d = 0
    last_sale_at = None
    shift_count = 0
    if store_ids:
        paid_orders, last_sale_at = (
            await db.execute(
                select(func.count(Order.id), func.max(Order.created_at)).where(
                    Order.store_id.in_(store_ids),
                    Order.status == "paid",
                )
            )
        ).one()
        paid_orders_30d = await db.scalar(
            select(func.count(Order.id)).where(
                Order.store_id.in_(store_ids),
                Order.status == "paid",
                Order.created_at >= utcnow() - timedelta(days=30),
            )
        ) or 0
    if store is not None:
        shift_count = await db.scalar(
            select(func.count(Shift.id)).where(Shift.store_id == store.id)
        ) or 0
    store_count = len(store_ids)
    member_count = await db.scalar(
        select(func.count(Membership.id)).where(
            Membership.company_id == company_id,
            Membership.status == "active",
        )
    ) or 0
    subscription = (
        await db.execute(
            select(Subscription)
            .where(Subscription.company_id == company_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    last_conversation = (
        await db.execute(
            select(SupportChatConversation)
            .where(SupportChatConversation.company_id == company_id)
            .order_by(
                SupportChatConversation.last_message_at.desc().nulls_last(),
                SupportChatConversation.created_at.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    open_tickets = await db.scalar(
        select(func.count(SupportTicket.id)).where(
            SupportTicket.company_id == company_id,
            SupportTicket.status.in_(["open", "pending"]),
        )
    ) or 0
    onboarding = {}
    if store is not None and isinstance(store.preferences, dict):
        profile = store.preferences.get("onboarding_profile")
        if isinstance(profile, dict):
            onboarding = profile

    context = OutreachContext(
        user=user,
        membership=membership,
        company=company,
        store=store,
        product_count=product_count,
        paid_orders=paid_orders or 0,
        paid_orders_30d=paid_orders_30d,
        last_sale_at=last_sale_at,
        shift_count=shift_count,
        store_count=store_count,
        member_count=member_count,
        subscription=subscription,
        last_conversation=last_conversation,
        open_tickets=open_tickets,
        onboarding=onboarding,
    )
    _classify(context)
    return context


def _classify(context: OutreachContext) -> None:
    """Set stage, detail and the next real setup step on the context."""
    team_band = str(context.onboarding.get("team_size_band") or "")
    payment_ready = bool(context.company.aba_payway_link)

    if not context.company.is_active:
        context.stage = "suspended"
        context.stage_label = "Workspace suspended"
        context.stage_detail = "The company is currently suspended."
    elif context.subscription is not None and context.subscription.status in {
        "pending",
        "past_due",
        "expired",
        "canceled",
    }:
        context.stage = "billing"
        context.stage_label = "Billing needs attention"
        context.stage_detail = (
            f"The {context.subscription.plan_code} plan is {context.subscription.status}."
        )
    elif context.last_conversation is not None and context.last_conversation.status in {
        "waiting",
        "live",
    }:
        context.stage = "support_followup"
        context.stage_label = "Support follow-up"
        context.stage_detail = (
            f"Chat {context.last_conversation.reference} is {context.last_conversation.status}."
        )
    elif context.product_count == 0:
        context.stage = "catalogue"
        context.stage_label = "Setting up the catalogue"
        context.stage_detail = "No real products yet; only sample items."
    elif context.paid_orders == 0:
        context.stage = "first_sale"
        context.stage_label = "Ready for the first sale"
        context.stage_detail = (
            f"{context.product_count} product(s) added, but no paid sale yet."
        )
    elif context.last_sale_at is not None and _days_since(context.last_sale_at) >= 14:
        context.stage = "dormant"
        context.stage_label = "Quiet store"
        context.stage_detail = f"Last paid sale was {_days_since(context.last_sale_at)} day(s) ago."
    else:
        context.stage = "active"
        context.stage_label = "Active seller"
        last = (
            f" Last sale {_days_since(context.last_sale_at)} day(s) ago."
            if context.last_sale_at is not None
            else ""
        )
        recent = f" {context.paid_orders_30d} paid sale(s) in the last 30 days." if context.paid_orders_30d else ""
        context.stage_detail = f"{context.paid_orders} paid sale(s) in total.{last}{recent}".strip()

    if context.product_count == 0:
        context.next_step = _first_step_title(context.company.vertical)
    elif context.paid_orders == 0:
        context.next_step = "Ring up your first sale"
    elif context.shift_count == 0:
        context.next_step = "Open a shift"
    elif not payment_ready:
        context.next_step = "Set up KHQR payments"
    elif context.member_count <= 1 and team_band != "1":
        context.next_step = "Invite a team member"
    else:
        context.next_step = None


def fallback_subjects(context: OutreachContext) -> list[str]:
    """Deterministic suggestions when AI is unavailable or returns too few."""
    store = context.store.name if context.store is not None else context.company.name
    reference = (
        context.last_conversation.reference if context.last_conversation is not None else "your last chat"
    )
    by_stage = {
        "suspended": [
            f"Your {context.company.name} workspace is paused",
            "Let's get your store back online",
            f"Can we help you restart {store}?",
        ],
        "billing": [
            f"Your {context.subscription.plan_code if context.subscription else 'Chmaba'} plan needs attention",
            "Keeping your store online",
            f"Can we help with billing at {store}?",
        ],
        "support_followup": [
            f"Following up on {reference}",
            "Did that issue get sorted?",
            f"Still need help at {store}?",
        ],
        "catalogue": [
            "Let's get your first products in",
            f"Ready to add items to {store}?",
            "A quick hand with your catalogue",
        ],
        "first_sale": [
            "Ready for your first sale?",
            f"Let's ring up the first sale at {store}",
            "A quick walkthrough for your first sale",
        ],
        "dormant": [
            f"How are things at {store}?",
            "Anything slowing sales down?",
            "A quick check-in from Chmaba",
        ],
        "active": [
            f"How is {store} doing?",
            "Anything we can improve for you?",
            "A quick check-in from Chmaba",
        ],
    }
    subjects = by_stage.get(context.stage, by_stage["active"])
    if context.next_step:
        subjects.append(f"Need a hand with: {context.next_step}")
    generic = [
        f"Checking in on {context.company.name}",
        f"Anything you need at {store}?",
    ]
    for subject in generic:
        if len(subjects) >= MIN_SUBJECTS:
            break
        if subject not in subjects:
            subjects.append(subject)
    return _clean_subjects(subjects)[:MAX_SUBJECTS]


def fallback_draft(context: OutreachContext) -> str:
    """A useful stage-based draft when the provider cannot write one.

    The subject is already in the composer; this fills the body with the same
    facts the AI would have received, so a provider outage does not leave the
    agent with an empty message. It never claims anything the database does not
    support.
    """
    first_name = (context.user.full_name or "").strip().split(" ")[0] or "there"
    store = context.store.name if context.store is not None else context.company.name
    plan = context.subscription.plan_code if context.subscription is not None else "free"
    plan_status = context.subscription.status if context.subscription is not None else "active"
    reference = (
        context.last_conversation.reference if context.last_conversation is not None else "your recent chat"
    )
    stage_sentence = {
        "suspended": f"I wanted to check in about {context.company.name}, which is currently paused.",
        "billing": f"I wanted to check in about your {plan} plan, which currently shows as {plan_status}.",
        "support_followup": f"I wanted to follow up on {reference} and see how things are going.",
        "catalogue": f"I saw that {store} does not have its own products in Chmaba yet.",
        "first_sale": f"I saw that {store} has products ready, but has not recorded a paid sale yet.",
        "dormant": (
            f"I saw that {store} has not recorded a paid sale in "
            f"{_days_since(context.last_sale_at)} days."
        ),
        "active": f"I saw that {store} has recorded {context.paid_orders} paid sale(s) so far.",
    }.get(context.stage, f"I wanted to check in on {store}.")
    lines = [f"Hi {first_name},", "", stage_sentence]
    if context.next_step:
        lines.append(f"If it would help, I can walk you through the next step: {context.next_step.lower()}.")
    lines.append("Is there anything you'd like help with today?")
    return "\n\n".join(lines)[:MAX_BODY_CHARS]


async def guides_for_company(db: AsyncSession, company: Company) -> list[dict]:
    """Published setup guides for this merchant's business type.

    The category guide gives the merchant the path for their own trade; the
    "every-shop" guides cover the four setups every workspace needs. Drafts and
    archived guides are never offered from the support composer.
    """
    category_slug = GUIDE_CATEGORY_BY_VERTICAL.get(company.vertical or "general", "general-retail")
    rows = (
        await db.execute(
            select(Guide, GuideCategory)
            .join(GuideCategory, GuideCategory.id == Guide.category_id)
            .where(
                Guide.status == "published",
                GuideCategory.is_active.is_(True),
                GuideCategory.slug.in_([category_slug, "every-shop"]),
            )
            .order_by(GuideCategory.position, Guide.position, Guide.title)
        )
    ).all()
    return [
        {
            "id": guide.id,
            "title": guide.title,
            "summary": guide.summary,
            "slug": guide.slug,
            "category_slug": category.slug,
            "category_name": category.name,
            "estimated_minutes": guide.estimated_minutes,
        }
        for guide, category in rows
    ]


def _clean_subjects(items: list) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            raw = item.get("subject") or item.get("title") or item.get("text") or ""
        else:
            raw = item
        text = " ".join(str(raw or "").split()).strip(" -–—:;,.!?\"'`")
        if not text:
            continue
        text = text[:MAX_SUBJECT_CHARS].rstrip()
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _merge_subjects(primary: list[str], fallback: list[str]) -> list[str]:
    subjects = _clean_subjects([*primary, *fallback])
    return subjects[:MAX_SUBJECTS]


def _parse_subjects(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            payload = None
        if isinstance(payload, dict):
            items = payload.get("subjects")
            if isinstance(items, list):
                return _clean_subjects(items)
        if isinstance(payload, list):
            return _clean_subjects(payload)
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            payload = None
        if isinstance(payload, list):
            return _clean_subjects(payload)
    return []


def _parse_body(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            payload = None
        if isinstance(payload, dict):
            body = payload.get("body") or payload.get("message") or payload.get("text") or ""
            if body:
                return str(body).strip()[:MAX_BODY_CHARS]
    # A model that ignored the JSON instruction is still usable as plain text.
    return text.strip('"').strip()[:MAX_BODY_CHARS]


SUBJECT_SYSTEM = (
    "You help Chmaba's platform support team start a proactive chat with a merchant. "
    "Chmaba is a cloud point-of-sale for retail shops in Cambodia. "
    "Use ONLY the MERCHANT CONTEXT provided. Never invent sales, products, dates, "
    "complaints, prices or promises. "
    'Return strict JSON only: {"subjects": ["...", "..."]} with 3 to 5 subjects. '
    "Each subject is one short, natural sentence under 70 characters, with no numbering, "
    "quotes or emoji. Make each one specific to the merchant's current stage, next step or "
    "recent support chat. Do not repeat the same idea. Never say the merchant complained."
)

DRAFT_SYSTEM = (
    "You write the first chat message from Chmaba's platform support team to a merchant. "
    "Chmaba is a cloud point-of-sale for retail shops in Cambodia. "
    "Use ONLY the MERCHANT CONTEXT and the CHOSEN SUBJECT. Never invent facts. "
    "Write 2-4 short paragraphs, under 120 words, in plain text with no markdown, links, "
    "emoji or signature. Show that we understand where the merchant is now by naming at "
    "most one concrete fact from the context, offer one specific next step, and ask one "
    "friendly question. If the subject is about billing or a support chat, stay factual and "
    "careful. Return strict JSON only: {\"body\": \"...\"}"
)


async def suggest_subjects(
    db: AsyncSession,
    context: OutreachContext,
) -> dict:
    """3-5 subjects for this merchant, falling back to the stage when AI fails."""
    fallback = fallback_subjects(context)
    try:
        result = await ai_service.complete_chat(
            db,
            system=SUBJECT_SYSTEM,
            messages=[{"role": "user", "content": context.as_text()}],
            temperature=0.6,
            max_tokens=350,
        )
    except ai_service.AINotConfiguredError as exc:
        logger.warning("Support outreach AI Error (subjects not configured) for company %s: %s", context.company.id, exc)
        return {
            "subjects": fallback,
            "source": "fallback",
            "notice": "AI is not configured, so these subjects come from the merchant's stage.",
            "provider": None,
            "model": None,
        }
    except ai_service.AIError as exc:
        logger.warning("Support outreach AI Error (subjects) for company %s: %s", context.company.id, exc)
        return {
            "subjects": fallback,
            "source": "fallback",
            "notice": "AI is unavailable right now, so these subjects come from the merchant's stage.",
            "provider": None,
            "model": None,
        }

    subjects = _parse_subjects(result.get("content") or "")
    if len(subjects) < MIN_SUBJECTS:
        return {
            "subjects": fallback,
            "source": "fallback",
            "notice": "AI returned too few usable subjects, so these come from the merchant's stage.",
            "provider": result.get("provider"),
            "model": result.get("model"),
        }
    subjects = _merge_subjects(subjects, [])
    await _record_usage(result, context.company.id)
    return {
        "subjects": subjects[:MAX_SUBJECTS],
        "source": "ai",
        "notice": None,
        "provider": result.get("provider"),
        "model": result.get("model"),
    }


async def draft_message(
    db: AsyncSession,
    context: OutreachContext,
    *,
    subject: str,
) -> dict:
    """Draft the first message for a chosen subject.

    A provider outage must not turn a chosen subject into a dead end, so the
    fallback uses the same stage facts the AI would have seen. The response says
    which path produced the text, and the UI labels the fallback for review.
    """
    prompt = f"CHOSEN SUBJECT: {subject.strip()}\n\nMERCHANT CONTEXT:\n{context.as_text()}"
    try:
        result = await ai_service.complete_chat(
            db,
            system=DRAFT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500,
        )
    except ai_service.AINotConfiguredError as exc:
        logger.warning("Support outreach AI Error (draft not configured) for company %s: %s", context.company.id, exc)
        return {
            "subject": subject.strip(),
            "body": fallback_draft(context),
            "source": "fallback",
            "notice": "AI is not configured, so this draft uses the merchant's current stage. Review and edit it before sending.",
            "provider": None,
            "model": None,
        }
    except ai_service.AIError as exc:
        logger.warning("Support outreach AI Error (draft) for company %s: %s", context.company.id, exc)
        return {
            "subject": subject.strip(),
            "body": fallback_draft(context),
            "source": "fallback",
            "notice": "AI is unavailable right now, so this draft uses the merchant's current stage. Review and edit it before sending.",
            "provider": None,
            "model": None,
        }
    body = _parse_body(result.get("content") or "")
    if not body:
        logger.warning("Support outreach AI Error (empty draft) for company %s", context.company.id)
        return {
            "subject": subject.strip(),
            "body": fallback_draft(context),
            "source": "fallback",
            "notice": "AI returned an empty message, so this draft uses the merchant's current stage. Review and edit it before sending.",
            "provider": result.get("provider"),
            "model": result.get("model"),
        }
    await _record_usage(result, context.company.id)
    return {
        "subject": subject.strip(),
        "body": body,
        "source": "ai",
        "notice": None,
        "provider": result.get("provider"),
        "model": result.get("model"),
    }


async def _record_usage(result: dict, company_id: UUID) -> None:
    usage = dict(result.get("usage") or {})
    usage.setdefault("provider", result.get("provider"))
    usage.setdefault("model", result.get("model"))
    await support_service.record_usage(usage=usage, company_id=company_id)

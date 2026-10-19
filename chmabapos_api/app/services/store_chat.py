"""Storefront customer <-> store chat.

The thread itself is trivial - one conversation, a stream of messages - so the
interesting work lives here: turning rows into the shapes the two clients render,
deriving the one-line preview, and telling the store when a customer writes.

Delivery is deliberately *not* handled here. Both clients stream with
``after_seq`` against the database, which means the API can stay a single
process with no broker and still deliver reliably; a background push would only
be an optimisation.
"""
from __future__ import annotations

from datetime import timedelta
from html import escape
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Company,
    EmailSend,
    Membership,
    MembershipStore,
    Notification,
    Order,
    ShopperAccount,
    Store,
    StoreChatConversation,
    StoreChatMessage,
    StoreChatReaction,
    User,
    utcnow,
)
from app.schemas import (
    StoreChatAttachmentRead,
    StoreChatConversationSummary,
    StoreChatMessageRead,
    StoreChatOrderRead,
    StoreChatReactionRead,
)
from app.services.email_layout import transactional_email


def preview(kind: str, body: str | None, attachment_name: str | None = None, order_number: str | None = None) -> str:
    """The one-line summary shown in an inbox list.

    A message with text is summarised by that text; otherwise the kind is shown
    as an icon and a word, so a list full of photos still reads.
    """
    text = (body or "").strip()
    if text:
        return text[:200]
    if kind == "order":
        return f"📦 Order #{order_number}"[:200] if order_number else "📦 Order"
    if kind == "image":
        return "📷 Photo"
    if kind == "voice":
        return "🎤 Voice message"
    if kind == "file":
        return f"📎 {attachment_name or 'Attachment'}"[:200]
    return "New message"


def display_name(
    conversation: StoreChatConversation,
    shopper: ShopperAccount | None = None,
    *,
    use_seller_label: bool = True,
) -> str:
    """How the store should see the customer in a list.

    A label the store set comes first: it is what the staff chose to call this
    thread, which is exactly what makes a list of "Guest"s readable. Pass
    ``use_seller_label=False`` on any customer-facing read, since the label is
    private to the store.
    """
    if use_seller_label and conversation.seller_label:
        return conversation.seller_label
    if conversation.guest_name:
        return conversation.guest_name
    if shopper is not None:
        return shopper.full_name or shopper.email or shopper.phone or "Customer"
    if conversation.guest_email:
        return conversation.guest_email
    if conversation.guest_phone:
        return conversation.guest_phone
    return "Guest"


def unread_for(conversation: StoreChatConversation, viewer_side: str) -> int:
    return conversation.seller_unread_count if viewer_side == "seller" else conversation.customer_unread_count


async def message_reads(db: AsyncSession, messages: list[StoreChatMessage], viewer_side: str) -> list[StoreChatMessageRead]:
    """Serialise messages, folding in the reaction tally per emoji.

    ``reacted`` is true when the *viewer's* side has reacted, so the same row can
    render "you reacted 👍" for the customer and "the customer reacted 👍" for
    the store without any client-side guessing.
    """
    if not messages:
        return []
    rows = (
        await db.execute(select(StoreChatReaction).where(StoreChatReaction.message_id.in_([m.id for m in messages])))
    ).scalars().all()
    grouped: dict[UUID, dict[str, dict]] = {}
    for reaction in rows:
        slot = grouped.setdefault(reaction.message_id, {})
        entry = slot.setdefault(reaction.emoji, {"count": 0, "reacted": False})
        entry["count"] += 1
        if reaction.reactor_type == viewer_side:
            entry["reacted"] = True
    # Name the author of each message. A seller message carries the staff member
    # who wrote it (so two people sharing the inbox are distinguishable); a
    # customer message carries the name the thread is labelled with.
    conversation_ids = {message.conversation_id for message in messages}
    conversations = {
        conversation.id: conversation
        for conversation in (
            await db.execute(select(StoreChatConversation).where(StoreChatConversation.id.in_(conversation_ids)))
        ).scalars().all()
    }
    shopper_ids = {conversation.shopper_id for conversation in conversations.values() if conversation.shopper_id}
    shoppers: dict[UUID, ShopperAccount] = {}
    if shopper_ids:
        shoppers = {
            shopper.id: shopper
            for shopper in (await db.execute(select(ShopperAccount).where(ShopperAccount.id.in_(shopper_ids)))).scalars().all()
        }
    seller_ids = {message.sender_user_id for message in messages if message.sender_user_id}
    sellers: dict[UUID, str] = {}
    if seller_ids:
        sellers = {
            user.id: user.full_name
            for user in (await db.execute(select(User).where(User.id.in_(seller_ids)))).scalars().all()
        }
    store_ids = {conversation.store_id for conversation in conversations.values()}
    store_names: dict[UUID, str] = {}
    if store_ids:
        store_names = {
            store.id: store.name
            for store in (await db.execute(select(Store).where(Store.id.in_(store_ids)))).scalars().all()
        }
    order_ids = {message.order_id for message in messages if message.order_id}
    orders: dict[UUID, Order] = {}
    if order_ids:
        orders = {
            order.id: order
            for order in (await db.execute(select(Order).where(Order.id.in_(order_ids)))).scalars().all()
        }
    reads: list[StoreChatMessageRead] = []
    for message in messages:
        attachment = None
        if message.attachment_url:
            attachment = StoreChatAttachmentRead(
                url=message.attachment_url,
                name=message.attachment_name,
                content_type=message.attachment_content_type,
                byte_size=message.attachment_byte_size or 0,
                duration_ms=message.attachment_duration_ms,
            )
        reactions = [
            StoreChatReactionRead(emoji=emoji, count=entry["count"], reacted=entry["reacted"])
            for emoji, entry in sorted(grouped.get(message.id, {}).items())
        ]
        if message.sender_type == "seller":
            conversation = conversations.get(message.conversation_id)
            if viewer_side == "customer":
                # The customer must never learn which staff member replied; the store
                # answers as one voice, so a seller message carries the store name.
                author_name = (store_names.get(conversation.store_id) if conversation else None) or "Store"
            else:
                # The inbox is internal, so it names the person who replied.
                author_name = sellers.get(message.sender_user_id) or "Store"
        else:
            conversation = conversations.get(message.conversation_id)
            author_name = (
                display_name(conversation, shoppers.get(conversation.shopper_id), use_seller_label=(viewer_side == "seller"))
                if conversation
                else "Guest"
            )
        order_read = None
        if message.order_id:
            order = orders.get(message.order_id)
            if order is not None:
                order_read = StoreChatOrderRead(
                    id=order.id,
                    order_number=order.order_number,
                    status=order.status,
                    total=str(order.total),
                    currency_code=order.currency_code,
                    public_token=order.public_token,
                )
        reads.append(
            StoreChatMessageRead(
                id=message.id,
                seq=message.seq,
                sender_type=message.sender_type,
                kind=message.kind,
                body=message.body,
                attachment=attachment,
                order=order_read,
                reactions=reactions,
                author_name=author_name,
                created_at=message.created_at,
            )
        )
    return reads


async def conversation_summaries(
    db: AsyncSession,
    conversations: list[StoreChatConversation],
    viewer_side: str,
) -> list[StoreChatConversationSummary]:
    """Summaries for a list, resolving store, company and shopper in one pass."""
    if not conversations:
        return []
    store_ids = {conversation.store_id for conversation in conversations}
    company_ids = {conversation.company_id for conversation in conversations}
    shopper_ids = {conversation.shopper_id for conversation in conversations if conversation.shopper_id}
    stores = {store.id: store for store in (await db.execute(select(Store).where(Store.id.in_(store_ids)))).scalars().all()}
    companies = {company.id: company for company in (await db.execute(select(Company).where(Company.id.in_(company_ids)))).scalars().all()}
    shoppers: dict[UUID, ShopperAccount] = {}
    if shopper_ids:
        shoppers = {shopper.id: shopper for shopper in (await db.execute(select(ShopperAccount).where(ShopperAccount.id.in_(shopper_ids)))).scalars().all()}
    summaries: list[StoreChatConversationSummary] = []
    for conversation in conversations:
        store = stores.get(conversation.store_id)
        company = companies.get(conversation.company_id)
        shopper = shoppers.get(conversation.shopper_id) if conversation.shopper_id else None
        shopper_name = None
        if shopper is not None:
            shopper_name = shopper.full_name or shopper.email or shopper.phone
        elif conversation.shopper_id:
            shopper_name = "Customer"
        # A signed-in shopper's account is the better source; an anonymous visitor
        # only ever has what they typed into the thread.
        contact_email = (shopper.email if shopper is not None else None) or conversation.guest_email
        contact_phone = (shopper.phone if shopper is not None else None) or conversation.guest_phone
        summaries.append(
            StoreChatConversationSummary(
                id=conversation.id,
                status=conversation.status,
                guest_name=conversation.guest_name,
                # The store's private name for the thread; the customer must never
                # receive it, so it is blanked for a customer-side read.
                seller_label=conversation.seller_label if viewer_side == "seller" else None,
                shopper_name=shopper_name,
                contact_email=contact_email,
                contact_phone=contact_phone,
                last_message_at=conversation.last_message_at,
                last_message_preview=conversation.last_message_preview,
                last_message_author=conversation.last_message_author,
                unread_count=unread_for(conversation, viewer_side),
                store_name=store.name if store else "",
                store_slug=(store.slug or "") if store else "",
                company_slug=(company.slug or "") if company else "",
                created_at=conversation.created_at,
            )
        )
    return summaries


async def append_message(
    db: AsyncSession,
    conversation: StoreChatConversation,
    *,
    sender_type: str,
    kind: str = "text",
    body: str | None = None,
    attachment_url: str | None = None,
    attachment_name: str | None = None,
    attachment_content_type: str | None = None,
    attachment_byte_size: int = 0,
    attachment_duration_ms: int | None = None,
    order_id: UUID | None = None,
    order_number: str | None = None,
    sender_user_id: UUID | None = None,
    sender_shopper_id: UUID | None = None,
) -> StoreChatMessage:
    """Add a message and roll the conversation's denormalised fields forward.

    Counters are incremented for the *other* side only, so an unread badge always
    means "needs your attention" rather than "has any new activity".
    """
    message = StoreChatMessage(
        conversation_id=conversation.id,
        sender_type=sender_type,
        sender_user_id=sender_user_id,
        sender_shopper_id=sender_shopper_id,
        kind=kind,
        body=(body.strip() if body and body.strip() else None),
        attachment_url=attachment_url,
        attachment_name=attachment_name,
        attachment_content_type=attachment_content_type,
        attachment_byte_size=attachment_byte_size or 0,
        attachment_duration_ms=attachment_duration_ms,
        order_id=order_id,
    )
    db.add(message)
    await db.flush()  # assigns ``seq`` from the identity column
    conversation.last_message_at = message.created_at
    conversation.last_message_preview = preview(kind, body, attachment_name, order_number)
    conversation.last_message_author = sender_type
    if sender_type == "customer":
        conversation.seller_unread_count = (conversation.seller_unread_count or 0) + 1
    else:
        conversation.customer_unread_count = (conversation.customer_unread_count or 0) + 1
    conversation.status = "open"
    conversation.updated_at = utcnow()
    return message


async def notify_sellers(db: AsyncSession, conversation: StoreChatConversation, customer_name: str, body: str) -> None:
    """Tell owners and store-linked managers that a customer wrote.

    Mirrors ``notify_company_managers`` for low stock and refunds: one row per
    recipient, no email, and the inbox is the destination. Rows are only created
    for the first unread message of a burst, so a chatty customer cannot bury the
    bell.
    """
    manager_scope = select(MembershipStore.membership_id).where(
        MembershipStore.membership_id == Membership.id, MembershipStore.store_id == conversation.store_id
    ).exists()
    user_ids = (
        await db.execute(
            select(User.id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == conversation.company_id,
                Membership.status == "active",
                Membership.role.in_(["owner", "manager"]),
                or_(Membership.role == "owner", manager_scope),
            )
        )
    ).scalars().all()
    title = f"New message from {customer_name}"
    for user_id in user_ids:
        db.add(
            Notification(
                store_id=conversation.store_id,
                user_id=user_id,
                type="store_chat_message",
                title=title[:200],
                body=body[:600],
                conversation_id=conversation.id,
            )
        )


def newest_first(conversations: list[StoreChatConversation]) -> list[StoreChatConversation]:
    """Sort newest activity first, falling back to creation time.

    Done in Python because ``last_message_at`` is null on an empty thread and the
    listing is already bounded.
    """
    return sorted(conversations, key=lambda c: c.last_message_at or c.created_at, reverse=True)


# How long a thread may sit idle before it closes itself, so an "Open" list means
# something. A new message on a closed thread reopens it (see ``append_message``).
CHAT_IDLE_CLOSE_AFTER = timedelta(days=3)
# Where an unanswered-message alert is recorded in the outbox. Kept within the
# source column's 20 characters.
CHAT_ALERT_SOURCE = "store_chat_alert"


async def close_idle_conversations(db: AsyncSession, store_id: UUID, *, now=None) -> int:
    """Close this store's threads that have been silent for longer than the idle window.

    A sweep rather than a background worker: it rides on the inbox list request,
    which is the only moment the answer is needed, and it is idempotent.
    """
    cutoff = (now or utcnow()) - CHAT_IDLE_CLOSE_AFTER
    result = await db.execute(
        update(StoreChatConversation)
        .where(
            StoreChatConversation.store_id == store_id,
            StoreChatConversation.status == "open",
            StoreChatConversation.last_message_at.is_not(None),
            StoreChatConversation.last_message_at < cutoff,
        )
        .values(status="closed", updated_at=utcnow())
    )
    return result.rowcount or 0


async def _alert_recipients(db: AsyncSession, conversation: StoreChatConversation) -> list[tuple[UUID, str]]:
    """Owners, plus managers linked to this store - the people who can answer."""
    manager_scope = select(MembershipStore.membership_id).where(
        MembershipStore.membership_id == Membership.id, MembershipStore.store_id == conversation.store_id
    ).exists()
    rows = (
        await db.execute(
            select(User.id, User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == conversation.company_id,
                Membership.status == "active",
                Membership.role.in_(["owner", "manager"]),
                or_(Membership.role == "owner", manager_scope),
            )
        )
    ).all()
    return [(row[0], row[1]) for row in rows]


async def run_unanswered_alerts(db: AsyncSession, *, now=None, unanswered_minutes: int | None = None) -> dict:
    """Email the store when a customer message has sat unanswered.

    The in-app bell only helps someone already looking at the app; a store that
    closed at 6pm still needs to learn at 7pm that a customer is waiting. One
    email per recipient per unanswered burst: the conversation records when it was
    last alerted, and a newer customer message makes the thread eligible again.
    """
    now = now or utcnow()
    minutes = settings.chat_alert_unanswered_minutes if unanswered_minutes is None else unanswered_minutes
    cutoff = now - timedelta(minutes=max(1, minutes))
    conversations = (
        await db.execute(
            select(StoreChatConversation)
            .where(
                StoreChatConversation.seller_unread_count > 0,
                StoreChatConversation.last_message_author == "customer",
                StoreChatConversation.last_message_at.is_not(None),
                StoreChatConversation.last_message_at <= cutoff,
                or_(
                    StoreChatConversation.seller_notified_at.is_(None),
                    StoreChatConversation.seller_notified_at < StoreChatConversation.last_message_at,
                ),
            )
            .limit(200)
        )
    ).scalars().all()

    stats = {"alerts": 0, "emails": 0}
    for conversation in conversations:
        store = await db.get(Store, conversation.store_id)
        # Stamp even when we do not send, so a switched-off store is not rescanned
        # every tick.
        conversation.seller_notified_at = now
        if store is None:
            continue
        if not bool(dict(store.preferences or {}).get("chat_unanswered_alerts", True)):
            continue
        recipients = await _alert_recipients(db, conversation)
        if not recipients:
            continue
        shopper = await db.get(ShopperAccount, conversation.shopper_id) if conversation.shopper_id else None
        customer = display_name(conversation, shopper)
        preview = conversation.last_message_preview or "New message"
        html = transactional_email(
            heading=f"{customer} is waiting for a reply",
            preview=preview,
            body=(
                f'<p style="margin:0 0 12px 0;">A message from <strong>{escape(customer)}</strong> '
                f"at {escape(store.name)} has been waiting for a reply.</p>"
                f'<p style="margin:0 0 12px 0;color:#6b6c76;">&ldquo;{escape(preview)}&rdquo;</p>'
            ),
            badge="Chat",
            cta_label="Open the inbox",
            cta_href=f"{settings.frontend_url}/inbox",
        )
        subject = f"Waiting for a reply at {store.name}"
        for user_id, email in recipients:
            db.add(
                EmailSend(
                    user_id=user_id,
                    recipient_email=email,
                    subject=subject,
                    body_html=html,
                    status="queued",
                    source=CHAT_ALERT_SOURCE,
                )
            )
            stats["emails"] += 1
        stats["alerts"] += 1
    await db.flush()
    return stats

"""Live support chat: threads, message rendering and notifications.

This is the merchant <-> Chmaba channel, shaped deliberately like
``app.services.store_chat``: a conversation row carries the unread counters and
last-message preview, each message carries a database ``seq`` cursor, and the
client streams with ``after_seq``. Reusing that model means the support inbox
needs no broker and a reconnecting client misses nothing.

The assistant (``app.services.support``) writes into the same thread. That is the
point of the design: when a merchant asks for a human, the agent opens the thread
with the AI conversation already in front of them instead of a blank ticket.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Company,
    Membership,
    MembershipStore,
    Notification,
    Store,
    SupportChatConversation,
    SupportChatMessage,
    User,
    utcnow,
)
from app.schemas import (
    SupportChatAttachmentRead,
    SupportChatConversationSummary,
    SupportChatMessageRead,
    SupportChatThreadRead,
)
from app.services import activity as activity_service
from app.services import help_repo
from app.services import support as support_service

AI_AUTHOR = "Chmaba assistant"
SYSTEM_AUTHOR = "System"
MAX_PREVIEW = 200


def preview(kind: str, body: str | None, attachment_name: str | None = None) -> str:
    """The one-line summary shown in a conversation list."""
    text = (body or "").strip()
    if text:
        return text[:MAX_PREVIEW]
    if kind == "image":
        return "📷 Photo"
    if kind == "file":
        return f"📎 {attachment_name or 'Attachment'}"[:MAX_PREVIEW]
    return "New message"


def unread_for(conversation: SupportChatConversation, viewer_side: str) -> int:
    return conversation.agent_unread_count if viewer_side == "admin" else conversation.merchant_unread_count


def notification_link(conversation: SupportChatConversation) -> str:
    """Workspace path that opens this thread from the merchant notification bell."""
    return f"support?conversation={conversation.id}"


def admin_thread_link(conversation: SupportChatConversation) -> str | None:
    """Absolute admin URL for the Telegram card, when the host is configured."""
    base = (settings.platform_admin_url or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/support?conversation={conversation.id}"


async def _names(db: AsyncSession, user_ids: set[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    rows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    return {row.id: (row.full_name or row.email or "Chmaba") for row in rows}


async def message_reads(
    db: AsyncSession,
    messages: list[SupportChatMessage],
    viewer_side: str,
) -> list[SupportChatMessageRead]:
    """Serialise messages, resolving the author's display name for this side.

    The merchant sees "You" for their own turns and the agent's real name for a
    reply, so a hand-off does not turn into a wall of anonymous "Support". The
    ops inbox does the mirror image.
    """
    if not messages:
        return []
    author_ids = {message.author_user_id for message in messages if message.author_user_id}
    names = await _names(db, author_ids)
    reads: list[SupportChatMessageRead] = []
    for message in messages:
        if message.author_type == "merchant":
            author_name = "You" if viewer_side == "merchant" else names.get(message.author_user_id, "Merchant")
        elif message.author_type == "agent":
            # Both sides see the agent's name: a shared inbox is easier to read
            # when a colleague's reply is attributed to them, not to "Support".
            author_name = names.get(message.author_user_id, "Support")
        elif message.author_type == "assistant":
            author_name = AI_AUTHOR
        else:
            author_name = SYSTEM_AUTHOR
        attachment = None
        if message.attachment_url:
            attachment = SupportChatAttachmentRead(
                url=message.attachment_url,
                name=message.attachment_name,
                content_type=message.attachment_content_type,
                byte_size=message.attachment_byte_size or 0,
            )
        reads.append(
            SupportChatMessageRead(
                id=message.id,
                seq=message.seq,
                author_type=message.author_type,
                kind=message.kind,
                body=message.body,
                attachment=attachment,
                guide_ids=list(message.guide_ids or []),
                author_name=author_name,
                created_at=message.created_at,
            )
        )
    return reads


async def conversation_summaries(
    db: AsyncSession,
    conversations: list[SupportChatConversation],
    viewer_side: str,
) -> list[SupportChatConversationSummary]:
    """Summaries for a list, resolving store, company and people in one pass."""
    if not conversations:
        return []
    store_ids = {conversation.store_id for conversation in conversations if conversation.store_id}
    company_ids = {conversation.company_id for conversation in conversations}
    user_ids = {conversation.user_id for conversation in conversations if conversation.user_id}
    admin_ids = {conversation.assigned_admin_id for conversation in conversations if conversation.assigned_admin_id}
    stores = {
        store.id: store
        for store in (await db.execute(select(Store).where(Store.id.in_(store_ids)))).scalars().all()
    } if store_ids else {}
    companies = {
        company.id: company
        for company in (await db.execute(select(Company).where(Company.id.in_(company_ids)))).scalars().all()
    } if company_ids else {}
    merchants = {
        user.id: user
        for user in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
    } if user_ids else {}
    admin_names = await _names(db, admin_ids)
    summaries: list[SupportChatConversationSummary] = []
    for conversation in conversations:
        store = stores.get(conversation.store_id)
        company = companies.get(conversation.company_id)
        merchant = merchants.get(conversation.user_id) if conversation.user_id else None
        summaries.append(
            SupportChatConversationSummary(
                id=conversation.id,
                reference=conversation.reference,
                subject=conversation.subject,
                status=conversation.status,
                priority=bool(conversation.priority),
                assigned_admin_id=conversation.assigned_admin_id if viewer_side == "admin" else None,
                assigned_admin_name=(
                    admin_names.get(conversation.assigned_admin_id)
                    if conversation.assigned_admin_id
                    else None
                ),
                merchant_name=(merchant.full_name if merchant else None) if viewer_side == "admin" else None,
                merchant_email=(merchant.email if merchant else None) if viewer_side == "admin" else None,
                company_name=company.name if company else None,
                store_name=store.name if store else None,
                last_message_at=conversation.last_message_at,
                last_message_preview=conversation.last_message_preview,
                last_message_author=conversation.last_message_author,
                unread_count=unread_for(conversation, viewer_side),
                handoff_requested_at=conversation.handoff_requested_at,
                created_at=conversation.created_at,
            )
        )
    return summaries


THREAD_PAGE = 200


async def thread_messages(
    db: AsyncSession,
    conversation_id: UUID,
    *,
    limit: int = THREAD_PAGE,
    before_seq: int | None = None,
) -> list[SupportChatMessage]:
    """The newest page of a thread, in reading order."""
    query = select(SupportChatMessage).where(SupportChatMessage.conversation_id == conversation_id)
    if before_seq is not None:
        query = query.where(SupportChatMessage.seq < before_seq)
    rows = (await db.execute(query.order_by(SupportChatMessage.seq.desc()).limit(limit))).scalars().all()
    return list(reversed(list(rows)))


async def thread_read(
    db: AsyncSession,
    conversation: SupportChatConversation,
    viewer_side: str,
    *,
    before_seq: int | None = None,
) -> SupportChatThreadRead:
    """A conversation plus one page of its thread, shaped for one side."""
    summary = (await conversation_summaries(db, [conversation], viewer_side))[0]
    messages = await thread_messages(db, conversation.id, before_seq=before_seq)
    has_more = False
    if len(messages) >= THREAD_PAGE:
        has_more = bool(
            await db.scalar(
                select(SupportChatMessage.id)
                .where(
                    SupportChatMessage.conversation_id == conversation.id,
                    SupportChatMessage.seq < messages[0].seq,
                )
                .limit(1)
            )
        )
    return SupportChatThreadRead(
        **summary.model_dump(),
        messages=await message_reads(db, messages, viewer_side),
        has_more=has_more,
        internal_notes=conversation.internal_notes if viewer_side == "admin" else None,
        assistant_enabled=conversation.status == "ai",
    )


async def append_message(
    db: AsyncSession,
    conversation: SupportChatConversation,
    *,
    author_type: str,
    body: str | None = None,
    kind: str = "text",
    author_user_id: UUID | None = None,
    attachment_url: str | None = None,
    attachment_name: str | None = None,
    attachment_content_type: str | None = None,
    attachment_byte_size: int = 0,
    guide_ids: list[str] | None = None,
) -> SupportChatMessage:
    """Add a message and roll the conversation's denormalised fields forward.

    Unread counts always describe the *other* side. An assistant turn is not
    unread for the merchant (they are watching it stream), and an AI-only thread
    does not raise the ops badge - the ops inbox lists those threads, but a badge
    that every AI answer increments would be noise rather than a call to action.
    """
    text = (body or "").strip() or None
    message = SupportChatMessage(
        conversation_id=conversation.id,
        author_type=author_type,
        author_user_id=author_user_id,
        kind=kind,
        body=text,
        attachment_url=attachment_url,
        attachment_name=attachment_name,
        attachment_content_type=attachment_content_type,
        attachment_byte_size=attachment_byte_size or 0,
        guide_ids=guide_ids or None,
    )
    db.add(message)
    await db.flush()  # assigns ``seq`` from the identity column
    conversation.last_message_at = message.created_at
    conversation.last_message_preview = preview(kind, text, attachment_name)
    conversation.last_message_author = author_type
    conversation.updated_at = utcnow()
    if author_type == "merchant":
        if conversation.status in {"resolved", "closed"}:
            conversation.status = "live" if conversation.assigned_admin_id else "waiting"
            conversation.resolved_at = None
        if conversation.status in {"waiting", "live"}:
            conversation.agent_unread_count = (conversation.agent_unread_count or 0) + 1
    elif author_type == "agent":
        conversation.status = "live"
        conversation.merchant_unread_count = (conversation.merchant_unread_count or 0) + 1
        # The merchant now has an answer, so the next message starts a new burst.
        conversation.agent_alert_pending = False
    return message


async def append_message_standalone(
    conversation_id: UUID,
    *,
    author_type: str,
    body: str,
    guide_ids: list[str] | None = None,
) -> None:
    """Persist an assistant turn after a streamed response has finished.

    The request's session may already be closing as the stream ends, so this
    opens its own short-lived session, exactly like the existing assistant chat.
    """
    from app.db import SessionLocal

    async with SessionLocal() as db:
        conversation = await db.get(SupportChatConversation, conversation_id)
        if conversation is None:
            return
        await append_message(
            db,
            conversation,
            author_type=author_type,
            body=body,
            guide_ids=guide_ids,
        )
        await db.commit()


async def clear_merchant_notifications(db: AsyncSession, conversation: SupportChatConversation, user_id: UUID) -> None:
    """Mark this merchant's bell entries for the thread read, matching the inbox."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.link == notification_link(conversation),
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )


async def notify_merchant_of_agent_reply(
    db: AsyncSession,
    conversation: SupportChatConversation,
    body: str,
) -> None:
    """Ring the merchant's in-app bell after a human replies.

    The thread owner plus the workspace's active owners and managers are
    notified, deduplicated. Notifications are store-scoped; a thread whose store
    was deleted simply has no bell entry (the agent reply is still in the thread).
    """
    if conversation.store_id is None:
        return
    recipient_ids: set[UUID] = set()
    if conversation.user_id is not None:
        recipient_ids.add(conversation.user_id)
    manager_ids = (
        await db.execute(
            select(User.id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == conversation.company_id,
                Membership.status == "active",
                Membership.role.in_(["owner", "manager"]),
            )
        )
    ).scalars().all()
    recipient_ids.update(manager_ids)
    snippet = (body or "").strip()[:600] or "Open the conversation to read it."
    for user_id in recipient_ids:
        db.add(
            Notification(
                store_id=conversation.store_id,
                user_id=user_id,
                type="support_chat_message",
                title="Support replied to your chat",
                body=snippet,
                link=notification_link(conversation),
            )
        )


async def notify_agent_group(
    db: AsyncSession,
    conversation: SupportChatConversation,
    *,
    handoff: bool = False,
    note: str | None = None,
) -> None:
    """Ping the internal ops Telegram group about a thread that needs a human.

    One alert per unanswered burst. ``agent_alert_pending`` is set by the first
    alert (a hand-off or the first message of a burst) and cleared only when an
    agent replies, so a chatty merchant cannot flood the group. The activity row
    also gives the ops activity feed the same record it has for escalations.
    """
    if conversation.agent_alert_pending:
        return
    store = await db.get(Store, conversation.store_id) if conversation.store_id else None
    merchant = await db.get(User, conversation.user_id) if conversation.user_id else None
    link = admin_thread_link(conversation)
    details = {
        "company": (await db.get(Company, conversation.company_id)).name if conversation.company_id else None,
        "store": store.name if store else None,
        "reference": conversation.reference,
        "topic": conversation.subject,
        "question": (note or conversation.last_message_preview or "")[:500] or None,
        "email": merchant.email if merchant else None,
        "link": link,
    }
    await activity_service.record_activity(
        db,
        "support.chat_handoff" if handoff else "support.chat_waiting",
        user=merchant,
        company_id=conversation.company_id,
        store_id=conversation.store_id,
        details=details,
    )
    conversation.agent_notified_at = utcnow()
    conversation.agent_alert_pending = True


async def suggest_reply(db: AsyncSession, conversation: SupportChatConversation) -> dict:
    """Draft an agent reply grounded in the help corpus, flagging whether it matched."""
    rows = (
        await db.execute(
            select(SupportChatMessage)
            .where(SupportChatMessage.conversation_id == conversation.id)
            .order_by(SupportChatMessage.seq.desc())
            .limit(12)
        )
    ).scalars().all()
    messages = list(reversed(list(rows)))
    question = next(
        (message.body for message in reversed(messages) if message.author_type == "merchant" and message.body),
        conversation.subject or "",
    )
    history = [
        {"role": "assistant" if message.author_type in {"agent", "assistant"} else "user", "content": message.body}
        for message in messages
        if message.body and message.author_type in {"merchant", "agent", "assistant"}
    ]
    if not question:
        return {"body": "", "matched": False, "guide_ids": [], "provider": None, "model": None}
    company = await db.get(Company, conversation.company_id)
    result = await support_service.answer(
        db,
        question=question,
        history=history,
        vertical=getattr(company, "vertical", None),
        role=None,
        store_id=conversation.store_id,
        company_id=conversation.company_id,
        language="en",
    )
    corpus = await help_repo.load_sections(db)
    matched = support_service.retrieval_matched(
        question=question,
        vertical=getattr(company, "vertical", None),
        role=None,
        language="en",
        corpus=corpus,
    )
    return {
        "body": (result.get("answer") or "").strip(),
        "matched": matched,
        "guide_ids": result.get("guide_ids") or [],
        "provider": result.get("provider"),
        "model": result.get("model"),
    }


# In-process typing state: (conversation id, side) -> last typing timestamp. The
# API stays a single process, so this is the whole truth and needs no broker.
TYPING_TTL_SECONDS = 5
_TYPING: dict[tuple[UUID, str], object] = {}


def mark_typing(conversation_id: UUID, side: str) -> None:
    _TYPING[(conversation_id, side)] = utcnow()


def is_typing(conversation_id: UUID, side: str, *, now=None) -> bool:
    now = now or utcnow()
    stamp = _TYPING.get((conversation_id, side))
    if stamp is None:
        return False
    if (now - stamp).total_seconds() > TYPING_TTL_SECONDS:
        _TYPING.pop((conversation_id, side), None)
        return False
    return True


async def agent_recipient_ids(db: AsyncSession, conversation: SupportChatConversation) -> set[UUID]:
    """Owners and store-linked managers who can pick the thread up.

    Exposed for tests and for any future email fallback; the live path only needs
    the Telegram alert, which does not address individual people.
    """
    manager_scope = select(MembershipStore.membership_id).where(
        MembershipStore.membership_id == Membership.id,
        MembershipStore.store_id == conversation.store_id,
    ).exists()
    rows = (
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
    return set(rows)

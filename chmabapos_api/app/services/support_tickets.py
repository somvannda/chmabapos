"""Human support tickets: attachments and thread rendering.

The AI assistant lives in ``app.services.support``; this module is about the
human hand-off (``support_tickets`` / ``support_ticket_messages``). It owns the
two pieces both the merchant API and the admin API need: claiming staged image
uploads when a request or reply is submitted, and rendering a ticket with its
attachments grouped by message.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    Membership,
    Notification,
    SupportTicket,
    SupportTicketAttachment,
    SupportTicketMessage,
    User,
)
from app.schemas import (
    SupportTicketAttachmentRead,
    SupportTicketDetailRead,
    SupportTicketMessageRead,
    SupportTicketRead,
)
from app.services import ai as ai_service
from app.services import help_repo
from app.services import support as support_service


async def bind_attachments(
    db: AsyncSession,
    *,
    company_id: UUID,
    ticket_id: UUID,
    message_id: UUID | None,
    attachment_ids: list[UUID],
) -> list[SupportTicketAttachment]:
    """Claim staged uploads for a ticket and (optionally) one of its messages.

    Uploads start unowned (``ticket_id`` is NULL) so a client can attach images
    to the request or reply it is still composing. Only the caller's own,
    still-unowned rows are claimed; an unknown, foreign or already-claimed id
    raises ``ValueError`` which the endpoint turns into a 400. That keeps one
    tenant from attaching another tenant's media, and stops a staged row from
    being claimed twice.
    """
    if not attachment_ids:
        return []
    unique_ids = list(dict.fromkeys(attachment_ids))
    rows = (
        await db.execute(
            select(SupportTicketAttachment).where(
                SupportTicketAttachment.id.in_(unique_ids),
                SupportTicketAttachment.company_id == company_id,
                SupportTicketAttachment.ticket_id.is_(None),
            )
        )
    ).scalars().all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(unique_ids):
        raise ValueError("One or more attachments could not be found")
    bound: list[SupportTicketAttachment] = []
    for position, attachment_id in enumerate(unique_ids):
        row = by_id[attachment_id]
        row.ticket_id = ticket_id
        row.message_id = message_id
        row.position = position
        bound.append(row)
    return bound


async def ticket_detail_read(
    db: AsyncSession,
    ticket: SupportTicket,
    *,
    include_system: bool = False,
) -> SupportTicketDetailRead:
    """Render a ticket and its thread, with attachments grouped by message.

    ``include_system`` is False for the merchant (assistant context hidden) and
    True for the operations inbox. Opening-question attachments are returned at
    the top level; each message carries its own.
    """
    messages = (
        await db.execute(
            select(SupportTicketMessage)
            .where(SupportTicketMessage.ticket_id == ticket.id)
            .order_by(SupportTicketMessage.created_at)
        )
    ).scalars().all()
    attachments = (
        await db.execute(
            select(SupportTicketAttachment)
            .where(SupportTicketAttachment.ticket_id == ticket.id)
            .order_by(SupportTicketAttachment.position, SupportTicketAttachment.created_at)
        )
    ).scalars().all()
    by_message: dict[UUID | None, list[SupportTicketAttachmentRead]] = {}
    for attachment in attachments:
        by_message.setdefault(attachment.message_id, []).append(
            SupportTicketAttachmentRead.model_validate(attachment)
        )
    visible = [message for message in messages if include_system or message.author_type != "system"]
    return SupportTicketDetailRead(
        **SupportTicketRead.model_validate(ticket).model_dump(),
        attachments=by_message.get(None, []),
        messages=[
            SupportTicketMessageRead(
                id=message.id,
                author_type=message.author_type,
                body=message.body,
                created_at=message.created_at,
                attachments=by_message.get(message.id, []),
            )
            for message in visible
        ],
    )


async def notify_ticket_merchants(
    db: AsyncSession,
    *,
    ticket: SupportTicket,
    kind: str,
    title: str,
    body: str | None = None,
) -> None:
    """Ring the in-app bell for the merchant workspace after support acts.

    Notifications are store-scoped, so a ticket whose store was deleted cannot
    produce one. The ticket author and the workspace's active owners/managers
    are notified, deduplicated. The caller commits the session.
    """
    if ticket.store_id is None:
        return
    recipient_ids: set[UUID] = set()
    if ticket.user_id is not None:
        recipient_ids.add(ticket.user_id)
    manager_ids = (
        await db.execute(
            select(User.id)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.company_id == ticket.company_id,
                Membership.status == "active",
                Membership.role.in_(["owner", "manager"]),
            )
        )
    ).scalars().all()
    recipient_ids.update(manager_ids)
    snippet = (body or "").strip()[:600] or None
    for user_id in recipient_ids:
        db.add(Notification(store_id=ticket.store_id, user_id=user_id, type=kind, title=title, body=snippet))


# --- AI-assisted replies -------------------------------------------------------
#
# The support team (admin) can ask the assistant to rewrite a draft reply, or to
# draft one on its own when the help corpus already covers the merchant's issue.
# Both reuse the existing provider plumbing in ``app.services.ai`` and the
# grounded answer path in ``app.services.support``, so no new provider logic or
# schema is introduced.

AI_REPLY_SYSTEM = (
    "You are a customer-support agent for Chmaba, a cloud point-of-sale used by "
    "retail shops in Cambodia.\n"
    "You help the human support team turn rough notes into the reply a merchant "
    "receives by email.\n"
    "Rules:\n"
    "- Write warm, clear, professional prose the merchant can act on.\n"
    "- Keep it concise; prefer short paragraphs or numbered steps.\n"
    "- Never invent features, prices, policies, timelines or steps that were not "
    "given to you in the conversation or the instructions.\n"
    "- If a draft already answers the question, keep its meaning and only improve "
    "the wording.\n"
    "- Do not mention that a machine wrote this, add a subject line, or use markdown.\n"
    "- Return plain text only."
)

AI_CONTEXT_MESSAGES = 12


async def _ticket_messages(db: AsyncSession, ticket_id: UUID) -> list[SupportTicketMessage]:
    rows = await db.execute(
        select(SupportTicketMessage)
        .where(SupportTicketMessage.ticket_id == ticket_id)
        .order_by(SupportTicketMessage.created_at)
    )
    return list(rows.scalars().all())


def _conversation_context(ticket: SupportTicket, messages: list[SupportTicketMessage], *, limit: int = AI_CONTEXT_MESSAGES) -> str:
    lines = [f"Merchant's original request: {ticket.question}"]
    for message in messages[-limit:]:
        if message.author_type == "system":
            continue
        speaker = "Support team" if message.author_type == "agent" else "Merchant"
        lines.append(f"{speaker}: {message.body}")
    return "\n".join(lines)


async def _record_ai_usage(result: dict[str, Any], company_id: UUID | None) -> None:
    usage = dict(result.get("usage") or {})
    usage.setdefault("provider", result.get("provider"))
    usage.setdefault("model", result.get("model"))
    await support_service.record_usage(usage=usage, company_id=company_id)


async def rewrite_reply(
    db: AsyncSession,
    *,
    ticket: SupportTicket,
    draft: str = "",
    instruction: str | None = None,
    tone: str | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Rewrite an agent's draft reply (or write one when the draft is empty)."""
    messages = await _ticket_messages(db, ticket.id)
    parts = [
        f"Support ticket {ticket.reference} conversation so far:\n{_conversation_context(ticket, messages)}",
        "",
    ]
    if draft and draft.strip():
        parts.append(f"Current draft reply from our support team:\n{draft.strip()}")
    else:
        parts.append("There is no draft yet. Write a reply to the merchant's request.")
    if instruction:
        parts.append(f"Extra instruction: {instruction.strip()}")
    if tone:
        parts.append(f"Tone: {tone.strip()}")
    if language == "km":
        parts.append("Reply in Khmer (ភាសាខ្មែរ).")
    result = await ai_service.complete_chat(
        db,
        system=AI_REPLY_SYSTEM,
        messages=[{"role": "user", "content": "\n".join(parts)}],
        temperature=0.4,
        max_tokens=settings.support_max_output_tokens,
    )
    await _record_ai_usage(result, ticket.company_id)
    return {"body": (result.get("content") or "").strip(), "provider": result.get("provider"), "model": result.get("model")}


async def suggest_reply(
    db: AsyncSession,
    *,
    ticket: SupportTicket,
    vertical: str | None = None,
    role: str | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Draft a reply grounded in the help corpus, flagging whether it matched."""
    messages = await _ticket_messages(db, ticket.id)
    history = [
        {"role": "assistant" if message.author_type == "agent" else "user", "content": message.body}
        for message in messages[-AI_CONTEXT_MESSAGES:]
        if message.author_type in ("agent", "merchant")
    ]
    result = await support_service.answer(
        db,
        question=ticket.question,
        history=history,
        vertical=vertical,
        role=role,
        store_id=ticket.store_id,
        company_id=ticket.company_id,
        language=language,
    )
    corpus = await help_repo.load_sections(db)
    matched = support_service.retrieval_matched(
        question=ticket.question, vertical=vertical, role=role, language=language, corpus=corpus
    )
    return {
        "body": (result.get("answer") or "").strip(),
        "matched": matched,
        "guide_ids": result.get("guide_ids") or [],
        "provider": result.get("provider"),
        "model": result.get("model"),
    }

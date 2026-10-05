"""Human support tickets: attachments and thread rendering.

The AI assistant lives in ``app.services.support``; this module is about the
human hand-off (``support_tickets`` / ``support_ticket_messages``). It owns the
two pieces both the merchant API and the admin API need: claiming staged image
uploads when a request or reply is submitted, and rendering a ticket with its
attachments grouped by message.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

"""copy pre-unification assistant conversations into the live support inbox

Before live support chat, Ask Chmaba stored its rolling conversation in
``support_conversations`` / ``support_messages``. Those questions were invisible
to the ops inbox. This migration copies each non-empty conversation into
``support_chat_conversations`` / ``support_chat_messages`` as a **closed**
history thread, preserving the original timestamps and the assistant's answers.
The source tables are left untouched.

References use the ``SUP-H`` prefix, which cannot collide with the six-hex
references generated for live threads (``H`` is not a hex digit).

Revision ID: b7e2f4a8c1d6
Revises: a5b7c9d1e3f5
Create Date: 2026-11-13
"""
from __future__ import annotations

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2f4a8c1d6"
down_revision: Union[str, None] = "a5b7c9d1e3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

HISTORY_REFERENCE_PREFIX = "SUP-H"


def _author_type(role: str | None) -> str:
    if role == "user":
        return "merchant"
    if role == "assistant":
        return "assistant"
    return "system"


def _copy_messages(bind, conversation_id: uuid.UUID, new_id: uuid.UUID, user_id) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT role, content, guide_ids, created_at FROM support_messages "
            "WHERE conversation_id = :conversation_id ORDER BY created_at, id"
        ),
        {"conversation_id": conversation_id},
    ).mappings().all()
    for row in rows:
        author_type = _author_type(row["role"])
        guides = row["guide_ids"]
        bind.execute(
            sa.text(
                """
                INSERT INTO support_chat_messages
                    (id, conversation_id, author_type, author_user_id, kind, body,
                     attachment_url, attachment_name, attachment_content_type,
                     attachment_byte_size, guide_ids, created_at)
                VALUES
                    (:id, :conversation_id, :author_type, :author_user_id, 'text', :body,
                     NULL, NULL, NULL, 0, CAST(:guide_ids AS json), :created_at)
                """
            ),
            {
                "id": uuid.uuid4(),
                "conversation_id": new_id,
                "author_type": author_type,
                "author_user_id": user_id if author_type == "merchant" else None,
                "body": row["content"],
                "guide_ids": json.dumps(guides) if guides is not None else None,
                "created_at": row["created_at"],
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    conversations = bind.execute(
        sa.text(
            "SELECT id, company_id, user_id, title, created_at, updated_at "
            "FROM support_conversations ORDER BY created_at, id"
        )
    ).mappings().all()
    for conversation in conversations:
        last = bind.execute(
            sa.text(
                "SELECT role, content, created_at FROM support_messages "
                "WHERE conversation_id = :conversation_id ORDER BY created_at DESC, id DESC LIMIT 1"
            ),
            {"conversation_id": conversation["id"]},
        ).mappings().first()
        if last is None:
            continue
        new_id = uuid.uuid4()
        reference = f"{HISTORY_REFERENCE_PREFIX}{conversation['id'].hex[:7].upper()}"
        preview = (last["content"] or "").strip()[:200] or None
        bind.execute(
            sa.text(
                """
                INSERT INTO support_chat_conversations
                    (id, reference, company_id, store_id, user_id, subject, status, priority,
                     assigned_admin_id, internal_notes, last_message_at, last_message_preview,
                     last_message_author, merchant_unread_count, agent_unread_count,
                     merchant_read_at, agent_read_at, merchant_delivered_at, agent_delivered_at,
                     agent_notified_at, agent_alert_pending, handoff_requested_at, resolved_at,
                     created_at, updated_at)
                VALUES
                    (:id, :reference, :company_id, NULL, :user_id, :subject, 'closed', false,
                     NULL, NULL, :last_message_at, :last_message_preview,
                     :last_message_author, 0, 0,
                     :read_at, :read_at, :read_at, :read_at,
                     NULL, false, NULL, :resolved_at,
                     :created_at, :updated_at)
                """
            ),
            {
                "id": new_id,
                "reference": reference,
                "company_id": conversation["company_id"],
                "user_id": conversation["user_id"],
                "subject": (conversation["title"] or "Historical assistant chat")[:200],
                "last_message_at": last["created_at"] or conversation["updated_at"],
                "last_message_preview": preview,
                "last_message_author": _author_type(last["role"]),
                "read_at": conversation["updated_at"],
                "resolved_at": conversation["updated_at"],
                "created_at": conversation["created_at"],
                "updated_at": conversation["updated_at"],
            },
        )
        _copy_messages(bind, conversation["id"], new_id, conversation["user_id"])


def downgrade() -> None:
    # Messages cascade from the conversation row.
    op.get_bind().execute(
        sa.text("DELETE FROM support_chat_conversations WHERE reference LIKE :prefix"),
        {"prefix": f"{HISTORY_REFERENCE_PREFIX}%"},
    )

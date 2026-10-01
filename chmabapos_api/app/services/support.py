"""Support assistant: answers questions about how to use Chmaba.

Every answer is grounded in the help corpus (``app.support_content``) so the model
does not invent UI steps or features. Provider selection, key handling and errors
are reused from ``app.services.ai``.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import support_content
from app.config import settings
from app.db import SessionLocal
from app.models import SupportConversation, SupportMessage, utcnow
from app.services import ai as ai_service

MAX_TURN_CHARS = 2000
MAX_GUIDE_SECTIONS = 6

# In-process sliding-window limiter. The current deployment is a single API
# process; if the API scales to multiple workers this should move to shared
# storage (Redis or a DB counter) so the limit is global rather than per worker.
_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, *, limit: int, window_seconds: int = 3600) -> bool:
    """Return True and record the call when under the limit, else False.

    A non-positive limit disables limiting (useful in tests).
    """
    if limit <= 0:
        return True
    now = time.monotonic()
    window = _rate_windows[key]
    while window and now - window[0] > window_seconds:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True

SYSTEM_PROMPT = (
    "You are Chmaba's in-app support assistant for a cloud point-of-sale used by "
    "retail shops in Cambodia.\n"
    "Rules:\n"
    "- Answer only questions about using the Chmaba app (setup, selling, inventory, "
    "team, billing). Politely decline anything else.\n"
    "- Ground every claim in the GUIDES below. Never invent features, prices, menu "
    "locations or steps.\n"
    "- If the guides do not cover the question, say so and suggest the Help & support "
    "page or contacting support.\n"
    "- Be concise and concrete. Prefer short numbered steps that match what the user "
    "sees on screen.\n"
    "- Never ask for passwords, card numbers or other secrets."
)


def _format_guides(sections: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for section in sections:
        for article in section.get("articles", []):
            lines.append(f"### {article['title']}")
            for step in article.get("steps", []):
                lines.append(f"- {step}")
            if article.get("tip"):
                lines.append(f"Tip: {article['tip']}")
    return "\n".join(lines)


def _clamp_history(history: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for turn in (history or [])[-settings.support_max_history_turns:]:
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        cleaned.append(
            {
                "role": "assistant" if turn.get("role") == "assistant" else "user",
                "content": content[:MAX_TURN_CHARS],
            }
        )
    return cleaned


def build_prompt(
    *,
    question: str,
    history: list[dict[str, Any]] | None,
    vertical: str | None,
    role: str | None,
) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    """Return ``(system, messages, guides)`` for a question.

    ``guides`` are ``{"id", "title"}`` pairs used to cite sources in the UI.
    Retrieval is scoped to the caller's company vertical and role, so a workspace
    can only ever be grounded in guidance meant for it. Shared by the one-shot and
    streaming answers so both are grounded identically.
    """
    cleaned_question = (question or "").strip()[: settings.support_max_question_chars]
    if not cleaned_question:
        raise ValueError("Ask a question to get started.")

    sections = support_content.articles_for(vertical=vertical, role=role, query=cleaned_question)
    if not sections:
        # Nothing matched the search; fall back to everything the caller can see.
        sections = support_content.articles_for(vertical=vertical, role=role)
    sections = sections[:MAX_GUIDE_SECTIONS]

    guides = [
        {"id": article["id"], "title": article["title"]}
        for section in sections
        for article in section.get("articles", [])
    ]
    guides_text = _format_guides(sections) or "(no matching guides)"
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Business type: {vertical or 'general'}. User role: {role or 'owner'}.\n\n"
        f"GUIDES:\n{guides_text}"
    )
    messages = [*_clamp_history(history), {"role": "user", "content": cleaned_question}]
    return system, messages, guides


async def answer(
    db: AsyncSession,
    *,
    question: str,
    history: list[dict[str, Any]] | None,
    vertical: str | None,
    role: str | None,
) -> dict[str, Any]:
    """Answer a how-to question, grounded in guides the caller is allowed to see."""
    system, messages, guides = build_prompt(question=question, history=history, vertical=vertical, role=role)
    result = await ai_service.complete_chat(
        db,
        system=system,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.support_max_output_tokens,
    )
    return {
        "answer": (result.get("content") or "").strip(),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "guide_ids": [guide["id"] for guide in guides],
    }


async def stream_answer(
    db: AsyncSession,
    *,
    question: str,
    history: list[dict[str, Any]] | None,
    vertical: str | None,
    role: str | None,
) -> AsyncIterator[str]:
    """Yield answer text progressively, grounded exactly like ``answer``."""
    system, messages, _guides = build_prompt(question=question, history=history, vertical=vertical, role=role)
    async for chunk in ai_service.stream_chat(
        db,
        system=system,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.support_max_output_tokens,
    ):
        yield chunk


# --- Conversation persistence -------------------------------------------------

CONVERSATION_TITLE_CHARS = 80


def _title_from(question: str) -> str:
    text = " ".join((question or "").split())
    if not text:
        return "New chat"
    return text[:CONVERSATION_TITLE_CHARS] + ("�" if len(text) > CONVERSATION_TITLE_CHARS else "")


async def resolve_conversation(
    db: AsyncSession,
    *,
    company_id,
    user_id,
    conversation_id,
    question: str,
) -> "SupportConversation":
    """Return the caller's conversation, creating one when none is given.

    A conversation id that does not belong to the caller's company and user is
    treated as not found, so a workspace can never read or append to another's.
    """
    if conversation_id is not None:
        row = (
            await db.execute(
                select(SupportConversation).where(
                    SupportConversation.id == conversation_id,
                    SupportConversation.company_id == company_id,
                    SupportConversation.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise LookupError("Conversation not found")
        return row
    row = SupportConversation(company_id=company_id, user_id=user_id, title=_title_from(question))
    db.add(row)
    await db.flush()
    return row


async def add_message(
    db: AsyncSession,
    *,
    conversation_id,
    role: str,
    content: str,
    guide_ids: list[str] | None = None,
) -> "SupportMessage":
    row = SupportMessage(conversation_id=conversation_id, role=role, content=content, guide_ids=guide_ids or None)
    db.add(row)
    # Bump the thread so listings sort by recency.
    conversation = await db.get(SupportConversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = utcnow()
    await db.flush()
    return row


async def add_message_standalone(*, conversation_id, role: str, content: str, guide_ids: list[str] | None = None) -> None:
    """Persist a message on its own session (used after a stream completes)."""
    async with SessionLocal() as session:
        await add_message(session, conversation_id=conversation_id, role=role, content=content, guide_ids=guide_ids)
        await session.commit()


async def list_conversations(db: AsyncSession, *, company_id, user_id, limit: int = 50) -> list["SupportConversation"]:
    rows = await db.execute(
        select(SupportConversation)
        .where(SupportConversation.company_id == company_id, SupportConversation.user_id == user_id)
        .order_by(SupportConversation.updated_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())


async def conversation_with_messages(db: AsyncSession, *, conversation_id, company_id, user_id):
    """Return ``(conversation, messages)`` scoped to the caller, or ``None``."""
    conversation = (
        await db.execute(
            select(SupportConversation).where(
                SupportConversation.id == conversation_id,
                SupportConversation.company_id == company_id,
                SupportConversation.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        return None
    messages = await db.execute(
        select(SupportMessage).where(SupportMessage.conversation_id == conversation_id).order_by(SupportMessage.created_at)
    )
    return conversation, list(messages.scalars().all())


async def delete_conversation(db: AsyncSession, *, conversation_id, company_id, user_id) -> bool:
    conversation = (
        await db.execute(
            select(SupportConversation).where(
                SupportConversation.id == conversation_id,
                SupportConversation.company_id == company_id,
                SupportConversation.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        return False
    await db.delete(conversation)
    return True

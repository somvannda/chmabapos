"""Support assistant: answers questions about how to use Chmaba.

Every answer is grounded in the help corpus (``app.support_content``) so the model
does not invent UI steps or features. Provider selection, key handling and errors
are reused from ``app.services.ai``.
"""
from __future__ import annotations

import re
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
from app.services import support_tools

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
    "- Never ask for passwords, card numbers or other secrets.\n"
    "- When LIVE STORE DATA is provided, use it to answer questions about the "
    "merchant's own stock or sales. Quote those numbers exactly and never invent "
    "data that is not in it."
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
    live_data: str | None = None,
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
    data_text = (
        f"\n\nLIVE STORE DATA (read-only, from the merchant's own store; use it to answer data questions):\n{live_data}"
        if live_data
        else ""
    )
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Business type: {vertical or 'general'}. User role: {role or 'owner'}.\n\n"
        f"GUIDES:\n{guides_text}{data_text}"
    )
    messages = [*_clamp_history(history), {"role": "user", "content": cleaned_question}]
    return system, messages, guides


_STOCK_WORDS = ("stock", "on hand", "how many", "quantity", "left", "reorder", "out of stock")
_SALES_WORDS = ("sales", "revenue", "sold", "turnover", "earnings", "how much did", "how much have")
_SKU_RE = re.compile(r"sku[:\s#-]*([a-z0-9][a-z0-9-]*)", re.IGNORECASE)


async def collect_live_data(db: AsyncSession, *, question: str, store_id, company_id=None) -> str | None:
    """Return a short read-only store data block for a data question, else ``None``.

    Only store-scoped read-only queries run, and only when the question looks like
    it is about stock or sales. Ordinary how-to questions return ``None`` so the
    assistant stays grounded in the help corpus.
    """
    if store_id is None:
        return None
    q = (question or "").lower()
    parts: list[str] = []
    sku_match = _SKU_RE.search(question or "")
    if sku_match and company_id is not None:
        matches = await support_tools.find_products(db, company_id=company_id, store_id=store_id, term=sku_match.group(1))
        if matches:
            lines = [
                f"- {row['name']} (SKU {row['sku']}): {row['on_hand'] if row['on_hand'] is not None else 'not tracked'} on hand, price {row['price']}"
                for row in matches
            ]
            parts.append("Matching products:\n" + "\n".join(lines))
    if any(word in q for word in _STOCK_WORDS):
        rows = await support_tools.low_stock(db, store_id=store_id)
        if rows:
            lines = [
                f"- {row['name']} (SKU {row['sku']}): {row['on_hand']} on hand, reorder at {row['reorder_point']}"
                for row in rows
            ]
            parts.append("Items at or below their reorder point:\n" + "\n".join(lines))
    if any(word in q for word in _SALES_WORDS):
        days = 1 if "today" in q else 7 if "week" in q else 30 if "month" in q else 1
        summary = await support_tools.sales_summary(db, store_id=store_id, days=days)
        parts.append(
            f"Sales in the last {summary['days']} day(s): {summary['transactions']} paid transactions, "
            f"total {summary['total']} {summary['currency']}."
        )
    return "\n\n".join(parts) if parts else None


async def answer(
    db: AsyncSession,
    *,
    question: str,
    history: list[dict[str, Any]] | None,
    vertical: str | None,
    role: str | None,
    store_id=None,
    company_id=None,
) -> dict[str, Any]:
    """Answer a how-to or data question, grounded in guides and the caller's store."""
    live_data = await collect_live_data(db, question=question, store_id=store_id, company_id=company_id)
    system, messages, guides = build_prompt(question=question, history=history, vertical=vertical, role=role, live_data=live_data)
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
    store_id=None,
    company_id=None,
) -> AsyncIterator[str]:
    """Yield answer text progressively, grounded exactly like ``answer``."""
    live_data = await collect_live_data(db, question=question, store_id=store_id, company_id=company_id)
    system, messages, _guides = build_prompt(question=question, history=history, vertical=vertical, role=role, live_data=live_data)
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

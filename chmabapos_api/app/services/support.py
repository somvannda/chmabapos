"""Support assistant: answers questions about how to use Chmaba.

Every answer is grounded in the help corpus (``app.support_content``) so the model
does not invent UI steps or features. Provider selection, key handling and errors
are reused from ``app.services.ai``.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import support_content
from app.services import ai as ai_service

MAX_HISTORY_TURNS = 8
MAX_QUESTION_CHARS = 1000
MAX_TURN_CHARS = 2000
MAX_GUIDE_SECTIONS = 6

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
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
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


async def answer(
    db: AsyncSession,
    *,
    question: str,
    history: list[dict[str, Any]] | None,
    vertical: str | None,
    role: str | None,
) -> dict[str, Any]:
    """Answer a how-to question, grounded in guides the caller is allowed to see.

    Retrieval is scoped to the caller's company vertical and role, so a workspace
    can only ever be grounded in guidance meant for it.
    """
    cleaned_question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not cleaned_question:
        raise ValueError("Ask a question to get started.")

    sections = support_content.articles_for(vertical=vertical, role=role, query=cleaned_question)
    if not sections:
        # Nothing matched the search; fall back to everything the caller can see.
        sections = support_content.articles_for(vertical=vertical, role=role)
    sections = sections[:MAX_GUIDE_SECTIONS]

    guide_ids = [article["id"] for section in sections for article in section.get("articles", [])]
    guides_text = _format_guides(sections) or "(no matching guides)"
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Business type: {vertical or 'general'}. User role: {role or 'owner'}.\n\n"
        f"GUIDES:\n{guides_text}"
    )
    messages = [*_clamp_history(history), {"role": "user", "content": cleaned_question}]

    result = await ai_service.complete_chat(
        db,
        system=system,
        messages=messages,
        temperature=0.3,
        max_tokens=800,
    )
    return {
        "answer": (result.get("content") or "").strip(),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "guide_ids": guide_ids,
    }

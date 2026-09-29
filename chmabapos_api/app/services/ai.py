"""AI drafting for the admin Mailing tool.

Platform admins configure one provider (ChatGPT, DeepSeek or Claude) from the
admin panel; the key is stored in ``platform_settings`` and never returned to
the browser. The helper here turns a short operator instruction into a subject
and an HTML body that the operator can review, edit and send.

Settings are provider-agnostic: OpenAI and DeepSeek speak the OpenAI
``/chat/completions`` dialect, Anthropic uses ``/messages``. No SDK is pulled
in; a plain ``httpx`` POST keeps the dependency surface tiny.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import PlatformSetting

AI_SETTING_KEYS: tuple[str, ...] = ("ai_provider", "ai_api_key", "ai_model", "ai_base_url")

_ENV_AI_DEFAULTS: dict[str, str | None] = {
    "ai_provider": settings.ai_provider,
    "ai_api_key": settings.ai_api_key,
    "ai_model": settings.ai_model,
    "ai_base_url": settings.ai_base_url,
}


@dataclass(frozen=True)
class Provider:
    code: str
    label: str
    base_url: str
    default_model: str
    dialect: str  # "openai" | "anthropic"


PROVIDERS: tuple[Provider, ...] = (
    Provider("openai", "ChatGPT (OpenAI)", "https://api.openai.com/v1", "gpt-4o-mini", "openai"),
    Provider("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", "openai"),
    Provider("anthropic", "Claude (Anthropic)", "https://api.anthropic.com/v1", "claude-3-5-sonnet-latest", "anthropic"),
)

_PROVIDER_BY_CODE = {provider.code: provider for provider in PROVIDERS}


class AIError(Exception):
    """A configured-but-failing AI call; the router turns this into a 502."""


def provider_catalog() -> list[dict[str, str]]:
    return [
        {"code": provider.code, "label": provider.label, "default_model": provider.default_model, "base_url": provider.base_url}
        for provider in PROVIDERS
    ]


async def load_ai_settings(db: AsyncSession) -> dict[str, str | None]:
    """Return effective AI settings (DB overrides, else env defaults)."""
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key.in_(AI_SETTING_KEYS)))
    overrides = {row.key: row.value for row in result.scalars().all() if row.value not in (None, "")}
    effective = dict(_ENV_AI_DEFAULTS)
    effective.update(overrides)
    return effective


async def save_ai_settings(db: AsyncSession, updates: dict[str, str | None]) -> None:
    """Persist AI settings. An empty value removes the DB override."""
    for key, value in updates.items():
        if key not in AI_SETTING_KEYS:
            continue
        cleaned = (value or "").strip() if isinstance(value, str) else (value or "")
        row = await db.get(PlatformSetting, key)
        if not cleaned:
            if row is not None:
                await db.delete(row)
            continue
        if row is None:
            db.add(PlatformSetting(key=key, value=cleaned))
        elif row.value != cleaned:
            row.value = cleaned
    await db.commit()


def resolve_provider(settings_map: dict[str, str | None]) -> tuple[Provider | None, str]:
    """Return the configured provider and the model that will be used."""
    code = (settings_map.get("ai_provider") or "").strip().lower()
    provider = _PROVIDER_BY_CODE.get(code)
    model = (settings_map.get("ai_model") or "").strip() or (provider.default_model if provider else "")
    return provider, model


def _system_prompt() -> str:
    return (
        "You are an email copywriter for Chmaba, a cloud point-of-sale platform for "
        "retail shops in Cambodia. You write short, warm, plain-spoken onboarding emails "
        "that help merchants finish setting up and start selling.\n\n"
        "Rules:\n"
        "- Keep it under 160 words.\n"
        "- Simple HTML only: <p>, <strong>, <a>, <ul>/<li>. No <html>, <head>, <style> or images.\n"
        "- One clear call to action linking to the Chmaba workspace.\n"
        "- No invented prices, features or deadlines.\n"
        "- Never claim the recipient did something they may not have done.\n\n"
        'Reply with strict JSON only: {"subject": "...", "body_html": "..."}'
    )


def _build_user_prompt(*, instruction: str, audience_note: str | None, tone: str | None) -> str:
    lines = [f"Write an email for this audience: {audience_note or 'merchants who signed up but have not started selling'}."]
    lines.append(f"Goal / instructions: {instruction.strip()}")
    if tone:
        lines.append(f"Tone: {tone.strip()}")
    return "\n".join(lines)


def _parse_draft(raw: str) -> dict[str, str]:
    """Best-effort extraction of {subject, body_html} from a model reply."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(text[start : end + 1])
            subject = str(payload.get("subject") or "").strip()
            body_html = str(payload.get("body_html") or payload.get("body") or "").strip()
            if subject and body_html:
                return {"subject": subject[:300], "body_html": body_html}
        except (ValueError, TypeError):
            pass
    # Fallback: treat the whole reply as the body with a generic subject.
    return {"subject": "Continue setting up your Chmaba store", "body_html": f"<p>{text}</p>" if text else ""}


async def _call_provider(provider: Provider, model: str, api_key: str, base_url: str, prompt: str) -> str:
    url = f"{base_url.rstrip('/')}" + ("/messages" if provider.dialect == "anthropic" else "/chat/completions")
    if provider.dialect == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": model, "max_tokens": 1200, "system": _system_prompt(), "messages": [{"role": "user", "content": prompt}]}
    else:
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        payload = {
            "model": model,
            "temperature": 0.7,
            "messages": [{"role": "system", "content": _system_prompt()}, {"role": "user", "content": prompt}],
        }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach the AI provider: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text[:300]
        raise AIError(f"The AI provider rejected the request ({response.status_code}): {detail}")
    try:
        data = response.json()
    except ValueError as exc:
        raise AIError("The AI provider returned a non-JSON response") from exc
    if provider.dialect == "anthropic":
        blocks = data.get("content") or []
        return "".join(block.get("text", "") for block in blocks if isinstance(block, dict))
    choices = data.get("choices") or []
    if not choices:
        raise AIError("The AI provider returned no content")
    return (choices[0].get("message") or {}).get("content") or ""


async def draft_email(
    db: AsyncSession,
    *,
    instruction: str,
    audience_note: str | None = None,
    tone: str | None = None,
) -> dict[str, str]:
    """Draft a subject + HTML body from an operator instruction.

    Raises ``AIError`` when AI is not configured or the provider call fails;
    the caller decides how to surface that.
    """
    configured = await load_ai_settings(db)
    provider, model = resolve_provider(configured)
    api_key = (configured.get("ai_api_key") or "").strip()
    if provider is None:
        raise AIError("No AI provider is configured yet. Add one in Mailing settings.")
    if not api_key:
        raise AIError("No AI API key is configured yet. Add one in Mailing settings.")
    base_url = (configured.get("ai_base_url") or "").strip() or provider.base_url
    prompt = _build_user_prompt(instruction=instruction, audience_note=audience_note, tone=tone)
    raw = await _call_provider(provider, model, api_key, base_url, prompt)
    draft = _parse_draft(raw)
    draft["provider"] = provider.code
    draft["model"] = model
    return draft

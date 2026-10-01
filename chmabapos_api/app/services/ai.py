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
from collections.abc import AsyncIterator
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
    """The AI provider was reachable-but-failed, or could not be reached."""


class AINotConfiguredError(AIError):
    """No provider or API key is stored yet. A user-fixable setup problem."""


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


async def _post_chat(
    provider: Provider,
    model: str,
    api_key: str,
    base_url: str,
    system: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1200,
) -> str:
    """POST a system + messages conversation to the configured provider.

    Shared by email drafting and the support assistant so the provider dialect,
    timeout and error handling live in exactly one place.
    """
    url = f"{base_url.rstrip('/')}" + ("/messages" if provider.dialect == "anthropic" else "/chat/completions")
    if provider.dialect == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    else:
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
    try:
        # Kept below the reverse proxy's read timeout so a slow provider yields
        # our JSON error rather than an opaque nginx 502.
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise AIError(f"The AI provider timed out after 45s: {exc}") from exc
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


async def _call_provider(provider: Provider, model: str, api_key: str, base_url: str, prompt: str) -> str:
    # Email drafting uses the mailing system prompt and a single user turn.
    return await _post_chat(provider, model, api_key, base_url, _system_prompt(), [{"role": "user", "content": prompt}])


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
        raise AINotConfiguredError("No AI provider is configured yet. Choose one in Settings, under AI writing.")
    if not api_key:
        raise AINotConfiguredError("No AI API key is stored. Add one in Settings, under AI writing.")
    base_url = (configured.get("ai_base_url") or "").strip() or provider.base_url
    prompt = _build_user_prompt(instruction=instruction, audience_note=audience_note, tone=tone)
    raw = await _call_provider(provider, model, api_key, base_url, prompt)
    draft = _parse_draft(raw)
    draft["provider"] = provider.code
    draft["model"] = model
    return draft


async def complete_chat(
    db: AsyncSession,
    *,
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 900,
) -> dict[str, str]:
    """Run a multi-turn chat against the configured provider.

    ``messages`` is a list of ``{"role": "user"|"assistant", "content": ...}``.
    Raises ``AINotConfiguredError`` when AI is not set up, or ``AIError`` when
    the provider call fails; the caller decides how to surface that.
    """
    configured = await load_ai_settings(db)
    provider, model = resolve_provider(configured)
    api_key = (configured.get("ai_api_key") or "").strip()
    if provider is None:
        raise AINotConfiguredError("No AI provider is configured yet. Choose one in Settings, under AI writing.")
    if not api_key:
        raise AINotConfiguredError("No AI API key is stored. Add one in Settings, under AI writing.")
    base_url = (configured.get("ai_base_url") or "").strip() or provider.base_url
    content = await _post_chat(
        provider,
        model,
        api_key,
        base_url,
        system,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return {"content": content, "provider": provider.code, "model": model}


async def require_chat_config(db: AsyncSession) -> None:
    """Raise ``AINotConfiguredError`` when the provider/key is missing.

    Endpoints that stream call this before sending response headers, so a
    setup problem becomes a normal 400 instead of a truncated stream.
    """
    configured = await load_ai_settings(db)
    provider, _ = resolve_provider(configured)
    if provider is None:
        raise AINotConfiguredError("No AI provider is configured yet. Choose one in Settings, under AI writing.")
    if not (configured.get("ai_api_key") or "").strip():
        raise AINotConfiguredError("No AI API key is stored. Add one in Settings, under AI writing.")


def _extract_delta(provider: Provider, parsed: dict) -> str:
    """Pull the incremental text out of one streamed provider chunk."""
    if provider.dialect == "anthropic":
        if parsed.get("type") == "content_block_delta":
            return (parsed.get("delta") or {}).get("text") or ""
        return ""
    choices = parsed.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("delta") or {}).get("content") or ""


async def stream_chat(
    db: AsyncSession,
    *,
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 900,
) -> AsyncIterator[str]:
    """Yield text deltas from the configured provider.

    Handles both the OpenAI/DeepSeek and Anthropic streaming formats. Raises
    ``AINotConfiguredError`` before the first yield when unconfigured; a provider
    failure mid-stream raises ``AIError`` after some text may already be yielded.
    """
    configured = await load_ai_settings(db)
    provider, model = resolve_provider(configured)
    api_key = (configured.get("ai_api_key") or "").strip()
    if provider is None:
        raise AINotConfiguredError("No AI provider is configured yet. Choose one in Settings, under AI writing.")
    if not api_key:
        raise AINotConfiguredError("No AI API key is stored. Add one in Settings, under AI writing.")
    base_url = (configured.get("ai_base_url") or "").strip() or provider.base_url
    url = f"{base_url.rstrip('/')}" + ("/messages" if provider.dialect == "anthropic" else "/chat/completions")
    if provider.dialect == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages, "stream": True}
    else:
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
        }
    try:
        # A stream resets the read timeout per chunk, so a longer overall budget
        # is safe here than for the one-shot request.
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise AIError(f"The AI provider rejected the request ({response.status_code}): {body[:300].decode(errors='ignore')}")
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    if not data:
                        continue
                    try:
                        parsed = json.loads(data)
                    except ValueError:
                        continue
                    text = _extract_delta(provider, parsed)
                    if text:
                        yield text
    except httpx.TimeoutException as exc:
        raise AIError(f"The AI provider timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach the AI provider: {exc}") from exc


async def test_ai(db: AsyncSession) -> dict[str, str]:
    """Validate the stored provider/key with a tiny request.

    Raises ``AINotConfiguredError`` when nothing is configured, or ``AIError``
    when the provider call fails.
    """
    draft = await draft_email(db, instruction="Reply with one short, friendly sentence.")
    return {"provider": draft.get("provider", ""), "model": draft.get("model", "")}

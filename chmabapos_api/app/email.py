from __future__ import annotations

from app.config import settings
from app.services.mail import deliver_message_with_id


async def send_email_with_id(
    recipient: str,
    subject: str,
    body: str,
    *,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    reply_to: str | None = None,
) -> tuple[bool, str | None]:
    """Send one message via the configured provider, returning ``(ok, message_id)``."""
    return await deliver_message_with_id(recipient=recipient, subject=subject, text=body, html=html, headers=headers, reply_to=reply_to)


async def send_email(
    recipient: str,
    subject: str,
    body: str,
    *,
    html: str | None = None,
    headers: dict[str, str] | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send one message via the configured provider (SMTP or Resend)."""
    ok, _ = await send_email_with_id(recipient, subject, body, html=html, headers=headers, reply_to=reply_to)
    return ok


async def send_verification_email(recipient: str, code: str) -> bool:
    body = (
        f"Your Chmaba confirmation code is: {code}\n\n"
        "Enter this 6-digit code on the sign-up screen to confirm your account.\n\n"
        "This code expires in 24 hours. If you did not create a Chmaba account, you can ignore this email."
    )
    return await send_email(recipient, "Your Chmaba confirmation code", body)


async def send_password_reset_email(recipient: str, token: str) -> bool:
    url = f"{settings.frontend_url}/reset-password?token={token}"
    body = f"Reset your Chmaba password by opening this link:\n\n{url}\n\nThis link expires in 30 minutes. If you did not request this, ignore this email."
    return await send_email(recipient, "Reset your Chmaba password", body)


async def send_invitation_email(recipient: str, token: str, company_name: str) -> bool:
    url = f"{settings.frontend_url}/accept-invitation?token={token}"
    body = f"You were invited to join {company_name} on Chmaba.\n\nAccept invitation:\n{url}\n\nThis invitation expires in 7 days."
    return await send_email(recipient, f"You were invited to {company_name} on Chmaba", body)


def unsubscribe_url(token: str) -> str:
    """Absolute one-click unsubscribe link served by this API."""
    base = (settings.api_public_url or settings.frontend_url).rstrip("/")
    return f"{base}/api/v1/email/unsubscribe?token={token}"


def html_to_text(html: str) -> str:
    """Crude but dependency-free plain-text fallback for an HTML body.

    Mail clients that prefer text/plain should still get a readable message,
    not raw markup.
    """
    import re

    text = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"(?s)<[^>]+>", "", text)
    replacements = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}
    for entity, char in replacements.items():
        text = text.replace(entity, char)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def send_marketing_email_with_id(
    recipient: str,
    subject: str,
    html: str,
    *,
    unsubscribe_token: str | None = None,
    reply_to: str | None = None,
) -> tuple[bool, str | None]:
    """Send an HTML mailing with a one-click ``List-Unsubscribe`` header.

    Returns ``(ok, message_id)`` so the caller can persist the provider id and
    later reconcile delivery/open webhook events against this exact message.
    """
    headers: dict[str, str] = {}
    if unsubscribe_token:
        url = unsubscribe_url(unsubscribe_token)
        headers["List-Unsubscribe"] = f"<{url}>"
        headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    return await send_email_with_id(recipient, subject, html_to_text(html), html=html, headers=headers, reply_to=reply_to)


async def send_marketing_email(
    recipient: str,
    subject: str,
    html: str,
    *,
    unsubscribe_token: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send an HTML mailing with a one-click ``List-Unsubscribe`` header."""
    ok, _ = await send_marketing_email_with_id(recipient, subject, html, unsubscribe_token=unsubscribe_token, reply_to=reply_to)
    return ok

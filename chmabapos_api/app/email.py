from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from app.config import settings
from app.services.email_layout import code_block, data_table, transactional_email
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
        '<p style="margin:0 0 4px 0;">Enter this 6-digit code on the sign-up screen to confirm your Chmaba account:</p>'
        + code_block(code)
        + '<p style="margin:18px 0 0 0;">This code expires in 24 hours. '
        "If you did not create a Chmaba account, you can ignore this email.</p>"
    )
    html = transactional_email(
        heading="Confirm your email",
        preview=f"Your Chmaba confirmation code is {code}.",
        body=body,
        badge="Verify",
    )
    return await send_email(recipient, "Your Chmaba confirmation code", html_to_text(html), html=html)


async def send_password_reset_email(recipient: str, token: str) -> bool:
    url = f"{settings.frontend_url}/reset-password?token={token}"
    body = (
        '<p style="margin:0 0 4px 0;">We received a request to reset your Chmaba password. '
        "Choose a new one with the button below.</p>"
        '<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br />'
        f'<a href="{url}" style="color:#6957f5;">{url}</a></p>'
    )
    html = transactional_email(
        heading="Reset your Chmaba password",
        preview="Reset your Chmaba password. This link expires in 30 minutes.",
        body=body,
        badge="Security",
        cta_label="Reset password",
        cta_href=url,
        footnote="This link expires in 30 minutes. If you did not request this, you can ignore this email.",
    )
    return await send_email(recipient, "Reset your Chmaba password", html_to_text(html), html=html)


async def send_invitation_email(recipient: str, token: str, company_name: str) -> bool:
    url = f"{settings.frontend_url}/accept-invitation?token={token}"
    body = (
        f'<p style="margin:0 0 4px 0;">You were invited to join <strong>{escape(company_name)}</strong> on Chmaba.</p>'
        '<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br />'
        f'<a href="{url}" style="color:#6957f5;">{url}</a></p>'
    )
    html = transactional_email(
        heading="You are invited to Chmaba",
        preview=f"Join {escape(company_name)} on Chmaba.",
        body=body,
        badge="Invitation",
        cta_label="Accept invitation",
        cta_href=url,
        footnote="This invitation expires in 7 days. If you were not expecting it, you can ignore this email.",
    )
    return await send_email(recipient, f"You were invited to {company_name} on Chmaba", html_to_text(html), html=html)


def _first_name(full_name: str | None) -> str:
    cleaned = (full_name or "").strip()
    return cleaned.split()[0] if cleaned else "there"


async def send_password_changed_email(recipient: str, full_name: str | None = None) -> bool:
    """Best-effort confirmation after a password reset or change.

    Security notices are account mail, so they are sent inline rather than via
    the store outbox; a mail failure must not fail the password change itself.
    """
    when = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    body = (
        f'<p style="margin:0 0 4px 0;">Hi {escape(_first_name(full_name))}, your Chmaba password was just changed.</p>'
        + data_table(["", ""], [["Changed", escape(when)]], aligns=["left", "right"], show_header=False)
        + '<p style="margin:18px 0 0 0;">If this was you, no action is needed. If you did not change it, '
        "reset your password and contact support right away.</p>"
    )
    html = transactional_email(
        heading="Your password was changed",
        preview="Your Chmaba password was just changed.",
        body=body,
        badge="Security",
    )
    return await send_email(recipient, "Your Chmaba password was changed", html_to_text(html), html=html)


async def send_new_signin_email(
    recipient: str,
    full_name: str | None = None,
    *,
    device: str | None = None,
    ip: str | None = None,
) -> bool:
    """Best-effort notice that the account was signed in to from a new device."""
    when = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    facts = [["When", escape(when)]]
    if device:
        facts.append(["Device", escape(device)])
    if ip:
        facts.append(["IP address", escape(ip)])
    body = (
        f'<p style="margin:0 0 4px 0;">Hi {escape(_first_name(full_name))}, your Chmaba account was just signed in to '
        f"from a new device.</p>"
        + data_table(["", ""], facts, aligns=["left", "right"], show_header=False)
        + '<p style="margin:18px 0 0 0;">If this was you, no action is needed. If it was not, change your password '
        "and contact support right away.</p>"
    )
    html = transactional_email(
        heading="New sign-in to your account",
        preview="A new device signed in to your Chmaba account.",
        body=body,
        badge="Security",
    )
    return await send_email(recipient, "New sign-in to your Chmaba account", html_to_text(html), html=html)


def username_for(email: str | None, full_name: str | None) -> str:
    """The SPA's username segment for this account (mirrors ``routing.js``)."""
    import re

    email_name = (email or "").split("@", 1)[0]
    source = email_name or (full_name or "") or "user"
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    return slug or "user"


def _app_url(username: str, path: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/{username}/{path}"


async def send_welcome_email(recipient: str, full_name: str | None, username: str) -> bool:
    """Sent once when an account is confirmed, pointing the merchant at setup."""
    url = _app_url(username, "setup/company")
    body = (
        f'<p style="margin:0 0 4px 0;">Welcome to Chmaba, {escape(_first_name(full_name))}! '
        "Your account is confirmed. Set up your store in about two minutes and start selling.</p>"
        '<p style="margin:14px 0 0 0;">Once it&rsquo;s ready you can add your first product and take a sale '
        "&mdash; cash or KHQR.</p>"
        '<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br />'
        f'<a href="{url}" style="color:#6957f5;">{url}</a></p>'
    )
    html = transactional_email(
        heading="Welcome to Chmaba",
        preview="Your Chmaba account is confirmed. Set up your store to start selling.",
        body=body,
        badge="Get started",
        cta_label="Set up your store",
        cta_href=url,
        footnote="If the link asks you to sign in first, sign in and you will be taken straight to setup.",
    )
    return await send_email(recipient, "Welcome to Chmaba", html_to_text(html), html=html)


async def send_store_ready_email(recipient: str, full_name: str | None, username: str, store_name: str) -> bool:
    """Sent once when a workspace is created, pointing at the first product."""
    url = _app_url(username, "catalog")
    body = (
        f'<p style="margin:0 0 4px 0;">Hi {escape(_first_name(full_name))}, your store '
        f"<strong>{escape(store_name)}</strong> is ready on Chmaba.</p>"
        '<p style="margin:14px 0 0 0;">The next step is your first product: add a name and a price and you can '
        "ring up a sale right away. We also added a few sample items so you can try the register immediately "
        "&mdash; replace them with your own catalogue when you are ready.</p>"
        '<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br />'
        f'<a href="{url}" style="color:#6957f5;">{url}</a></p>'
    )
    html = transactional_email(
        heading="Your Chmaba store is ready",
        preview=f"{escape(store_name)} is ready. Add your first product to start selling.",
        body=body,
        badge="Your store",
        cta_label="Add your first product",
        cta_href=url,
        footnote="Tip: replace the sample items with your own catalogue when you are ready.",
    )
    return await send_email(recipient, "Your Chmaba store is ready", html_to_text(html), html=html)


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

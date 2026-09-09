from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.policy import SMTP

from app.config import settings


def _send_email(recipient: str, subject: str, body: str) -> None:
    # Keep reset and verification URLs intact in plain-text MailHog messages.
    message = EmailMessage(policy=SMTP.clone(max_line_length=998))
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


async def send_email(recipient: str, subject: str, body: str) -> bool:
    try:
        await asyncio.to_thread(_send_email, recipient, subject, body)
        return True
    except (OSError, smtplib.SMTPException):
        return False


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

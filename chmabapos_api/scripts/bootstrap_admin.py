from __future__ import annotations

import asyncio
import secrets
import sys

from sqlalchemy import select

sys.path.insert(0, "chmabapos_api")

from app.db import SessionLocal
from app.email import send_email
from app.models import User
from app.security import hash_password


ADMIN_EMAIL = "duke@chmaba.com"


async def bootstrap() -> None:
    temporary_password = None
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == ADMIN_EMAIL))
        user = result.scalar_one_or_none()
        if user:
            user.platform_role = "super_admin"
            user.is_active = True
            user.is_email_verified = True
            action = "promoted"
        else:
            temporary_password = secrets.token_urlsafe(18)
            user = User(email=ADMIN_EMAIL, full_name="Duke", password_hash=hash_password(temporary_password), is_active=True, is_email_verified=True, platform_role="super_admin")
            db.add(user)
            action = "created"
        await db.commit()
    if temporary_password:
        sent = await send_email(
            ADMIN_EMAIL,
            "Your Chmaba platform admin account",
            f"Your Chmaba platform admin account was created.\n\nEmail: {ADMIN_EMAIL}\nTemporary password: {temporary_password}\n\nChange this password after first sign in.\n\nAdmin panel: http://localhost:5173/admin",
        )
        print(f"Duke account {action}; temporary credentials sent to MailHog: {sent}")
        print(f"MailHog: http://localhost:8025")
    else:
        print(f"Duke account {action} as super_admin; existing password preserved")


if __name__ == "__main__":
    asyncio.run(bootstrap())

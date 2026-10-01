from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.services import help_repo

ARTICLE_ID = "test.admin-created"


@pytest.mark.asyncio
async def test_admin_help_article_crud_reaches_read_path() -> None:
    email = f"help-admin-{uuid.uuid4().hex[:10]}@example.com"
    create_payload = {
        "id": ARTICLE_ID,
        "section_id": "test",
        "section_title": "Testing",
        "section_blurb": "Admin-created guides.",
        "title": "Admin created guide",
        "steps": ["Do the first thing.", "Do the second thing."],
        "verticals": ["general"],
        "roles": ["owner"],
        "position": 1,
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": "Help Admin", "password": "strong-password"})
            await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            async with SessionLocal() as db:
                await db.execute(text("UPDATE users SET platform_role = 'admin' WHERE email = :email"), {"email": email})
                await db.commit()

            # Seeded content is listed for editing.
            listing = await client.get("/api/v1/admin/help/articles", headers=headers)
            assert listing.status_code == 200
            assert any(row["id"] == "inventory.restock" for row in listing.json())

            created = await client.post("/api/v1/admin/help/articles", headers=headers, json=create_payload)
            assert created.status_code == 201
            assert created.json()["title"] == "Admin created guide"

            # The write is immediately visible on the read path (no cache).
            async with SessionLocal() as db:
                sections = await help_repo.load_sections(db)
            assert any(article["id"] == ARTICLE_ID for section in sections for article in section["articles"])

            # Duplicate id is rejected.
            duplicate = await client.post("/api/v1/admin/help/articles", headers=headers, json=create_payload)
            assert duplicate.status_code == 409

            updated = await client.patch(f"/api/v1/admin/help/articles/{ARTICLE_ID}", headers=headers, json={"title": "Renamed guide"})
            assert updated.status_code == 200
            assert updated.json()["title"] == "Renamed guide"

            # Unknown vertical is rejected.
            bad = await client.patch(f"/api/v1/admin/help/articles/{ARTICLE_ID}", headers=headers, json={"verticals": ["spaceship"]})
            assert bad.status_code == 422

            deleted = await client.delete(f"/api/v1/admin/help/articles/{ARTICLE_ID}", headers=headers)
            assert deleted.status_code == 204
            async with SessionLocal() as db:
                sections = await help_repo.load_sections(db)
            assert not any(article["id"] == ARTICLE_ID for section in sections for article in section["articles"])
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM help_articles WHERE id = :id"), {"id": ARTICLE_ID})
            await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
            await db.commit()

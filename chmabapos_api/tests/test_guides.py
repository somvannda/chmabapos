from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app

CATEGORY_SLUG = "test-guides"
GUIDE_SLUG = "test-guide"


async def _platform_admin(client: AsyncClient) -> dict[str, str]:
    email = f"guides-admin-{uuid.uuid4().hex[:10]}@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Guides Admin", "password": "strong-password"},
    )
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    async with SessionLocal() as db:
        await db.execute(
            text("UPDATE users SET platform_role = 'admin' WHERE email = :email"),
            {"email": email},
        )
        await db.commit()
    return {"Authorization": f"Bearer {login.json()['access_token']}", "X-Test-Email": email}


def _guide_payload(category_id: str, **overrides: object) -> dict[str, object]:
    return {
        "category_id": category_id,
        "slug": GUIDE_SLUG,
        "title": "Test coffee guide",
        "summary": "A guide created by the test suite.",
        "group_title": "Start here",
        "level": "beginner",
        "estimated_minutes": 5,
        "intro": "Intro paragraph.",
        "learning_points": ["Learn one thing"],
        "requirements": ["A test account"],
        "sections": [
            {
                "heading": "First section",
                "body": ["A paragraph of body copy."],
                "steps": ["Do the first thing.", "Do the second thing."],
                "tip": "A helpful tip.",
            }
        ],
        "takeaways": ["One takeaway"],
        "status": "draft",
        "position": 99,
        **overrides,
    }


@pytest.mark.asyncio
async def test_public_guide_library_is_seeded_and_drafts_stay_hidden() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _platform_admin(client)
        email = headers.pop("X-Test-Email")

        try:
            index = await client.get("/api/v1/public/guides")
            assert index.status_code == 200
            payload = index.json()
            coffee = next(category for category in payload["categories"] if category["slug"] == "coffee-shop")
            assert coffee["guide_count"] >= 10
            restaurant = next(category for category in payload["categories"] if category["slug"] == "restaurant")
            assert restaurant["guide_count"] >= 8
            assert any(guide["slug"] == "ring-up-your-first-sale" for guide in payload["guides"])
            assert any(guide["slug"] == "take-a-dine-in-order" for guide in payload["guides"])
            assert payload["featured"]

            restaurant_page = await client.get("/api/v1/public/guides/restaurant")
            assert restaurant_page.status_code == 200
            assert restaurant_page.json()["total"] >= 8
            restaurant_detail = await client.get("/api/v1/public/guides/restaurant/take-a-dine-in-order")
            assert restaurant_detail.status_code == 200
            assert restaurant_detail.json()["step_count"] == 4
            assert len(restaurant_detail.json()["series"]) >= 8

            mart_page = await client.get("/api/v1/public/guides/mart")
            assert mart_page.status_code == 200
            assert mart_page.json()["total"] >= 5
            mart_detail = await client.get("/api/v1/public/guides/mart/sell-and-reconcile-your-mart")
            assert mart_detail.status_code == 200
            assert len(mart_detail.json()["series"]) >= 5

            electronics_page = await client.get("/api/v1/public/guides/electronics")
            assert electronics_page.status_code == 200
            assert electronics_page.json()["total"] >= 4
            electronics_detail = await client.get("/api/v1/public/guides/electronics/sell-service-and-trade-in")
            assert electronics_detail.status_code == 200
            assert len(electronics_detail.json()["series"]) >= 4

            category = (
                await client.post(
                    "/api/v1/admin/guide-categories",
                    headers=headers,
                    json={
                        "slug": CATEGORY_SLUG,
                        "name": "Test guides",
                        "description": "Test-only category",
                        "position": 99,
                    },
                )
            )
            assert category.status_code == 201, category.text
            category_id = category.json()["id"]

            draft = await client.post("/api/v1/admin/guides", headers=headers, json=_guide_payload(category_id))
            assert draft.status_code == 201, draft.text
            assert draft.json()["status"] == "draft"
            assert draft.json()["published_at"] is None

            # The test category exists but a draft is not published, so it must
            # not appear in the public index or the category page.
            public_index = (await client.get("/api/v1/public/guides")).json()
            assert all(guide["category_slug"] != CATEGORY_SLUG for guide in public_index["guides"])
            assert (await client.get(f"/api/v1/public/guides/{CATEGORY_SLUG}")).status_code == 404

            published = await client.patch(
                f"/api/v1/admin/guides/{draft.json()['id']}",
                headers=headers,
                json={"status": "published"},
            )
            assert published.status_code == 200, published.text
            assert published.json()["published_at"] is not None

            public_category = await client.get(f"/api/v1/public/guides/{CATEGORY_SLUG}")
            assert public_category.status_code == 200
            assert public_category.json()["total"] == 1
            assert public_category.json()["groups"][0]["guides"][0]["slug"] == GUIDE_SLUG

            detail = await client.get(f"/api/v1/public/guides/{CATEGORY_SLUG}/{GUIDE_SLUG}")
            assert detail.status_code == 200
            assert detail.json()["sections"][0]["steps"] == ["Do the first thing.", "Do the second thing."]
            assert detail.json()["step_count"] == 1
            assert [row["slug"] for row in detail.json()["series"]] == [GUIDE_SLUG]
            assert detail.json()["previous"] is None
            assert detail.json()["next"] is None

            # Archived guides disappear from the public page while staying in
            # the admin list.
            archived = await client.patch(
                f"/api/v1/admin/guides/{draft.json()['id']}",
                headers=headers,
                json={"status": "archived"},
            )
            assert archived.status_code == 200
            assert (await client.get(f"/api/v1/public/guides/{CATEGORY_SLUG}/{GUIDE_SLUG}")).status_code == 404
            listing = await client.get("/api/v1/admin/guides", headers=headers, params={"status": "archived"})
            assert any(row["slug"] == GUIDE_SLUG for row in listing.json())
        finally:
            async with SessionLocal() as db:
                await db.execute(
                    text("DELETE FROM guide_categories WHERE slug = :slug"),
                    {"slug": CATEGORY_SLUG},
                )
                await db.execute(
                    text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email=:email)"),
                    {"email": email},
                )
                await db.execute(
                    text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"),
                    {"email": email},
                )
                await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
                await db.commit()


@pytest.mark.asyncio
async def test_guide_admin_validation_and_category_guard() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _platform_admin(client)
        email = headers.pop("X-Test-Email")
        try:
            category = await client.post(
                "/api/v1/admin/guide-categories",
                headers=headers,
                json={"slug": CATEGORY_SLUG, "name": "Test guides", "position": 99},
            )
            assert category.status_code == 201
            category_id = category.json()["id"]

            duplicate_category = await client.post(
                "/api/v1/admin/guide-categories",
                headers=headers,
                json={"slug": CATEGORY_SLUG, "name": "Another name"},
            )
            assert duplicate_category.status_code == 409

            created = await client.post("/api/v1/admin/guides", headers=headers, json=_guide_payload(category_id))
            assert created.status_code == 201

            duplicate_guide = await client.post("/api/v1/admin/guides", headers=headers, json=_guide_payload(category_id))
            assert duplicate_guide.status_code == 409

            # A non-empty category cannot be deleted; the guides must move first.
            blocked = await client.delete(f"/api/v1/admin/guide-categories/{category_id}", headers=headers)
            assert blocked.status_code == 409

            bad_slug = await client.patch(
                f"/api/v1/admin/guides/{created.json()['id']}",
                headers=headers,
                json={"slug": "!!!"},
            )
            # An unusable slug falls back to a safe value rather than 500ing.
            assert bad_slug.status_code == 200
            assert bad_slug.json()["slug"] == "guide"

            invalid_level = await client.patch(
                f"/api/v1/admin/guides/{created.json()['id']}",
                headers=headers,
                json={"level": "expert"},
            )
            assert invalid_level.status_code == 422

            empty_sections = await client.patch(
                f"/api/v1/admin/guides/{created.json()['id']}",
                headers=headers,
                json={"sections": []},
            )
            assert empty_sections.status_code == 422

            removed = await client.delete(f"/api/v1/admin/guides/{created.json()['id']}", headers=headers)
            assert removed.status_code == 204
            deleted_category = await client.delete(f"/api/v1/admin/guide-categories/{category_id}", headers=headers)
            assert deleted_category.status_code == 204
        finally:
            async with SessionLocal() as db:
                await db.execute(
                    text("DELETE FROM guide_categories WHERE slug = :slug"),
                    {"slug": CATEGORY_SLUG},
                )
                await db.execute(
                    text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email=:email)"),
                    {"email": email},
                )
                await db.execute(
                    text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email=:email)"),
                    {"email": email},
                )
                await db.execute(text("DELETE FROM users WHERE email=:email"), {"email": email})
                await db.commit()

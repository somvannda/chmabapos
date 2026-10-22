"""Platform contacts: CRUD, categories and CSV import."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, EmailSuppression


async def register_verified(client: AsyncClient, email: str) -> None:
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Contacts Tester", "password": "strong-password"},
    )
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})


async def promote(email: str, role: str = "admin") -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = :role WHERE email = :email"), {"role": role, "email": email})
        await db.commit()


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def cleanup(emails: list[str], category_names: list[str]) -> None:
    async with SessionLocal() as db:
        if emails:
            await db.execute(text("DELETE FROM contacts WHERE email = ANY(:emails)"), {"emails": emails})
        if category_names:
            await db.execute(text("DELETE FROM contact_categories WHERE name = ANY(:names)"), {"names": category_names})
        await db.execute(
            text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"),
            {"emails": emails},
        )
        await db.execute(
            text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = ANY(:emails))"),
            {"emails": emails},
        )
        await db.execute(text("DELETE FROM users WHERE email = ANY(:emails)"), {"emails": emails})
        await db.commit()


@pytest.mark.asyncio
async def test_contacts_require_platform_admin() -> None:
    email = f"contacts-user-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, email)
            headers = await login_headers(client, email)
            denied = await client.get("/api/v1/admin/contacts", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup([email], [])


@pytest.mark.asyncio
async def test_contact_and_category_crud() -> None:
    admin = f"contacts-admin-{uuid.uuid4().hex[:8]}@example.com"
    contact_email = f"lead-{uuid.uuid4().hex[:8]}@example.com"
    category_name = f"Imported Lead {uuid.uuid4().hex[:6]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin)
            await promote(admin)
            headers = await login_headers(client, admin)

            category = await client.post(
                "/api/v1/admin/contact-categories",
                headers=headers,
                json={"name": category_name, "color": "blue", "description": "From a spreadsheet"},
            )
            assert category.status_code == 201
            category_id = category.json()["id"]
            assert category.json()["contact_count"] == 0

            duplicate_category = await client.post(
                "/api/v1/admin/contact-categories",
                headers=headers,
                json={"name": category_name.lower()},
            )
            assert duplicate_category.status_code == 409

            created = await client.post(
                "/api/v1/admin/contacts",
                headers=headers,
                json={
                    "email": contact_email,
                    "name": "Sokha Chan",
                    "phone": "+855 12 345 678",
                    "company": "Sokha Retail",
                    "category_id": category_id,
                    "source": "manual",
                    "notes": "Met at the market",
                },
            )
            assert created.status_code == 201
            contact = created.json()
            assert contact["category_name"] == category_name
            assert contact["category_color"] == "blue"

            duplicate = await client.post(
                "/api/v1/admin/contacts",
                headers=headers,
                json={"email": contact_email.upper(), "name": "Someone else"},
            )
            assert duplicate.status_code == 409

            listed = await client.get("/api/v1/admin/contacts", headers=headers, params={"search": contact_email})
            assert listed.status_code == 200
            assert listed.json()["total"] == 1
            assert listed.json()["items"][0]["id"] == contact["id"]

            filtered = await client.get("/api/v1/admin/contacts", headers=headers, params={"category_id": category_id})
            assert filtered.json()["total"] == 1

            updated = await client.patch(
                f"/api/v1/admin/contacts/{contact['id']}",
                headers=headers,
                json={"name": "Sokha C.", "notes": "", "category_id": None},
            )
            assert updated.status_code == 200
            assert updated.json()["name"] == "Sokha C."
            assert updated.json()["notes"] is None
            assert updated.json()["category_id"] is None

            uncategorized = await client.get("/api/v1/admin/contacts", headers=headers, params={"uncategorized": "true"})
            assert any(item["id"] == contact["id"] for item in uncategorized.json()["items"])

            summary = await client.get("/api/v1/admin/contacts/summary", headers=headers)
            assert summary.status_code == 200
            by_name = {row["name"]: row for row in summary.json()["categories"]}
            assert by_name[category_name]["contact_count"] == 0
            assert summary.json()["uncategorized"] >= 1

            # Deleting a category keeps its contacts, they just lose the grouping.
            await client.patch(
                f"/api/v1/admin/contacts/{contact['id']}",
                headers=headers,
                json={"category_id": category_id},
            )
            deleted_category = await client.delete(f"/api/v1/admin/contact-categories/{category_id}", headers=headers)
            assert deleted_category.status_code == 204
            moved = await client.get("/api/v1/admin/contacts", headers=headers, params={"uncategorized": "true"})
            assert any(item["id"] == contact["id"] for item in moved.json()["items"])

            deleted = await client.delete(f"/api/v1/admin/contacts/{contact['id']}", headers=headers)
            assert deleted.status_code == 204
            assert (await client.get("/api/v1/admin/contacts", headers=headers, params={"search": contact_email})).json()["total"] == 0
    finally:
        await cleanup([admin, contact_email], [category_name])


@pytest.mark.asyncio
async def test_contact_csv_import_creates_updates_and_reports_bad_rows() -> None:
    admin = f"contacts-admin-{uuid.uuid4().hex[:8]}@example.com"
    existing_email = f"known-{uuid.uuid4().hex[:8]}@example.com"
    new_email = f"imported-{uuid.uuid4().hex[:8]}@example.com"
    other_email = f"imported2-{uuid.uuid4().hex[:8]}@example.com"
    category_name = f"CSV Lead {uuid.uuid4().hex[:6]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin)
            await promote(admin)
            headers = await login_headers(client, admin)

            created = await client.post(
                "/api/v1/admin/contacts",
                headers=headers,
                json={"email": existing_email, "name": "Known Person", "company": "Known Co"},
            )
            assert created.status_code == 201

            csv_body = (
                "Email,Full Name,Phone,Company,Category,Notes\n"
                f"{existing_email},Known Person Updated,+855 10 000 000,Known Co 2,{category_name},Called today\n"
                f"{new_email},New Person,+855 11 111 111,New Co,{category_name},From the event\n"
                f"{other_email},Other Person,,Other Co,,\n"
                "not-an-email,Bad Row,,,,\n"
            ).encode()
            imported = await client.post(
                "/api/v1/admin/contacts/import",
                headers=headers,
                files={"file": ("contacts.csv", csv_body, "text/csv")},
                data={"update_existing": "true"},
            )
            assert imported.status_code == 200, imported.text
            result = imported.json()
            assert result["created"] == 2
            assert result["updated"] == 1
            assert result["invalid"] == 1
            assert result["categories_created"] == 1
            assert result["errors"]

            rows = await client.get("/api/v1/admin/contacts", headers=headers, params={"search": new_email})
            item = rows.json()["items"][0]
            assert item["name"] == "New Person"
            assert item["category_name"] == category_name

            # Updating an existing row must not blank fields the CSV omits.
            second_body = (
                "email,name,phone\n"
                f"{new_email},,+855 99 999 999\n"
            ).encode()
            second = await client.post(
                "/api/v1/admin/contacts/import",
                headers=headers,
                files={"file": ("contacts.csv", second_body, "text/csv")},
                data={"update_existing": "true"},
            )
            assert second.json()["updated"] == 1
            row = (await client.get("/api/v1/admin/contacts", headers=headers, params={"search": new_email})).json()["items"][0]
            assert row["name"] == "New Person"
            assert row["phone"] == "+855 99 999 999"

            skipped = await client.post(
                "/api/v1/admin/contacts/import",
                headers=headers,
                files={"file": ("contacts.csv", second_body, "text/csv")},
                data={"update_existing": "false"},
            )
            assert skipped.json()["skipped"] == 1

            missing_email = await client.post(
                "/api/v1/admin/contacts/import",
                headers=headers,
                files={"file": ("contacts.csv", b"name,phone\nA,123\n", "text/csv")},
            )
            assert missing_email.status_code == 422
    finally:
        await cleanup([admin, existing_email, new_email, other_email], [category_name])


@pytest.mark.asyncio
async def test_contact_list_shows_mailing_engagement_and_suppression() -> None:
    admin = f"contacts-admin-{uuid.uuid4().hex[:8]}@example.com"
    contact_email = f"engaged-{uuid.uuid4().hex[:8]}@example.com"
    now = datetime.now(timezone.utc)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin)
            await promote(admin)
            headers = await login_headers(client, admin)
            created = await client.post(
                "/api/v1/admin/contacts",
                headers=headers,
                json={"email": contact_email, "name": "Engaged Lead"},
            )
            assert created.status_code == 201

        async with SessionLocal() as db:
            db.add(
                EmailSend(
                    recipient_email=contact_email,
                    subject="First touch",
                    body_html="<p>Hi</p>",
                    status="sent",
                    source="manual",
                    created_at=now,
                )
            )
            db.add(
                EmailSend(
                    recipient_email=contact_email,
                    subject="Second touch",
                    body_html="<p>Hi</p>",
                    status="clicked",
                    source="manual",
                    created_at=now,
                    opened_at=now,
                    clicked_at=now,
                )
            )
            db.add(EmailSuppression(email=contact_email, reason="unsubscribed"))
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, admin)
            response = await client.get("/api/v1/admin/contacts", headers=headers, params={"search": contact_email})
            assert response.status_code == 200
            row = response.json()["items"][0]
            # Engagement is rolled up from the delivery log by address.
            assert row["sends"] == 2
            assert row["last_sent_at"] is not None
            assert row["last_opened_at"] is not None
            assert row["last_clicked_at"] is not None
            assert row["suppressed"] is True
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": contact_email})
            await db.execute(text("DELETE FROM email_suppressions WHERE email = :email"), {"email": contact_email})
            await db.commit()
        await cleanup([admin, contact_email], [])


@pytest.mark.asyncio
async def test_contact_detail_shows_send_history() -> None:
    admin = f"contacts-admin-{uuid.uuid4().hex[:8]}@example.com"
    contact_email = f"history-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin)
            await promote(admin)
            headers = await login_headers(client, admin)
            created = await client.post(
                "/api/v1/admin/contacts",
                headers=headers,
                json={"email": contact_email, "name": "History Lead"},
            )
            assert created.status_code == 201
            contact_id = created.json()["id"]

        async with SessionLocal() as db:
            db.add(
                EmailSend(
                    recipient_email=contact_email,
                    subject="A past send",
                    body_html="<p>Hi</p>",
                    status="opened",
                    source="manual",
                    opened_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, admin)
            detail = await client.get(f"/api/v1/admin/contacts/{contact_id}", headers=headers)
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body["email"] == contact_email
            assert len(body["sends"]) == 1
            assert body["sends"][0]["subject"] == "A past send"
            assert body["sends"][0]["campaign_name"] is None
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": contact_email})
            await db.commit()
        await cleanup([admin, contact_email], [])


@pytest.mark.asyncio
async def test_contact_bulk_actions_and_csv_export() -> None:
    admin = f"contacts-admin-{uuid.uuid4().hex[:8]}@example.com"
    emails = [f"bulk-{index}-{uuid.uuid4().hex[:8]}@example.com" for index in range(3)]
    name_a = f"Bulk A {uuid.uuid4().hex[:6]}"
    name_b = f"Bulk B {uuid.uuid4().hex[:6]}"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin)
            await promote(admin)
            headers = await login_headers(client, admin)

            category_a = await client.post("/api/v1/admin/contact-categories", headers=headers, json={"name": name_a})
            category_b = await client.post("/api/v1/admin/contact-categories", headers=headers, json={"name": name_b})
            assert category_a.status_code == 201 and category_b.status_code == 201
            category_a_id = category_a.json()["id"]
            category_b_id = category_b.json()["id"]

            contact_ids = []
            for email in emails:
                created = await client.post(
                    "/api/v1/admin/contacts",
                    headers=headers,
                    json={"email": email, "category_id": category_a_id},
                )
                assert created.status_code == 201, created.text
                contact_ids.append(created.json()["id"])

            moved = await client.post(
                "/api/v1/admin/contacts/bulk",
                headers=headers,
                json={"action": "category", "contact_ids": contact_ids, "category_id": category_b_id},
            )
            assert moved.status_code == 200, moved.text
            assert moved.json()["updated"] == 3
            listed = await client.get("/api/v1/admin/contacts", headers=headers, params={"category_id": category_b_id})
            assert listed.json()["total"] == 3

            unsubscribed = await client.post(
                "/api/v1/admin/contacts/bulk",
                headers=headers,
                json={"action": "unsubscribe", "contact_ids": contact_ids},
            )
            assert unsubscribed.status_code == 200, unsubscribed.text
            assert unsubscribed.json()["updated"] == 3
            first = (await client.get("/api/v1/admin/contacts", headers=headers, params={"search": emails[0]})).json()["items"][0]
            assert first["suppressed"] is True

            exported = await client.get("/api/v1/admin/contacts/export", headers=headers, params={"search": emails[0]})
            assert exported.status_code == 200
            assert "text/csv" in exported.headers["content-type"]
            assert emails[0] in exported.text
            assert "unsubscribed" in exported.text

            deleted = await client.post(
                "/api/v1/admin/contacts/bulk",
                headers=headers,
                json={"action": "delete", "contact_ids": contact_ids},
            )
            assert deleted.status_code == 200, deleted.text
            assert deleted.json()["updated"] == 3
            remaining = await client.get("/api/v1/admin/contacts", headers=headers, params={"search": emails[0]})
            assert remaining.json()["total"] == 0
    finally:
        async with SessionLocal() as db:
            await db.execute(text("DELETE FROM email_suppressions WHERE email = ANY(:emails)"), {"emails": emails})
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = ANY(:emails)"), {"emails": emails})
            await db.commit()
        await cleanup([admin, *emails], [name_a, name_b])

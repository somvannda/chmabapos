"""Admin Mailing: audience selection, manual sends, AI drafting, unsubscribe."""
from __future__ import annotations

import base64
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, EmailSuppression, EmailTemplate
from app.services.mailing import create_unsubscribe_token

AI_KEYS = ("ai_provider", "ai_api_key", "ai_model", "ai_base_url")


async def register_verified(client: AsyncClient, email: str, *, workspace: bool = False, full_name: str = "Mailing Tester") -> dict | None:
    register = await client.post("/api/v1/auth/register", json={"email": email, "full_name": full_name, "password": "strong-password"})
    assert register.status_code == 201
    await client.post("/api/v1/auth/verify-email", json={"token": register.json()["dev_verification_token"]})
    if not workspace:
        return None
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    setup = await client.post(
        "/api/v1/workspaces/setup",
        headers=headers,
        json={"company_name": "Mailing Store", "store_name": "Main Counter", "country": "Cambodia", "currency_code": "USD", "plan_code": "free"},
    )
    assert setup.status_code == 201
    return setup.json()


async def promote(email: str, role: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET platform_role = :role WHERE email = :email"), {"role": role, "email": email})
        await db.commit()


async def backdate(email: str, days: int) -> None:
    async with SessionLocal() as db:
        await db.execute(text("UPDATE users SET created_at = created_at - make_interval(days => :days) WHERE email = :email"), {"days": days, "email": email})
        await db.commit()


async def login_headers(client: AsyncClient, email: str) -> dict:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "strong-password"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def cleanup(emails: list[str]) -> None:
    async with SessionLocal() as db:
        for email in emails:
            company_ids = (
                await db.execute(
                    text("SELECT company_id FROM memberships WHERE user_id IN (SELECT id FROM users WHERE email = :email)"),
                    {"email": email},
                )
            ).scalars().all()
            for company_id in company_ids:
                parameters = {"company_id": company_id}
                for statement in [
                    "DELETE FROM notifications USING stores WHERE notifications.store_id = stores.id AND stores.company_id = :company_id",
                    "DELETE FROM membership_stores USING memberships WHERE membership_stores.membership_id = memberships.id AND memberships.company_id = :company_id",
                    "DELETE FROM memberships WHERE company_id = :company_id",
                    "DELETE FROM company_currencies WHERE company_id = :company_id",
                    "DELETE FROM stores WHERE company_id = :company_id",
                    "DELETE FROM companies WHERE id = :company_id",
                ]:
                    await db.execute(text(statement), parameters)
            await db.execute(text("DELETE FROM audit_logs WHERE actor_user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM email_sends WHERE recipient_email = :email"), {"email": email})
            await db.execute(text("DELETE FROM email_suppressions WHERE email = :email"), {"email": email})
            await db.execute(text("DELETE FROM email_verification_tokens WHERE user_id IN (SELECT id FROM users WHERE email = :email)"), {"email": email})
            await db.execute(text("DELETE FROM users WHERE email = :email"), {"email": email})
        await db.commit()


async def clear_ai_settings() -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM platform_settings WHERE key = ANY(:keys)"), {"keys": list(AI_KEYS)})
        await db.commit()


@pytest.mark.asyncio
async def test_mailing_requires_platform_admin() -> None:
    email = f"mailing-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, email, workspace=True)
            headers = await login_headers(client, email)
            denied = await client.get("/api/v1/admin/mailing/audience", headers=headers)
            assert denied.status_code == 403
    finally:
        await cleanup([email])


@pytest.mark.asyncio
async def test_audience_lists_stalled_signup_only_when_old_enough() -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    stalled = f"mailing-stalled-{uuid.uuid4().hex[:8]}@example.com"
    fresh = f"mailing-fresh-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await register_verified(client, stalled, workspace=False)
            await register_verified(client, fresh, workspace=False)
        await promote(admin, "admin")
        await backdate(stalled, 10)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, admin)
            response = await client.get("/api/v1/admin/mailing/audience?audience=no_workspace&min_age_hours=24", headers=headers)
            assert response.status_code == 200
            body = response.json()
            emails = [row["email"] for row in body["recipients"]]
            assert stalled in emails
            assert fresh not in emails
            assert admin not in emails
            codes = {segment["code"] for segment in body["segments"]}
            assert {"no_workspace", "unverified", "no_sales", "all"} <= codes
    finally:
        await cleanup([admin, stalled, fresh])


@pytest.mark.asyncio
async def test_send_requires_super_admin_and_records_delivery(monkeypatch) -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    stalled = f"mailing-stalled-{uuid.uuid4().hex[:8]}@example.com"
    suppressed = f"mailing-optedout-{uuid.uuid4().hex[:8]}@example.com"

    async def fake_send(recipient, subject, html, *, unsubscribe_token=None, reply_to=None):
        return True

    monkeypatch.setattr("app.services.mailing.send_marketing_email", fake_send)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await register_verified(client, stalled, workspace=False)
            await register_verified(client, suppressed, workspace=False)
            await promote(admin, "admin")
            await backdate(stalled, 10)
            await backdate(suppressed, 10)
            admin_headers = await login_headers(client, admin)

            # A plain platform admin may not send.
            denied = await client.post(
                "/api/v1/admin/mailing/send",
                headers=admin_headers,
                json={"subject": "Finish setup", "body_html": "<p>Hello</p>", "audience": "no_workspace", "min_age_hours": 24},
            )
            assert denied.status_code == 403

            await promote(admin, "super_admin")
            super_headers = await login_headers(client, admin)

            async with SessionLocal() as db:
                db.add(EmailSuppression(email=suppressed, reason="unsubscribed"))
                await db.commit()

            sent = await client.post(
                "/api/v1/admin/mailing/send",
                headers=super_headers,
                json={"subject": "Finish setup", "body_html": "<p>Hello</p>", "audience": "no_workspace", "min_age_hours": 24},
            )
            assert sent.status_code == 200
            result = sent.json()
            assert result["recipients"] >= 2
            assert result["sent"] >= 1
            assert result["skipped"] >= 1
            assert result["test"] is False

            async with SessionLocal() as db:
                records = (await db.execute(select(EmailSend).where(EmailSend.recipient_email == stalled))).scalars().all()
                assert len(records) == 1
                assert records[0].status == "sent"
                opted_out = (await db.execute(select(EmailSend).where(EmailSend.recipient_email == suppressed))).scalars().all()
                assert opted_out == []
    finally:
        await cleanup([admin, stalled, suppressed])


@pytest.mark.asyncio
async def test_test_send_targets_one_address() -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"

    async def fake_send(recipient, subject, html, *, unsubscribe_token=None, reply_to=None):
        return True

    import app.services.mailing as mailing_service

    original = mailing_service.send_marketing_email
    mailing_service.send_marketing_email = fake_send
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await promote(admin, "super_admin")
            headers = await login_headers(client, admin)
            response = await client.post(
                "/api/v1/admin/mailing/send",
                headers=headers,
                json={"subject": "Preview", "body_html": "<p>Preview</p>", "test_email": admin, "min_age_hours": 0},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["test"] is True
            assert body["recipients"] == 1
            assert body["sent"] == 1
    finally:
        mailing_service.send_marketing_email = original
        await cleanup([admin])


@pytest.mark.asyncio
async def test_templates_crud() -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    template_id = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await promote(admin, "admin")
            headers = await login_headers(client, admin)
            created = await client.post(
                "/api/v1/admin/mailing/templates",
                headers=headers,
                json={"name": "Nudge", "subject": "Still there?", "body_html": "<p>Hi</p>"},
            )
            assert created.status_code == 201
            template_id = created.json()["id"]

            listed = await client.get("/api/v1/admin/mailing/templates", headers=headers)
            assert listed.status_code == 200
            assert any(item["id"] == template_id for item in listed.json())

            updated = await client.patch(f"/api/v1/admin/mailing/templates/{template_id}", headers=headers, json={"subject": "New subject"})
            assert updated.status_code == 200
            assert updated.json()["subject"] == "New subject"

            deleted = await client.delete(f"/api/v1/admin/mailing/templates/{template_id}", headers=headers)
            assert deleted.status_code == 204
            template_id = None
            async with SessionLocal() as db:
                assert (await db.get(EmailTemplate, uuid.UUID(created.json()["id"]))) is None
    finally:
        if template_id:
            async with SessionLocal() as db:
                row = await db.get(EmailTemplate, uuid.UUID(template_id))
                if row is not None:
                    await db.delete(row)
                    await db.commit()
        await cleanup([admin])


@pytest.mark.asyncio
async def test_unsubscribe_endpoint_suppresses_and_rejects_bad_token() -> None:
    email = f"mailing-optout-{uuid.uuid4().hex[:8]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, email)
            token = create_unsubscribe_token(email)
            response = await client.get(f"/api/v1/email/unsubscribe?token={token}")
            assert response.status_code == 200
            assert "no longer receive" in response.text

            bad = await client.get("/api/v1/email/unsubscribe?token=not-a-token")
            assert bad.status_code == 400

            async with SessionLocal() as db:
                assert (await db.scalar(select(EmailSuppression.id).where(EmailSuppression.email == email))) is not None
    finally:
        await cleanup([email])


@pytest.mark.asyncio
async def test_ai_settings_mask_secret_and_draft(monkeypatch) -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await clear_ai_settings()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await promote(admin, "super_admin")
            headers = await login_headers(client, admin)

            initial = await client.get("/api/v1/admin/ai-settings", headers=headers)
            assert initial.status_code == 200
            assert initial.json()["api_key_set"] is False
            assert {item["code"] for item in initial.json()["providers"]} == {"openai", "deepseek", "anthropic"}

            # Drafting without a key is a clear 502, not a crash.
            unconfigured = await client.post("/api/v1/admin/mailing/draft", headers=headers, json={"instruction": "Welcome them"})
            assert unconfigured.status_code == 502

            updated = await client.patch(
                "/api/v1/admin/ai-settings",
                headers=headers,
                json={"provider": "deepseek", "api_key": "sk-secret-value", "model": "deepseek-chat"},
            )
            assert updated.status_code == 200
            body = updated.json()
            assert body["provider"] == "deepseek"
            assert body["api_key_set"] is True
            assert "sk-secret-value" not in updated.text
            assert body["api_key_preview"].startswith("sk-sec")

            async def fake_call(provider, model, api_key, base_url, prompt):
                return '{"subject": "Finish setting up Chmaba", "body_html": "<p>Let us help you start selling.</p>"}'

            monkeypatch.setattr("app.services.ai._call_provider", fake_call)
            draft = await client.post("/api/v1/admin/mailing/draft", headers=headers, json={"instruction": "Warm nudge to finish setup", "audience": "no_workspace"})
            assert draft.status_code == 200
            assert draft.json()["subject"] == "Finish setting up Chmaba"
            assert "start selling" in draft.json()["body_html"]
            assert draft.json()["provider"] == "deepseek"
    finally:
        await clear_ai_settings()
        await cleanup([admin])


def test_merge_values_and_render() -> None:
    from app.services.mailing import merge_values, render_merge

    class _Anon:
        full_name = ""
        email = "sokha@example.com"

    fallback = merge_values(_Anon(), None)
    assert fallback["{{name}}"] == "there"
    assert fallback["{{store}}"] == "your store"
    assert fallback["{{email}}"] == "sokha@example.com"

    class _Named:
        full_name = "Sokha Chan"
        email = "sokha@example.com"

    named = merge_values(_Named(), "A & B Mart")
    assert named["{{name}}"] == "Sokha"
    assert named["{{full_name}}"] == "Sokha Chan"
    assert render_merge("<p>Hi {{name}}</p>", named, escape=True) == "<p>Hi Sokha</p>"
    assert render_merge("<p>{{store}}</p>", named, escape=True) == "<p>A &amp; B Mart</p>"
    assert render_merge("Hi {{name}}", named, escape=False) == "Hi Sokha"
    # Unknown placeholders are left alone so typos are visible in preview.
    assert render_merge("<p>{{nope}}</p>", named, escape=True) == "<p>{{nope}}</p>"


@pytest.mark.asyncio
async def test_send_personalizes_tokens_per_recipient() -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    stalled = f"mailing-personal-{uuid.uuid4().hex[:8]}@example.com"
    captured = {}

    async def fake_send(recipient, subject, html, *, unsubscribe_token=None, reply_to=None):
        captured[recipient] = {"subject": subject, "html": html}
        return True

    import app.services.mailing as mailing_service

    original = mailing_service.send_marketing_email
    mailing_service.send_marketing_email = fake_send
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await register_verified(client, stalled, workspace=True, full_name="Sokha Chan")
        await promote(admin, "super_admin")
        await backdate(stalled, 10)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, admin)
            response = await client.post(
                "/api/v1/admin/mailing/send",
                headers=headers,
                json={
                    "subject": "Hi {{name}}",
                    "body_html": "<p>{{name}} from {{store}} - {{email}}</p>",
                    "audience": "no_sales",
                    "min_age_hours": 24,
                },
            )
            assert response.status_code == 200

        assert captured[stalled]["subject"] == "Hi Sokha"
        assert captured[stalled]["html"] == f"<p>Sokha from Mailing Store - {stalled}</p>"
        assert "{{" not in captured[stalled]["html"]

        async with SessionLocal() as db:
            record = (await db.execute(select(EmailSend).where(EmailSend.recipient_email == stalled))).scalars().one()
            assert record.subject == "Hi Sokha"
            assert "Mailing Store" in record.body_html
    finally:
        mailing_service.send_marketing_email = original
        await cleanup([admin, stalled])


@pytest.mark.asyncio
async def test_mailing_image_upload_validates_and_returns_absolute_url() -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            headers = await login_headers(client, admin)
            denied = await client.post("/api/v1/admin/mailing/images", headers=headers, files={"file": ("a.png", png, "image/png")})
            assert denied.status_code == 403
        await promote(admin, "admin")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = await login_headers(client, admin)
            rejected = await client.post("/api/v1/admin/mailing/images", headers=headers, files={"file": ("notes.txt", b"hello", "text/plain")})
            assert rejected.status_code == 422
            uploaded = await client.post("/api/v1/admin/mailing/images", headers=headers, files={"file": ("logo.png", png, "image/png")})
            assert uploaded.status_code == 201
            body = uploaded.json()
            assert body["path"].startswith("/media/platform/mailing/")
            assert body["url"].startswith("http") and body["url"].endswith(body["path"])
            assert body["byte_size"] == len(png)
    finally:
        await cleanup([admin])


async def _clear_drip_config() -> None:
    import app.services.mailing as mailing_service

    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM platform_settings WHERE key = :key"), {"key": mailing_service.DRIP_SETTING_KEY})
        await db.commit()


@pytest.mark.asyncio
async def test_drip_sends_once_per_step_and_is_idempotent() -> None:
    stalled = f"mailing-drip-{uuid.uuid4().hex[:8]}@example.com"
    sent_to = []

    async def fake_send(recipient, subject, html, *, unsubscribe_token=None, reply_to=None):
        sent_to.append(recipient)
        return True

    import app.services.mailing as mailing_service

    original = mailing_service.send_marketing_email
    mailing_service.send_marketing_email = fake_send
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, stalled)
        await backdate(stalled, 5)
        async with SessionLocal() as db:
            await mailing_service.save_drip_config(
                db,
                {
                    "max_age_days": 365,
                    "steps": [
                        {
                            "id": "test-step-1",
                            "day_offset": 2,
                            "audience": "no_workspace",
                            "enabled": True,
                            "subject": "Hi {{name}}",
                            "body_html": "<p>Hello {{name}}</p>",
                        }
                    ],
                },
            )

        async with SessionLocal() as db:
            first = await mailing_service.run_mailing_drip(db)
        assert first["sent"] >= 1
        assert stalled in sent_to

        async with SessionLocal() as db:
            second = await mailing_service.run_mailing_drip(db)
        assert second["sent"] == 0

        async with SessionLocal() as db:
            records = (
                await db.execute(select(EmailSend).where(EmailSend.recipient_email == stalled, EmailSend.source == "drip"))
            ).scalars().all()
            assert len(records) == 1
            assert records[0].subject.startswith("Hi ")
    finally:
        mailing_service.send_marketing_email = original
        await _clear_drip_config()
        await cleanup([stalled])


@pytest.mark.asyncio
async def test_drip_settings_require_super_admin_to_change() -> None:
    admin = f"mailing-admin-{uuid.uuid4().hex[:8]}@example.com"
    try:
        await _clear_drip_config()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await register_verified(client, admin, workspace=True)
            await promote(admin, "admin")
            headers = await login_headers(client, admin)

            current = await client.get("/api/v1/admin/mailing/drip", headers=headers)
            assert current.status_code == 200
            assert current.json()["steps"]

            denied = await client.put(
                "/api/v1/admin/mailing/drip",
                headers=headers,
                json={"max_age_days": 14, "steps": [{"id": "s1", "day_offset": 1, "audience": "no_workspace", "enabled": True, "subject": "Hi", "body_html": "<p>Hi</p>"}]},
            )
            assert denied.status_code == 403

            # Running the drip is also a super-admin action.
            forbidden_run = await client.post("/api/v1/admin/mailing/drip/run", headers=headers)
            assert forbidden_run.status_code == 403

            await promote(admin, "super_admin")
            super_headers = await login_headers(client, admin)
            saved = await client.put(
                "/api/v1/admin/mailing/drip",
                headers=super_headers,
                json={"max_age_days": 14, "steps": [{"id": "s1", "day_offset": 1, "audience": "no_workspace", "enabled": True, "subject": "Hi {{name}}", "body_html": "<p>Hi {{name}}</p>"}]},
            )
            assert saved.status_code == 200
            assert saved.json()["max_age_days"] == 14
            assert saved.json()["steps"][0]["id"] == "s1"
    finally:
        await _clear_drip_config()
        await cleanup([admin])

"""Storefront customer <-> store chat.

Covers the contract the two clients depend on: a guest can start a thread and
resume it with only their visitor token, the store's inbox sees it and is told
about it, a reply comes back on the same thread with the right unread counts, and
a guest who signs in keeps the thread they already had.
"""
from __future__ import annotations

import re
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text

from app.db import SessionLocal
from app.main import app
from app.models import EmailSend, Order, StoreChatConversation, utcnow
from app.services.store_chat import run_unanswered_alerts
from tests.test_lifecycle import cleanup_company, register_and_setup


async def _public_store(client: AsyncClient, ctx: dict) -> tuple[str, str, str]:
    """Enable online ordering and return the public slug address."""
    await client.patch(f"/api/v1/stores/{ctx['store_id']}/public-order", headers=ctx["headers"], json={"enabled": True})
    current = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()
    company_slug, store_slug = current["company"]["slug"], current["store"]["slug"]
    return company_slug, store_slug, f"/api/v1/public/store/{company_slug}/{store_slug}"


async def _shopper_signin_code(email: str) -> str:
    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(EmailSend)
                .where(EmailSend.recipient_email == email, EmailSend.source == "shopper_signin")
                .order_by(EmailSend.created_at.desc())
            )
        ).scalars().first()
    assert row is not None, "a sign-in code should have been queued"
    match = re.search(r"<strong>(\d{6})</strong>", row.body_html or "")
    assert match, row.body_html
    return match.group(1)


async def _purge_shopper(email: str) -> None:
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM shopper_email_codes WHERE shopper_id IN (SELECT id FROM shopper_accounts WHERE email = :e)"), {"e": email})
        await db.execute(text("DELETE FROM shopper_accounts WHERE email = :e"), {"e": email})
        await db.commit()


@pytest.mark.asyncio
async def test_storefront_chat_guest_store_conversation() -> None:
    company_id: str | None = None
    ctx: dict | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Co {suffix}", f"Chat Till {suffix}", email_prefix="chat")
            company_id = ctx["company_id"]
            _, _, base = await _public_store(client, ctx)

            # A guest starts the thread with no account at all.
            first = await client.post(f"{base}/chat/messages", json={"body": "Hi, do you deliver?", "name": "Dara", "email": "dara@example.com", "phone": "+855 12 345 678"})
            assert first.status_code == 201, first.text
            body = first.json()
            token = body["visitor_token"]
            conversation_id = body["conversation"]["id"]
            assert body["conversation"]["guest_name"] == "Dara"
            assert body["message"]["sender_type"] == "customer"
            # The thread labels the customer by the name they gave.
            assert body["message"]["author_name"] == "Dara"
            assert token

            # The store is told, and the thread reads as unread.
            unread = await client.get("/api/v1/store-chat/unread-count", headers=ctx["store_headers"])
            assert unread.status_code == 200
            assert unread.json()["unread"] == 1
            listing = (await client.get("/api/v1/store-chat/conversations", headers=ctx["store_headers"])).json()
            assert len(listing) == 1
            assert listing[0]["unread_count"] == 1
            assert listing[0]["last_message_preview"] == "Hi, do you deliver?"
            notifications = (await client.get("/api/v1/notifications", headers=ctx["headers"])).json()
            assert any(item["type"] == "store_chat_message" for item in notifications)

            # Opening the thread clears the store badge.
            thread = await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])
            assert thread.status_code == 200
            assert len(thread.json()["messages"]) == 1
            # The seller's thread panel gets the guest's contact details, both on
            # the thread and in the list summary.
            assert thread.json()["contact_email"] == "dara@example.com"
            assert thread.json()["contact_phone"] == "+855 12 345 678"
            assert listing[0]["contact_email"] == "dara@example.com"
            assert (await client.get("/api/v1/store-chat/unread-count", headers=ctx["store_headers"])).json()["unread"] == 0

            # Opening the thread also clears the bell that announced it, so a thread
            # the store has answered no longer looks unanswered after re-login.
            unread_only = (await client.get("/api/v1/notifications", headers=ctx["headers"], params={"unread_only": True})).json()
            assert not any(item["type"] == "store_chat_message" for item in unread_only)
            chat_notes = [item for item in (await client.get("/api/v1/notifications", headers=ctx["headers"])).json() if item["type"] == "store_chat_message"]
            assert chat_notes and all(item["is_read"] for item in chat_notes)

            # The store can name a thread for its own benefit. The label is private:
            # it is on the seller's copy and never on the customer's.
            renamed = await client.patch(
                f"/api/v1/store-chat/conversations/{conversation_id}",
                headers=ctx["store_headers"],
                json={"seller_label": "Table 4"},
            )
            assert renamed.status_code == 200, renamed.text
            assert renamed.json()["seller_label"] == "Table 4"
            assert renamed.json()["status"] == "open"
            customer_view = await client.get(f"{base}/chat/session", headers={"X-Chat-Token": token})
            assert customer_view.json()["conversation"]["seller_label"] is None
            # Contact details belong to the store, not the customer: the storefront
            # read blanks them exactly like the private seller label.
            assert customer_view.json()["conversation"]["contact_email"] is None
            assert customer_view.json()["conversation"]["contact_phone"] is None

            # A store reply lands on the same thread and un-reads it for the customer.
            reply = await client.post(
                f"/api/v1/store-chat/conversations/{conversation_id}/messages",
                headers=ctx["store_headers"],
                json={"body": "Yes, within 5km.", "kind": "text"},
            )
            assert reply.status_code == 201, reply.text
            assert reply.json()["message"]["sender_type"] == "seller"
            # The internal inbox names the person who replied.
            assert reply.json()["message"]["author_name"] == "Lifecycle Owner"

            session = await client.get(f"{base}/chat/session", headers={"X-Chat-Token": token})
            assert session.status_code == 200
            session_body = session.json()
            assert session_body["conversation"]["id"] == conversation_id
            assert session_body["unread_count"] == 1
            assert [m["sender_type"] for m in session_body["messages"]] == ["customer", "seller"]
            # A seller reply is credited to the store, never to the staff member:
            # the customer must not learn who is behind the counter.
            store_name = (await client.get("/api/v1/workspaces/current", headers=ctx["store_headers"])).json()["store"]["name"]
            assert session_body["messages"][1]["author_name"] == store_name

            # The customer's own read clears their side only.
            cleared = await client.post(f"{base}/chat/read", headers={"X-Chat-Token": token})
            assert cleared.status_code == 200
            after = await client.get(f"{base}/chat/messages", headers={"X-Chat-Token": token}, params={"after_seq": session_body["messages"][-1]["seq"]})
            assert after.json() == []

            # Emoji reactions are per side.
            last_message_id = session_body["messages"][-1]["id"]
            reacted = await client.post(f"{base}/chat/messages/{last_message_id}/reactions", headers={"X-Chat-Token": token}, json={"emoji": "👍"})
            assert reacted.status_code == 200
            assert reacted.json()["reactions"][0]["emoji"] == "👍"
            assert reacted.json()["reactions"][0]["reacted"] is True
            seller_view = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            seller_last = seller_view["messages"][-1]
            assert seller_last["reactions"][0]["count"] == 1
            assert seller_last["reactions"][0]["reacted"] is False

            # Voice notes and images upload, then attach to a message.
            upload = await client.post(f"{base}/chat/upload", files={"file": ("voice.webm", b"chmaba-voice", "audio/webm")})
            assert upload.status_code == 201, upload.text
            assert upload.json()["kind"] == "voice"
            sent_voice = await client.post(
                f"{base}/chat/messages",
                headers={"X-Chat-Token": token},
                json={
                    "kind": "voice",
                    "attachment_url": upload.json()["url"],
                    "attachment_content_type": "audio/webm",
                    "attachment_byte_size": upload.json()["byte_size"],
                    "attachment_duration_ms": 3200,
                },
            )
            assert sent_voice.status_code == 201, sent_voice.text
            assert sent_voice.json()["message"]["attachment"]["duration_ms"] == 3200

            # Guard rails: an empty text message is refused, and a token that names
            # nothing cannot be used to walk into a new thread.
            assert (await client.post(f"{base}/chat/messages", json={"body": "   "})).status_code == 400
            assert (await client.post(f"{base}/chat/messages", headers={"X-Chat-Token": "not-a-real-token"}, json={"body": "hi"})).status_code == 404
            assert (await client.post(f"{base}/chat/messages", json={"kind": "file", "attachment_url": "https://evil.example/x.pdf"})).status_code == 400
    finally:
        if ctx is not None:
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])


@pytest.mark.asyncio
async def test_storefront_chat_guest_keeps_thread_after_signin() -> None:
    company_id: str | None = None
    ctx: dict | None = None
    shopper_email = f"chat-shopper-{uuid.uuid4().hex[:10]}@example.com"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Shopper Co {suffix}", f"Chat Shopper Till {suffix}", email_prefix="chat-shop")
            company_id = ctx["company_id"]
            _, _, base = await _public_store(client, ctx)

            started = await client.post(f"{base}/chat/messages", json={"body": "Is the blue one in stock?", "name": "Guest"})
            assert started.status_code == 201, started.text
            token = started.json()["visitor_token"]
            conversation_id = started.json()["conversation"]["id"]

            # Sign in as a shopper through the emailed code.
            assert (await client.post("/api/v1/public/auth/email-code", json={"email": shopper_email})).status_code == 202
            code = await _shopper_signin_code(shopper_email)
            verified = await client.post("/api/v1/public/auth/verify", json={"email": shopper_email, "code": code})
            assert verified.status_code == 200, verified.text
            shopper_headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}

            # The next message carries both the thread token and the account, which
            # is what moves ownership of the existing thread to the account.
            merged = await client.post(
                f"{base}/chat/messages",
                headers={**shopper_headers, "X-Chat-Token": token},
                json={"body": "It's me, signed in now."},
            )
            assert merged.status_code == 201, merged.text
            assert merged.json()["conversation"]["id"] == conversation_id

            mine = await client.get("/api/v1/public/auth/chat/conversations", headers=shopper_headers)
            assert mine.status_code == 200
            assert [row["id"] for row in mine.json()] == [conversation_id]
            assert mine.json()[0]["shopper_name"]

            # Once the thread belongs to an account, the store's panel shows the
            # account's email as the contact.
            shopper_thread = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            assert shopper_thread["contact_email"] == shopper_email
    finally:
        if ctx is not None:
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])
        await _purge_shopper(shopper_email)


@pytest.mark.asyncio
async def test_storefront_chat_reliability() -> None:
    """Scrollback, idle close, and the unanswered-message alert."""
    company_id: str | None = None
    ctx: dict | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Rel Co {suffix}", f"Chat Rel Till {suffix}", email_prefix="chat-rel")
            company_id = ctx["company_id"]
            _, _, base = await _public_store(client, ctx)

            first = await client.post(f"{base}/chat/messages", json={"body": "Anyone there?", "name": "Dara"})
            assert first.status_code == 201, first.text
            token = first.json()["visitor_token"]
            conversation_id = first.json()["conversation"]["id"]
            for body in ("second", "third"):
                sent = await client.post(f"{base}/chat/messages", headers={"X-Chat-Token": token}, json={"body": body})
                assert sent.status_code == 201, sent.text

            thread = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            newest_seq = thread["messages"][-1]["seq"]

            # Scrollback: the page strictly older than the cursor, oldest first.
            older = (
                await client.get(
                    f"/api/v1/store-chat/conversations/{conversation_id}",
                    headers=ctx["store_headers"],
                    params={"before_seq": newest_seq},
                )
            ).json()
            assert [m["body"] for m in older["messages"]] == ["Anyone there?", "second"]
            assert older["has_more"] is False

            # Idle close: a thread untouched for days closes itself when the inbox is read.
            async with SessionLocal() as db:
                conversation = await db.get(StoreChatConversation, uuid.UUID(conversation_id))
                conversation.last_message_at = utcnow() - timedelta(days=4)
                await db.commit()
            listing = (await client.get("/api/v1/store-chat/conversations", headers=ctx["store_headers"], params={"status": "all"})).json()
            assert listing[0]["status"] == "closed"

            # Unanswered alert: one customer message past the window queues one email, and
            # a second scan sends nothing more.
            async with SessionLocal() as db:
                conversation = await db.get(StoreChatConversation, uuid.UUID(conversation_id))
                conversation.status = "open"
                conversation.seller_unread_count = 1
                conversation.last_message_author = "customer"
                conversation.seller_notified_at = None
                conversation.last_message_at = utcnow() - timedelta(hours=2)
                await db.commit()

                stats = await run_unanswered_alerts(db, unanswered_minutes=30)
                await db.commit()
                assert stats["emails"] >= 1

                queued = await db.scalar(
                    select(func.count(EmailSend.id)).where(
                        EmailSend.source == "store_chat_alert",
                        EmailSend.recipient_email == ctx["email"],
                    )
                )
                assert queued and queued >= 1

                again = await run_unanswered_alerts(db, unanswered_minutes=30)
                await db.commit()
                assert again["emails"] == 0
    finally:
        if ctx is not None:
            async with SessionLocal() as db:
                # The outbox row is ours and outlives the user (email_sends.user_id
                # is ON DELETE SET NULL), so clear it rather than leave it for
                # another test's mail drain to trip over.
                await db.execute(
                    text("DELETE FROM email_sends WHERE source = 'store_chat_alert' AND recipient_email = :email"),
                    {"email": ctx["email"]},
                )
                await db.commit()
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])


@pytest.mark.asyncio
async def test_storefront_chat_canned_replies() -> None:
    """Quick replies: saved, listed, edited, deleted, and validated."""
    company_id: str | None = None
    ctx: dict | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Canned Co {suffix}", f"Chat Canned Till {suffix}", email_prefix="chat-canned")
            company_id = ctx["company_id"]
            headers = ctx["store_headers"]

            assert (await client.get("/api/v1/store-chat/canned-replies", headers=headers)).json() == []

            created = await client.post(
                "/api/v1/store-chat/canned-replies",
                headers=headers,
                json={"label": "Delivery area", "body": "We deliver within 5km."},
            )
            assert created.status_code == 201, created.text
            reply_id = created.json()["id"]
            assert created.json()["label"] == "Delivery area"

            listed = (await client.get("/api/v1/store-chat/canned-replies", headers=headers)).json()
            assert [row["id"] for row in listed] == [reply_id]

            updated = await client.patch(
                f"/api/v1/store-chat/canned-replies/{reply_id}",
                headers=headers,
                json={"label": "Delivery", "body": "Within 5km, about 45 minutes."},
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["body"] == "Within 5km, about 45 minutes."

            # A blank label or a blank message is refused, whitespace included.
            assert (await client.post("/api/v1/store-chat/canned-replies", headers=headers, json={"label": "", "body": "x"})).status_code == 422
            assert (await client.post("/api/v1/store-chat/canned-replies", headers=headers, json={"label": "x", "body": "  "})).status_code == 400

            assert (await client.delete(f"/api/v1/store-chat/canned-replies/{reply_id}", headers=headers)).status_code == 204
            assert (await client.get("/api/v1/store-chat/canned-replies", headers=headers)).json() == []
            assert (await client.delete(f"/api/v1/store-chat/canned-replies/{reply_id}", headers=headers)).status_code == 404
    finally:
        if ctx is not None:
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])


@pytest.mark.asyncio
async def test_storefront_chat_order_card() -> None:
    """A seller can send an order card; the customer sees it on their thread."""
    company_id: str | None = None
    ctx: dict | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Order Co {suffix}", f"Chat Order Till {suffix}", email_prefix="chat-order")
            company_id = ctx["company_id"]
            _, _, base = await _public_store(client, ctx)

            started = await client.post(f"{base}/chat/messages", json={"body": "Where is my order?", "name": "Dara"})
            assert started.status_code == 201, started.text
            token = started.json()["visitor_token"]
            conversation_id = started.json()["conversation"]["id"]

            # An order of this store to point the card at.
            async with SessionLocal() as db:
                order = Order(
                    store_id=uuid.UUID(ctx["store_id"]),
                    order_number=f"A-{suffix}",
                    status="paid",
                    currency_code="USD",
                    subtotal=Decimal("12.00"),
                    total=Decimal("12.00"),
                    source="online",
                    order_type="takeaway",
                    public_token=f"tok-{suffix}",
                )
                db.add(order)
                await db.commit()
                order_id, order_number = str(order.id), order.order_number

            reply = await client.post(
                f"/api/v1/store-chat/conversations/{conversation_id}/messages",
                headers=ctx["store_headers"],
                json={"kind": "order", "order_id": order_id},
            )
            assert reply.status_code == 201, reply.text
            card = reply.json()["message"]
            assert card["kind"] == "order"
            assert card["order"]["order_number"] == order_number
            assert card["order"]["public_token"] == f"tok-{suffix}"

            # The thread carries the shared orders as their own list, complete even
            # when a page of messages excludes the order's own message.
            thread = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            assert [o["order_number"] for o in thread["orders"]] == [order_number]
            scrollback = (
                await client.get(
                    f"/api/v1/store-chat/conversations/{conversation_id}",
                    headers=ctx["store_headers"],
                    params={"before_seq": card["seq"]},
                )
            ).json()
            assert all(message["order"] is None for message in scrollback["messages"])
            assert [o["order_number"] for o in scrollback["orders"]] == [order_number]

            # An unknown order cannot be attached.
            missing = await client.post(
                f"/api/v1/store-chat/conversations/{conversation_id}/messages",
                headers=ctx["store_headers"],
                json={"kind": "order", "order_id": str(uuid.uuid4())},
            )
            assert missing.status_code == 404

            # The customer's own copy carries the same card.
            session = (await client.get(f"{base}/chat/session", headers={"X-Chat-Token": token})).json()
            assert session["messages"][-1]["order"]["order_number"] == order_number
    finally:
        if ctx is not None:
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])


@pytest.mark.asyncio
async def test_storefront_chat_read_receipts() -> None:
    """A message reads as "seen" for its sender once the other side has read the thread."""
    company_id: str | None = None
    ctx: dict | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Read Co {suffix}", f"Chat Read Till {suffix}", email_prefix="chat-read")
            company_id = ctx["company_id"]
            _, _, base = await _public_store(client, ctx)

            started = await client.post(f"{base}/chat/messages", json={"body": "hello", "name": "Dara"})
            assert started.status_code == 201, started.text
            token = started.json()["visitor_token"]
            conversation_id = started.json()["conversation"]["id"]

            # The shopper's message is not seen until the store opens the thread.
            before = (await client.get(f"{base}/chat/session", headers={"X-Chat-Token": token})).json()
            assert before["messages"][0]["seen"] is False

            opened = await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])
            assert opened.status_code == 200

            after = (await client.get(f"{base}/chat/session", headers={"X-Chat-Token": token})).json()
            assert after["messages"][0]["seen"] is True

            # The store replies; it is unseen until the customer reads.
            reply = await client.post(
                f"/api/v1/store-chat/conversations/{conversation_id}/messages",
                headers=ctx["store_headers"],
                json={"kind": "text", "body": "hi there"},
            )
            assert reply.status_code == 201, reply.text
            unseen = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            assert unseen["messages"][-1]["sender_type"] == "seller"
            assert unseen["messages"][-1]["seen"] is False

            assert (await client.post(f"{base}/chat/read", headers={"X-Chat-Token": token})).status_code == 200
            seen = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            assert seen["messages"][-1]["seen"] is True
    finally:
        if ctx is not None:
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])


@pytest.mark.asyncio
async def test_storefront_chat_claim_and_notes() -> None:
    """A thread can be claimed and noted on; neither reaches the customer."""
    company_id: str | None = None
    ctx: dict | None = None
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            suffix = uuid.uuid4().hex[:6]
            ctx = await register_and_setup(client, f"Chat Claim Co {suffix}", f"Chat Claim Till {suffix}", email_prefix="chat-claim")
            company_id = ctx["company_id"]
            _, _, base = await _public_store(client, ctx)

            started = await client.post(f"{base}/chat/messages", json={"body": "hi", "name": "Dara"})
            assert started.status_code == 201, started.text
            token = started.json()["visitor_token"]
            conversation_id = started.json()["conversation"]["id"]
            me_id = (await client.get("/api/v1/auth/me", headers=ctx["headers"])).json()["id"]

            # Claim the thread for myself.
            claimed = await client.patch(
                f"/api/v1/store-chat/conversations/{conversation_id}",
                headers=ctx["store_headers"],
                json={"assigned_user_id": me_id},
            )
            assert claimed.status_code == 200, claimed.text
            assert claimed.json()["assigned_user_id"] == me_id
            assert claimed.json()["assigned_user_name"]

            # A note lives on the seller's thread read, never on the customer's copy.
            noted = await client.patch(
                f"/api/v1/store-chat/conversations/{conversation_id}",
                headers=ctx["store_headers"],
                json={"internal_notes": "Wants the blue one"},
            )
            assert noted.status_code == 200, noted.text
            thread = (await client.get(f"/api/v1/store-chat/conversations/{conversation_id}", headers=ctx["store_headers"])).json()
            assert thread["internal_notes"] == "Wants the blue one"
            customer = (await client.get(f"{base}/chat/session", headers={"X-Chat-Token": token})).json()["conversation"]
            assert customer["assigned_user_id"] is None
            assert "internal_notes" not in customer

            # Release, and refuse a person who cannot see this store.
            released = await client.patch(
                f"/api/v1/store-chat/conversations/{conversation_id}",
                headers=ctx["store_headers"],
                json={"assigned_user_id": None},
            )
            assert released.json()["assigned_user_id"] is None
            assert released.json()["assigned_user_name"] is None
            stranger = await client.patch(
                f"/api/v1/store-chat/conversations/{conversation_id}",
                headers=ctx["store_headers"],
                json={"assigned_user_id": str(uuid.uuid4())},
            )
            assert stranger.status_code == 400
    finally:
        if ctx is not None:
            await cleanup_company(ctx["company_id"], [ctx["email"]])
        elif company_id:
            await cleanup_company(company_id, [])

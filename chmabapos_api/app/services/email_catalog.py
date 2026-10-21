"""Every email Chmaba sends, in one read-only inventory.

The admin Mailing screen used to show only ``EmailTemplate`` rows - campaigns an
operator saved by hand - so automated mail such as "Reset your password" never
appeared there and looked missing. This module is the catalog behind the
"System emails" section of that screen: one entry per message the platform can
deliver, with who receives it and what triggers it.

The copy for these messages lives in code (``app.email``, ``sale_emails``,
``store_notifications``, ``billing_emails``, ``reminders``, ``quota_warnings``,
``store_chat`` and the support flows) because the bodies are built from live
records: an order total, a receipt number, the items in a shift. They are
therefore listed for review, not editing; the operator-editable onboarding
sequence is seeded separately as ``EmailTemplate`` rows.

Keep this list in step with the senders: ``tests/test_mailing.py`` asserts the
catalog covers every category and that keys stay unique.
"""
from __future__ import annotations

from typing import Final, TypedDict


class EmailCatalogEntry(TypedDict):
    """One message the platform can send, for the admin inventory."""

    key: str
    name: str
    category: str
    audience: str
    trigger: str
    subject: str
    delivery: str


# Display order of the sections on the Mailing screen.
EMAIL_CATEGORIES: Final[tuple[str, ...]] = (
    "Account and security",
    "Onboarding",
    "Sales and receipts",
    "Store operations",
    "Billing",
    "Support",
    "Marketing",
    "Internal",
)


SYSTEM_EMAILS: Final[tuple[EmailCatalogEntry, ...]] = (
    # ------------------------------------------------------------------
    # Account and security (sent inline, never through the marketing queue)
    # ------------------------------------------------------------------
    {
        "key": "account.verify_email",
        "name": "Confirm your email",
        "category": "Account and security",
        "audience": "Account owner",
        "trigger": "Sent on sign-up, and again when the merchant taps Resend.",
        "subject": "Your Chmaba confirmation code",
        "delivery": "Instant",
    },
    {
        "key": "account.password_reset",
        "name": "Reset your password",
        "category": "Account and security",
        "audience": "Account owner",
        "trigger": "Requested with Forgot password on the sign-in screen. The link expires in 30 minutes.",
        "subject": "Reset your Chmaba password",
        "delivery": "Instant",
    },
    {
        "key": "account.password_changed",
        "name": "Password changed",
        "category": "Account and security",
        "audience": "Account owner",
        "trigger": "Sent after a password reset or a password change in settings.",
        "subject": "Your Chmaba password was changed",
        "delivery": "Instant",
    },
    {
        "key": "account.new_signin",
        "name": "New sign-in",
        "category": "Account and security",
        "audience": "Account owner",
        "trigger": "Sent when the account is signed in to from a new device.",
        "subject": "New sign-in to your Chmaba account",
        "delivery": "Instant",
    },
    {
        "key": "account.invitation",
        "name": "Workspace invitation",
        "category": "Account and security",
        "audience": "Invited teammate",
        "trigger": "An owner or manager invites a teammate from Team. The link expires in 7 days.",
        "subject": "You were invited to {company} on Chmaba",
        "delivery": "Instant",
    },
    {
        "key": "account.shopper_signin_code",
        "name": "Shopper sign-in code",
        "category": "Account and security",
        "audience": "Storefront shopper",
        "trigger": "A shopper asks for a one-time code on the storefront. The code expires in 15 minutes.",
        "subject": "Your Chmaba sign-in code",
        "delivery": "Queued",
    },
    # ------------------------------------------------------------------
    # Onboarding (also mirrored as saved templates and editable in the drip)
    # ------------------------------------------------------------------
    {
        "key": "onboarding.welcome",
        "name": "Welcome to Chmaba",
        "category": "Onboarding",
        "audience": "New merchant",
        "trigger": "The account email is confirmed for the first time.",
        "subject": "Welcome to Chmaba",
        "delivery": "Instant",
    },
    {
        "key": "onboarding.store_ready",
        "name": "Your store is ready",
        "category": "Onboarding",
        "audience": "New merchant",
        "trigger": "The first workspace and store are created.",
        "subject": "Your Chmaba store is ready",
        "delivery": "Instant",
    },
    {
        "key": "onboarding.drip",
        "name": "Onboarding follow-ups (9 steps)",
        "category": "Onboarding",
        "audience": "Stalled signup",
        "trigger": "Automated drip on days 1-7 for a confirmed or unconfirmed signup with no workspace, no real product, or no sale. Editable under Automated drip.",
        "subject": "Nine subjects - see Automated drip",
        "delivery": "Scheduled",
    },
    # ------------------------------------------------------------------
    # Sales and receipts (queued through the outbox)
    # ------------------------------------------------------------------
    {
        "key": "sales.sale_alert",
        "name": "New sale alert",
        "category": "Sales and receipts",
        "audience": "Workspace owner",
        "trigger": "A sale is completed and the store has sale alerts on. Set the frequency to daily to send one 'Sales today' summary instead.",
        "subject": "New sale · {store} · {total}",
        "delivery": "Queued",
    },
    {
        "key": "sales.sales_today",
        "name": "Sales today (daily alert)",
        "category": "Sales and receipts",
        "audience": "Workspace owner",
        "trigger": "Once a day when sale alerts are set to the daily frequency.",
        "subject": "Sales today · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "sales.receipt",
        "name": "Customer receipt",
        "category": "Sales and receipts",
        "audience": "Customer",
        "trigger": "A paid sale when customer receipts are on and the plan includes email receipts, or an operator resends one from the order.",
        "subject": "Your receipt for {order}",
        "delivery": "Queued",
    },
    {
        "key": "sales.deposit_receipt",
        "name": "Deposit receipt (pickup order)",
        "category": "Sales and receipts",
        "audience": "Customer",
        "trigger": "A pickup order is paid with a deposit; the receipt shows the balance still due.",
        "subject": "Your deposit receipt for {order}",
        "delivery": "Queued",
    },
    {
        "key": "sales.refund_confirmation",
        "name": "Refund processed (customer)",
        "category": "Sales and receipts",
        "audience": "Customer",
        "trigger": "A refund is recorded on an order with a customer email and the plan includes email receipts.",
        "subject": "Refund processed · {order}",
        "delivery": "Queued",
    },
    {
        "key": "sales.online_order_received",
        "name": "Online order received",
        "category": "Sales and receipts",
        "audience": "Customer",
        "trigger": "A customer submits an online or QR order with an email address.",
        "subject": "Order received · {store}",
        "delivery": "Queued",
    },
    {
        "key": "sales.online_order_closed",
        "name": "Unpaid order closed",
        "category": "Sales and receipts",
        "audience": "Customer",
        "trigger": "An unpaid online or QR order passes the store's payment window and is closed.",
        "subject": "Order closed - {store}",
        "delivery": "Queued",
    },
    {
        "key": "sales.service_complete",
        "name": "Service complete",
        "category": "Sales and receipts",
        "audience": "Customer",
        "trigger": "A service ticket for a sold serial is resolved and the plan includes email receipts.",
        "subject": "Service complete · {store}",
        "delivery": "Queued",
    },
    # ------------------------------------------------------------------
    # Store operations (owner notifications, each with a store setting)
    # ------------------------------------------------------------------
    {
        "key": "operations.daily_summary",
        "name": "Daily summary",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "Once a day when Daily summary is on in the store's notifications.",
        "subject": "Daily summary · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.weekly_summary",
        "name": "Weekly summary",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "Every Monday when Weekly report is on in the store's notifications.",
        "subject": "Weekly summary · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.monthly_summary",
        "name": "Monthly summary",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "On the first of the month when Monthly report is on in the store's notifications.",
        "subject": "Monthly summary · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.low_stock",
        "name": "Low stock alert",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "Once a day when Low stock alerts is on and an item is at or below its reorder point.",
        "subject": "Low stock alert · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.operations_digest",
        "name": "Operations summary",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "Once a day when Operations digest is on and there are approvals, discount reviews, refund reviews or stock transfers.",
        "subject": "Operations summary · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.warranty_expiry",
        "name": "Warranties expiring soon",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "Every Monday when Warranty expiry is on and a sold serial's warranty ends within 30 days.",
        "subject": "Warranties expiring · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.refund_recorded",
        "name": "Refund recorded (owner)",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "A refund is recorded and Refund activity is on in the store's notifications.",
        "subject": "Refund · {store} · {amount}",
        "delivery": "Queued",
    },
    {
        "key": "operations.online_order",
        "name": "New online order (owner)",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "A customer submits an online or QR order and Online orders is on in the store's notifications.",
        "subject": "New online order · {store}",
        "delivery": "Queued",
    },
    {
        "key": "operations.shift_closed",
        "name": "Shift closed",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "A cashier closes a shift and Shift reports is on in the store's notifications.",
        "subject": "Shift closed · {store}",
        "delivery": "Queued",
    },
    {
        "key": "operations.shift_still_open",
        "name": "Shift still open",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "A shift has stayed open for more than 12 hours and Shift reminders is on.",
        "subject": "Shift still open · {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.team_activity",
        "name": "Team activity",
        "category": "Store operations",
        "audience": "Workspace owner",
        "trigger": "A teammate is added, removed or changed and Team activity is on.",
        "subject": "{activity title}",
        "delivery": "Queued",
    },
    {
        "key": "operations.chat_waiting",
        "name": "Customer waiting for a reply",
        "category": "Store operations",
        "audience": "Workspace owner and managers",
        "trigger": "A store chat message has waited too long for a reply and chat alerts are on.",
        "subject": "Waiting for a reply at {store}",
        "delivery": "Scheduled",
    },
    {
        "key": "operations.chat_reply",
        "name": "Store replied to a shopper",
        "category": "Store operations",
        "audience": "Storefront shopper",
        "trigger": "The store replies in chat and the shopper left an email address. At most one per hour per conversation.",
        "subject": "{store} replied to your message",
        "delivery": "Queued",
    },
    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------
    {
        "key": "billing.payment_received",
        "name": "Payment received",
        "category": "Billing",
        "audience": "Workspace owner",
        "trigger": "A plan payment succeeds; the receipt number and paid-through date are included.",
        "subject": "Payment received · {receipt}",
        "delivery": "Queued",
    },
    {
        "key": "billing.payment_failed",
        "name": "Payment did not go through",
        "category": "Billing",
        "audience": "Workspace owner",
        "trigger": "A plan payment fails or expires before it is paid.",
        "subject": "Payment did not go through · {plan}",
        "delivery": "Queued",
    },
    {
        "key": "billing.renewal_reminder",
        "name": "Renewal reminder",
        "category": "Billing",
        "audience": "Workspace owner",
        "trigger": "A paid plan is ending and a reminder offset is due; also covers a scheduled plan switch and a plan already in grace.",
        "subject": "Renew your {plan} plan - ${amount} {cycle}",
        "delivery": "Scheduled",
    },
    {
        "key": "billing.plan_expired",
        "name": "Plan expired",
        "category": "Billing",
        "audience": "Workspace owner",
        "trigger": "A paid plan lapses and the workspace falls back to Free; lists what was paused.",
        "subject": "Your {plan} plan has expired",
        "delivery": "Queued",
    },
    {
        "key": "billing.quota_warning",
        "name": "Approaching plan limits",
        "category": "Billing",
        "audience": "Workspace owner",
        "trigger": "A workspace crosses the warning threshold for stores, team members or monthly transactions.",
        "subject": "Approaching your plan limits · {plan}",
        "delivery": "Queued",
    },
    # ------------------------------------------------------------------
    # Support
    # ------------------------------------------------------------------
    {
        "key": "support.request_received",
        "name": "Support request received",
        "category": "Support",
        "audience": "Merchant",
        "trigger": "A merchant escalates a question to the human support team.",
        "subject": "We received your support request ({reference})",
        "delivery": "Instant",
    },
    {
        "key": "support.status_changed",
        "name": "Support request status changed",
        "category": "Support",
        "audience": "Merchant",
        "trigger": "An admin moves a support request to resolved, closed, pending or open.",
        "subject": "Your support request {reference} is resolved",
        "delivery": "Instant",
    },
    {
        "key": "support.reply",
        "name": "Support replied",
        "category": "Support",
        "audience": "Merchant",
        "trigger": "An admin replies on a support request.",
        "subject": "New reply on your support request {reference}",
        "delivery": "Instant",
    },
    # ------------------------------------------------------------------
    # Marketing
    # ------------------------------------------------------------------
    {
        "key": "marketing.manual_campaign",
        "name": "Manual campaign",
        "category": "Marketing",
        "audience": "Chosen merchant segment",
        "trigger": "An operator composes and sends a campaign from the Compose tab. Subject and body are written per send.",
        "subject": "Written per campaign",
        "delivery": "Queued",
    },
    # ------------------------------------------------------------------
    # Internal (Chmaba team, not customers)
    # ------------------------------------------------------------------
    {
        "key": "internal.support_merchant_reply",
        "name": "Merchant reply on a support ticket",
        "category": "Internal",
        "audience": "Chmaba support inbox",
        "trigger": "A merchant replies on a support ticket and a support inbox is configured.",
        "subject": "Merchant reply on support ticket {reference}",
        "delivery": "Instant",
    },
    {
        "key": "internal.mail_failure_alert",
        "name": "Mail delivery failures",
        "category": "Internal",
        "audience": "Platform admins",
        "trigger": "Queued mail exhausts its retries, so an operator can check the provider and the affected recipients.",
        "subject": "Mail delivery failures · {count} message(s)",
        "delivery": "Instant",
    },
    {
        "key": "internal.test_email",
        "name": "Test email",
        "category": "Internal",
        "audience": "Platform admin",
        "trigger": "An operator sends a test from Settings > Email to verify the provider.",
        "subject": "Chmaba test email",
        "delivery": "Instant",
    },
)


def email_catalog() -> list[dict[str, str]]:
    """The catalog as plain dicts, ready for the API schema."""
    return [dict(entry) for entry in SYSTEM_EMAILS]

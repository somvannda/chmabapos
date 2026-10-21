"""Sample renderings of the system emails, for the admin Mailing screen.

The Mailing catalog (``app.services.email_catalog``) lists every message Chmaba
sends. An operator also wants to see what each one looks like, but a receipt or
a daily summary only exists once a real order or day is in the database.

This module renders each message with representative sample data through the
same shared layout (``transactional_email`` / ``marketing_email``) as the live
senders, so the preview shows the true shell, type scale, badge and buttons.
The data is marked as a sample in the UI; the live body is assembled at send
time from the store's own records.
"""
from __future__ import annotations

from typing import Final

from app.services.email_layout import code_block, marketing_email, totals_table, transactional_email
from app.services.email_layout import data_table as table
from app.services.onboarding_emails import ONBOARDING_EMAILS

STORE: Final = "Sokha Mart"
COMPANY: Final = "Sokha Retail"
CUSTOMER: Final = "Dara"
ORDER: Final = "ORD-1042"
APP: Final = "https://chmaba.com"

_ITEMS = [["Iced coffee", "2", "$3.50", "$7.00"], ["Croissant", "1", "$2.25", "$2.25"]]
_TOTALS = [("Subtotal", "$9.25"), ("Tax", "$0.74"), ("Total", "$9.99")]


def _email(heading: str, preview: str, body: str, badge: str, **kwargs) -> str:
    return transactional_email(heading=heading, preview=preview, body=body, badge=badge, **kwargs)


def _paragraphs(*lines: str) -> str:
    return "".join(f'<p style="margin:0 0 12px 0;">{line}</p>' for line in lines)


def _order_facts() -> str:
    return table(
        ["Order", "When", "Customer"],
        [[ORDER, "21 Oct 2026 10:42", CUSTOMER]],
    )


def _item_table() -> str:
    return table(["Item", "Qty", "Price", "Amount"], _ITEMS, aligns=["left", "right", "right", "right"])


def _subjects_and_bodies() -> dict[str, str]:
    """Every catalog key mapped to its sample HTML."""

    draft = str(ONBOARDING_EMAILS[0]["body_html"]).replace("{{base}}", APP).replace("{{name}}", "Sokha")

    return {
        # -- Account and security -------------------------------------
        "account.verify_email": _email(
            "Confirm your email",
            "Your Chmaba confirmation code is 482913.",
            '<p style="margin:0 0 4px 0;">Enter this 6-digit code on the sign-up screen to confirm your Chmaba account:</p>'
            + code_block("482913")
            + '<p style="margin:18px 0 0 0;">This code expires in 24 hours. If you did not create a Chmaba account, you can ignore this email.</p>',
            "Verify",
        ),
        "account.password_reset": _email(
            "Reset your Chmaba password",
            "Reset your Chmaba password. This link expires in 30 minutes.",
            '<p style="margin:0 0 4px 0;">We received a request to reset your Chmaba password. Choose a new one with the button below.</p>'
            f'<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br /><a href="{APP}/reset-password?token=sample" style="color:#6957f5;">{APP}/reset-password?token=sample</a></p>',
            "Security",
            cta_label="Reset password",
            cta_href=f"{APP}/reset-password?token=sample",
            footnote="This link expires in 30 minutes. If you did not request this, you can ignore this email.",
        ),
        "account.password_changed": _email(
            "Your password was changed",
            "Your Chmaba password was just changed.",
            '<p style="margin:0 0 4px 0;">Hi Sokha, your Chmaba password was just changed.</p>'
            + table(["", ""], [["Changed", "21 Oct 2026, 10:42 UTC"]], aligns=["left", "right"], show_header=False)
            + '<p style="margin:18px 0 0 0;">If this was you, no action is needed. If you did not change it, reset your password and contact support right away.</p>',
            "Security",
        ),
        "account.new_signin": _email(
            "New sign-in to your account",
            "A new device signed in to your Chmaba account.",
            '<p style="margin:0 0 4px 0;">Hi Sokha, your Chmaba account was just signed in to from a new device.</p>'
            + table(
                ["", ""],
                [["When", "21 Oct 2026, 10:42 UTC"], ["Device", "Chrome on Windows"], ["IP address", "203.0.113.24"]],
                aligns=["left", "right"],
                show_header=False,
            )
            + '<p style="margin:18px 0 0 0;">If this was you, no action is needed. If it was not, change your password and contact support right away.</p>',
            "Security",
        ),
        "account.invitation": _email(
            "You are invited to Chmaba",
            f"Join {COMPANY} on Chmaba.",
            f'<p style="margin:0 0 4px 0;">You were invited to join <strong>{COMPANY}</strong> on Chmaba.</p>'
            f'<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br /><a href="{APP}/accept-invitation?token=sample" style="color:#6957f5;">{APP}/accept-invitation?token=sample</a></p>',
            "Invitation",
            cta_label="Accept invitation",
            cta_href=f"{APP}/accept-invitation?token=sample",
            footnote="This invitation expires in 7 days. If you were not expecting it, you can ignore this email.",
        ),
        "account.shopper_signin_code": (
            "<p>Your sign-in code is <strong>731 204</strong>. It expires in 15 minutes.</p>"
        ),
        # -- Onboarding ------------------------------------------------
        "onboarding.welcome": _email(
            "Welcome to Chmaba",
            "Your Chmaba account is confirmed. Set up your store to start selling.",
            _paragraphs(
                "Welcome to Chmaba, Sokha! Your account is confirmed. Set up your store in about two minutes and start selling.",
                "Once it&rsquo;s ready you can add your first product and take a sale &mdash; cash or KHQR.",
            )
            + f'<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br /><a href="{APP}/sokha/setup/company" style="color:#6957f5;">{APP}/sokha/setup/company</a></p>',
            "Get started",
            cta_label="Set up your store",
            cta_href=f"{APP}/sokha/setup/company",
            footnote="If the link asks you to sign in first, sign in and you will be taken straight to setup.",
        ),
        "onboarding.store_ready": _email(
            "Your Chmaba store is ready",
            f"{STORE} is ready. Add your first product to start selling.",
            _paragraphs(
                f"Hi Sokha, your store <strong>{STORE}</strong> is ready on Chmaba.",
                "The next step is your first product: add a name and a price and you can ring up a sale right away. We also added a few sample items so you can try the register immediately &mdash; replace them with your own catalogue when you are ready.",
            )
            + f'<p style="margin:16px 0 0 0;font-size:13px;color:#92939d;">Or paste this link into your browser:<br /><a href="{APP}/sokha/catalog" style="color:#6957f5;">{APP}/sokha/catalog</a></p>',
            "Your store",
            cta_label="Add your first product",
            cta_href=f"{APP}/sokha/catalog",
            footnote="Tip: replace the sample items with your own catalogue when you are ready.",
        ),
        "onboarding.drip": draft,
        # -- Sales and receipts ---------------------------------------
        "sales.sale_alert": _email(
            "New sale",
            f"$9.99 · {ORDER} at {STORE}",
            f'<p style="margin:0 0 15px 0;">A new sale was completed at <strong>{STORE}</strong>.</p>'
            + _order_facts()
            + _item_table()
            + totals_table(_TOTALS)
            + '<p style="margin:20px 0 6px 0;font-weight:700;color:#202128;">Paid by</p>'
            + table(["Method", "Amount"], [["Cash", "$9.99"]], aligns=["left", "right"]),
            "Sale",
        ),
        "sales.sales_today": _email(
            "Sales today",
            "12 orders · $186.40 at Sokha Mart",
            f'<p style="margin:0 0 4px 0;">Sales for <strong>{STORE}</strong> on Wednesday, 21 October 2026.</p>'
            + table(["Orders", "Gross sales"], [["12", "$186.40"]], aligns=["center", "center"])
            + table(
                ["Order", "Time", "Total"],
                [[ORDER, "10:42", "$9.99"], ["ORD-1043", "11:15", "$24.50"], ["ORD-1044", "12:03", "$6.75"]],
                aligns=["left", "center", "right"],
            ),
            "Sales",
        ),
        "sales.receipt": _email(
            f"Receipt {ORDER}",
            f"Thank you for shopping at {STORE}.",
            f'<p style="margin:0 0 15px 0;"><strong>{COMPANY}</strong><br />{STORE}<br /><span style="color:#92939d;">St. 271, Phnom Penh</span></p>'
            + table(["", ""], [["Receipt", ORDER], ["Date", "2026-10-21 10:42"], ["Customer", CUSTOMER]], aligns=["left", "right"], show_header=False)
            + _item_table()
            + totals_table(_TOTALS)
            + '<p style="margin:20px 0 6px 0;font-weight:700;color:#202128;">Paid by</p>'
            + table(["Method", "Amount"], [["Cash", "$10.00 (USD)"]], aligns=["left", "right"])
            + totals_table([("Change", "$0.01")]),
            "Receipt",
            footnote="Thank you for shopping with us!",
        ),
        "sales.deposit_receipt": _email(
            "Deposit receipt ORD-1042",
            f"Thank you for shopping at {STORE}.",
            f'<p style="margin:0 0 15px 0;"><strong>{COMPANY}</strong><br />{STORE}</p>'
            + table(
                ["", ""],
                [["Receipt", ORDER], ["Date", "2026-10-21 10:42"], ["Customer", CUSTOMER], ["Pickup", "2026-10-21 16:00"]],
                aligns=["left", "right"],
                show_header=False,
            )
            + _item_table()
            + totals_table(_TOTALS)
            + totals_table([("Deposit paid", "$3.00"), ("Balance due", "$6.99")]),
            "Deposit receipt",
            footnote="Thank you for shopping with us!",
        ),
        "sales.refund_confirmation": _email(
            "Refund processed",
            f"$9.99 refunded for {ORDER}",
            f'<p style="margin:0 0 4px 0;">We processed a refund for your order at <strong>{COMPANY}</strong>.</p>'
            + table(["Order", "Refund", "Method"], [[ORDER, "$9.99", "Cash"]], aligns=["left", "right", "left"])
            + '<p style="margin:18px 0 0 0;">Depending on your bank or card issuer, it may take a few business days to appear.</p>',
            "Receipt",
            footnote="Thank you for shopping with us!",
        ),
        "sales.online_order_received": _email(
            "We have your order",
            f"2 item(s) · $9.99 at {STORE}",
            f'<p style="margin:0 0 4px 0;">Hi {CUSTOMER}, we have your order at <strong>{STORE}</strong>.</p>'
            + table(["Item", "Qty", "Amount"], [["Iced coffee", "2", "$7.00"], ["Croissant", "1", "$2.25"]], aligns=["left", "right", "right"])
            + totals_table([("Total", "$9.25")])
            + '<p style="margin:18px 0 0 0;">Please pay at the counter. We will have it ready shortly.</p>'
            + f'<p style="margin:18px 0 0 0;"><a href="{APP}/order/sample" style="color:#6957f5;font-weight:700;">Follow your order</a></p>',
            "Order",
        ),
        "sales.online_order_closed": _email(
            "Order closed",
            f"Your unpaid order at {STORE} has been closed",
            f'<p style="margin:0 0 4px 0;">Hi {CUSTOMER}, we did not receive the payment for your order at <strong>{STORE}</strong>, so it has been closed and the items are no longer held for you.</p>'
            '<p style="margin:12px 0 0 0;">Nothing has been charged. You are welcome to order again, and we will have it ready as soon as you do.</p>',
            "Order",
        ),
        "sales.service_complete": _email(
            "Your service is complete",
            f"Blender service is complete at {STORE}.",
            f'<p style="margin:0 0 4px 0;">Hi {CUSTOMER}, the service for your item at <strong>{STORE}</strong> is complete.</p>'
            + table(
                ["", ""],
                [["Item", "Blender"], ["Serial", "SN-88213"], ["Service", "Repair"], ["Summary", "Replaced motor coupling and tested."]],
                aligns=["left", "right"],
                show_header=False,
            )
            + '<p style="margin:18px 0 0 0;">Please contact the store if you have any questions.</p>',
            "Service",
        ),
        # -- Store operations -----------------------------------------
        "operations.daily_summary": _email(
            "Daily summary",
            f"12 orders · $186.40 at {STORE}",
            f'<p style="margin:0 0 4px 0;">Here is how <strong>{STORE}</strong> performed on Wednesday, 21 October 2026.</p>'
            + table(["Orders", "Gross sales", "Refunds"], [["12", "$186.40", "$9.99"]], aligns=["center", "center", "center"]),
            "Daily summary",
        ),
        "operations.weekly_summary": _email(
            "Weekly summary",
            f"86 orders · $1,284.10 at {STORE}",
            f'<p style="margin:0 0 4px 0;">Sales for <strong>{STORE}</strong> from 15 Oct to 21 Oct 2026.</p>'
            + table(["Orders", "Gross sales", "Refunds"], [["86", "$1,284.10", "$24.00"]], aligns=["center", "center", "center"])
            + table(
                ["Day", "Orders", "Sales"],
                [["Mon 15 Oct", "11", "$162.00"], ["Tue 16 Oct", "14", "$201.50"], ["Wed 17 Oct", "9", "$141.20"]],
                aligns=["left", "center", "right"],
            ),
            "Sales",
        ),
        "operations.monthly_summary": _email(
            "Monthly summary",
            f"342 orders · $5,120.75 at {STORE}",
            f'<p style="margin:0 0 4px 0;">Sales for <strong>{STORE}</strong> in September 2026.</p>'
            + table(["Orders", "Gross sales", "Refunds"], [["342", "$5,120.75", "$86.00"]], aligns=["center", "center", "center"])
            + table(
                ["Week of", "Orders", "Sales"],
                [["01 Sep", "78", "$1,180.00"], ["08 Sep", "84", "$1,240.50"], ["15 Sep", "91", "$1,370.25"]],
                aligns=["left", "center", "right"],
            ),
            "Sales",
        ),
        "operations.low_stock": _email(
            "Low stock alert",
            "3 items need restocking at Sokha Mart.",
            f'<p style="margin:0 0 4px 0;">3 items at <strong>{STORE}</strong> are at or below the reorder point. 1 is already out of stock.</p>'
            + table(
                ["Product", "On hand", "Reorder at"],
                [["Iced coffee beans", "<strong style=\"color:#b45309;\">0</strong>", "5"], ["Croissant", "2", "6"], ["Oat milk", "1", "4"]],
                aligns=["left", "right", "right"],
            ),
            "Inventory",
            footnote="Update your reorder points or receive stock so these items do not sell out.",
        ),
        "operations.operations_digest": _email(
            "Operations summary",
            "4 item(s) at Sokha Mart.",
            f'<p style="margin:0 0 4px 0;">4 item(s) need your attention at <strong>{STORE}</strong>.</p>'
            + table(
                ["Type", "Item"],
                [
                    ["Approval", "Discount 15% on ORD-1042<br /><span style=\"color:#92939d;\">Requested by Dara</span>"],
                    ["Refund review", "Refund $9.99 on ORD-1038"],
                    ["Stock transfer", "12 units to Main Counter"],
                ],
                aligns=["left", "left"],
            ),
            "Ops",
            footnote="Turn this summary off in Settings → Notifications.",
        ),
        "operations.warranty_expiry": _email(
            "Warranties expiring soon",
            "2 warranty/warranties expiring at Sokha Mart.",
            f'<p style="margin:0 0 4px 0;">2 customer warranty/warranties at <strong>{STORE}</strong> expire within 30 days.</p>'
            + table(
                ["Product", "Serial", "Ends", "Left"],
                [["Blender", "SN-88213", "02 Nov 2026", "12d"], ["Kettle", "SN-77120", "08 Nov 2026", "18d"]],
                aligns=["left", "left", "left", "right"],
            )
            + '<p style="margin:18px 0 0 0;">Reach out before they lapse if a service or renewal is expected.</p>',
            "Warranty",
        ),
        "operations.refund_recorded": _email(
            "Refund recorded",
            "$9.99 refunded at Sokha Mart.",
            f'<p style="margin:0 0 4px 0;">A refund was recorded at <strong>{STORE}</strong>.</p>'
            + table(["Order", "Amount", "Method", "Recorded by"], [[ORDER, "$9.99", "Cash", "Sokha Chan"]], aligns=["left", "right", "left", "left"]),
            "Refund",
        ),
        "operations.online_order": _email(
            "New online order",
            f"2 item(s) · $9.25 at {STORE}",
            f'<p style="margin:0 0 4px 0;">A new online order arrived at <strong>{STORE}</strong>.</p>'
            + table(["Item", "Qty", "Amount"], [["Iced coffee", "2", "$7.00"], ["Croissant", "1", "$2.25"]], aligns=["left", "right", "right"])
            + totals_table([("Total", "$9.25")])
            + '<p style="margin:18px 0 0 0;">Confirm it on the Kitchen or Floor board and settle as usual.</p>',
            "Online order",
        ),
        "operations.shift_closed": _email(
            "Shift closed",
            f"18 order(s) · $246.80 at {STORE}",
            f'<p style="margin:0 0 4px 0;">A shift at <strong>{STORE}</strong> has been closed.</p>'
            + table(
                ["", ""],
                [
                    ["Cashier", "Dara"],
                    ["Opened", "2026-10-21 08:00"],
                    ["Closed", "2026-10-21 17:30"],
                    ["Orders", "18"],
                    ["Sales", "$246.80"],
                    ["Expected cash", "$180.00"],
                    ["Counted cash", "$179.50"],
                    ["Difference", "-$0.50"],
                ],
                aligns=["left", "right"],
                show_header=False,
            ),
            "Shift",
        ),
        "operations.shift_still_open": _email(
            "Shift still open",
            f"A shift at {STORE} has been open for over 12 hours.",
            f'<p style="margin:0 0 4px 0;">A shift at <strong>{STORE}</strong> has been open for more than 12 hours. It may need closing.</p>'
            + table(["Opened", "Status"], [["2026-10-21 08:00", "Still open"]], aligns=["left", "right"]),
            "Shift",
        ),
        "operations.team_activity": _email(
            "New team member",
            "Dara joined Sokha Mart as cashier.",
            '<p style="margin:0;">Dara joined Sokha Mart as cashier.</p>',
            "Team",
        ),
        "operations.chat_waiting": _email(
            "Dara is waiting for a reply",
            "Do you have this in a large?",
            f'<p style="margin:0 0 12px 0;">A message from <strong>{CUSTOMER}</strong> at {STORE} has been waiting for a reply.</p>'
            '<p style="margin:0 0 12px 0;color:#6b6c76;">&ldquo;Do you have this in a large?&rdquo;</p>',
            "Chat",
            cta_label="Open the inbox",
            cta_href=f"{APP}/inbox",
        ),
        "operations.chat_reply": _email(
            f"{STORE} replied",
            "Yes, we have large in stock.",
            f'<p style="margin:0 0 12px 0;">{STORE} replied to your message.</p>'
            '<p style="margin:0 0 12px 0;color:#6b6c76;">&ldquo;Yes, we have large in stock.&rdquo;</p>',
            "Chat",
            cta_label="Open the conversation",
            cta_href=f"{APP}/sokha-retail/sokha-mart",
        ),
        # -- Billing ---------------------------------------------------
        "billing.payment_received": _email(
            "Payment received",
            "$4.99 · Pro",
            '<p style="margin:0 0 4px 0;">We received your payment. Your <strong>Pro</strong> plan is active through 21 Nov 2026.</p>'
            + table(
                ["Receipt", "Plan", "Amount", "Paid", "Valid until"],
                [["RCP-90211", "Pro", "$4.99", "21 Oct 2026", "21 Nov 2026"]],
                aligns=["left", "left", "right", "left", "left"],
            )
            + '<p style="margin:18px 0 0 0;">Find this and past receipts under Billing &amp; plans in your workspace.</p>',
            "Billing",
        ),
        "billing.payment_failed": _email(
            "Payment did not go through",
            "Retry your Pro payment.",
            '<p style="margin:0 0 4px 0;">Your payment for the <strong>Pro</strong> plan did not go through. Your workspace keeps working until your current period ends.</p>'
            + table(["Plan", "Amount", "Status"], [["Pro", "$4.99", "Failed"]], aligns=["left", "right", "left"])
            + '<p style="margin:18px 0 0 0;">Open Billing &amp; plans in your workspace to try the payment again.</p>',
            "Billing",
        ),
        "billing.renewal_reminder": _email(
            "Renew your Pro plan - $4.99 monthly",
            "Your Pro plan ends on 2026-11-04.",
            _paragraphs(
                "Your Pro plan ends on 2026-11-04.",
                "Renew Pro for $4.99 (monthly) to keep your workspace running without interruption.",
            )
            + table(["", ""], [["Plan", "Pro"], ["Renewal", "$4.99 / monthly"], ["Period ends", "2026-11-04"]], aligns=["left", "right"], show_header=False),
            "Billing",
            cta_label="Go to Billing & plans",
            cta_href=f"{APP}/sokha/billing?renew=pro&cycle=monthly&pay=1",
            footnote=f'Billing &amp; plans: <a href="{APP}/sokha/billing" style="color:#6957f5;">{APP}/sokha/billing</a>',
        ),
        "billing.plan_expired": _email(
            "Your Pro plan has expired",
            "Your paid plan has expired. Your workspace is on the Free plan.",
            _paragraphs(
                "Your workspace is now on the Free plan.",
                "2 store(s) and 3 team member(s) are paused. Your data is safe &mdash; upgrade to restore them.",
            ),
            "Billing",
            cta_label="Upgrade your plan",
            cta_href=f"{APP}/sokha/billing",
        ),
        "billing.quota_warning": _email(
            "Approaching your plan limits",
            "Your Pro plan is nearing its limits.",
            '<p style="margin:0 0 4px 0;">Your workspace is getting close to its <strong>Pro</strong> plan limits.</p>'
            + table(
                ["Resource", "Used", "Limit", "Status"],
                [["Stores", "5", "5", "At limit"], ["Team members", "8", "10", "80% used"]],
                aligns=["left", "right", "right", "left"],
            )
            + '<p style="margin:18px 0 0 0;">Upgrade in Billing &amp; plans to add more, or remove what you no longer use.</p>',
            "Billing",
        ),
        # -- Support ---------------------------------------------------
        "support.request_received": _email(
            "We received your support request",
            "Support request SUP-8F31A2 received.",
            '<p style="margin:0 0 4px 0;">Thanks for contacting Chmaba support. We have your request and our team has been notified.</p>'
            + table(["", ""], [["Reference", "SUP-8F31A2"], ["Topic", "Billing"]], aligns=["left", "right"], show_header=False)
            + '<p style="margin:16px 0 0 0;"><strong>Your message</strong></p>'
            '<p style="margin:6px 0 0 0;">I upgraded but my receipts still show the Free plan.</p>'
            + '<p style="margin:18px 0 0 0;">Our team will follow up by email. You can keep using the in-app help and assistant in the meantime.</p>',
            "Support",
        ),
        "support.status_changed": _email(
            "Your support request SUP-8F31A2 is resolved",
            "Your support request has been resolved.",
            '<p style="margin:0 0 4px 0;">Your support request has been resolved.</p>'
            + table(["", ""], [["Reference", "SUP-8F31A2"]], aligns=["left", "right"], show_header=False)
            + '<p style="margin:16px 0 0 0;"><strong>Your question</strong></p>'
            '<p style="margin:6px 0 0 0;">I upgraded but my receipts still show the Free plan.</p>'
            + '<p style="margin:16px 0 0 0;"><strong>Note from our team</strong></p>'
            '<p style="margin:6px 0 0 0;">We refreshed your plan and receipts now show Pro.</p>'
            + '<p style="margin:18px 0 0 0;">The in-app help and assistant are always available.</p>',
            "Support",
        ),
        "support.reply": _email(
            "New reply on SUP-8F31A2",
            "Support replied to your request SUP-8F31A2.",
            '<p style="margin:0 0 4px 0;">Our team replied to your support request.</p>'
            + table(["", ""], [["Reference", "SUP-8F31A2"]], aligns=["left", "right"], show_header=False)
            + '<div style="margin:16px 0 0 0;"><p>We refreshed your plan &mdash; could you check the receipt on your next sale?</p></div>'
            + '<p style="margin:18px 0 0 0;">You can reply from the Help page under Your support requests.</p>',
            "Support",
        ),
        # -- Marketing -------------------------------------------------
        "marketing.manual_campaign": marketing_email(
            heading="Ready when you are",
            preview="Your Chmaba store is a couple of minutes away.",
            paragraphs=(
                "Hi Sokha,",
                "Your Chmaba account is ready. Set up your store and start taking sales today.",
            ),
            cta_label="Open Chmaba",
            cta_href=APP,
        ),
        # -- Internal --------------------------------------------------
        "internal.support_merchant_reply": _email(
            "Merchant reply on SUP-8F31A2",
            "Reply on support ticket SUP-8F31A2.",
            '<p style="margin:0 0 4px 0;">A merchant replied on a support ticket.</p>'
            + table(["", ""], [["From", "Sokha Chan"], ["Company", COMPANY]], aligns=["left", "right"], show_header=False)
            + '<p style="margin:16px 0 0 0;"><strong>Question</strong></p>'
            '<p style="margin:6px 0 0 0;">I upgraded but my receipts still show the Free plan.</p>'
            + '<p style="margin:16px 0 0 0;"><strong>Reply</strong></p>'
            '<p style="margin:6px 0 0 0;">It is still showing Free on today&rsquo;s receipt.</p>'
            + '<p style="margin:18px 0 0 0;">Open the admin panel to answer the merchant.</p>',
            "Support",
        ),
        "internal.mail_failure_alert": _email(
            "Mail delivery failures",
            "2 email(s) failed to send.",
            '<p style="margin:0 0 4px 0;">2 queued email(s) exhausted their retries and will not be sent.</p>'
            + table(
                ["Recipient", "Source", "Error"],
                [["dara@example.com", "receipt", "Resend rejected the message (422)"], ["sokha@example.com", "drip", "Delivery failed"]],
                aligns=["left", "left", "left"],
            )
            + '<p style="margin:18px 0 0 0;">Check the mail provider settings and the affected recipients.</p>',
            "Ops",
        ),
        "internal.test_email": _email(
            "Chmaba test email",
            "Your mail provider is configured correctly.",
            '<p style="margin:0 0 4px 0;">This is a test message from Chmaba.</p>'
            '<p style="margin:0;">If you can read it, the mail provider is configured correctly.</p>',
            "Test",
        ),
    }


_PREVIEWS: Final[dict[str, str]] = _subjects_and_bodies()


def preview_html(key: str) -> str | None:
    """The sample rendering for one catalog entry, or ``None`` if unknown."""
    return _PREVIEWS.get(key)


def preview_keys() -> set[str]:
    """Keys that have a preview. Used by the catalog test."""
    return set(_PREVIEWS)

# Email & notifications plan

Status: Living document — tracks what we send and the rollout backlog.
Owners: Engineering
Scope: inventory + design; implementation lands one PR at a time (see §6).

Related: `app/email.py` (account mail), `app/services/sale_emails.py`,
`app/services/store_notifications.py`, `app/services/reminders.py` (billing),
`app/services/mailing.py` (queue + marketing), `app/services/email_layout.py`
(shared branded template), `app/services/mail_events.py` (provider webhooks),
`apps/web/src/features/settings.jsx` (notification toggles),
`docs/capabilities-and-gaps.md`, `docs/billing-model.md`.

## 1. Goal

Every meaningful event should reach the right person by email, exactly once,
without mail ever blocking a sale, a refund, or a settings change. This document
records what we send today, the gaps, and the order to close them.

## 2. How email works today

- **Outbox, not inline (for store mail).** Sale alerts, receipts, store notes,
  onboarding drips and admin campaigns are written to `email_sends` (`EmailSend`)
  and delivered by the queue worker (`mailing.send_pending_emails`) with retries.
  A mail outage can never roll back a sale.
- **Transactional vs marketing.** `TRANSACTIONAL_SOURCES` (`sale_alert`,
  `receipt`, `store_note`) ignore the unsubscribe list and carry no
  `List-Unsubscribe` header; marketing rows get a one-click unsubscribe and are
  suppressed for unsubscribed addresses.
- **One branded template.** `email_layout.py` renders a shared dark-header shell
  (`marketing_email`, `transactional_email`) with `data_table`/`totals_table`
  helpers and a Khmer-capable font stack.
- **Preferences.** Merchant emails are opt-in per store under
  `Store.preferences.notifications` (Settings → Notifications): `sale_alert`
  (+ `sale_alert_frequency`), `customer_receipt`, `daily_summary`,
  `low_stock_alerts`, `refund_activity`, `shift_reminders`, `team_activity`.
  The customer receipt also needs the paid `email_receipts` capability and a
  customer email.
- **Idempotency.** `notification_state` (per store, per day / per open shift) and
  `billing_reminders` stop duplicates.
- **Inline account mail.** Verification, password reset, invitation, welcome,
  store-ready, support request/status/reply, and billing renewal reminders are
  sent **inline** (best-effort), not through the outbox. Fine for now; noted in
  §7.
- **Every message is branded.** Account, security, support and billing mail all
  render through the shared shell (`transactional_email`; the confirmation code
  uses `code_block`), so no user-facing email falls back to bare text or
  un-shelled HTML. Only the provider test message and the internal support-inbox
  notice are operator/internal and are branded for consistency too.
- **In-app only.** `notify_company_managers` (`v1.py`) writes `Notification`
  rows for several events that are **never emailed**: `stock_transfer`,
  `discount_review`, `refund_review`, `approval_request` (and `low_stock` /
  `refund`, which do have emails).

## 3. Current inventory (built)

| Email | Trigger | Recipient | Channel |
|---|---|---|---|
| Confirmation code | sign-up / resend | account | inline |
| Password reset | request | account | inline |
| Invitation | team invite | invitee | inline |
| Welcome | email confirmed | owner | inline |
| Store ready | workspace created | owner | inline |
| Onboarding drip (9) | stalled at signup/workspace/product/sale | owner | outbox |
| Support request received | contact form | merchant | inline |
| Support status change / reply | admin action | merchant | inline |
| Billing renewal reminder | −7 / −3 / −1 days, grace | owner | inline |
| Plan expired fallback | grace lapsed | owner | inline |
| Owner sale alert | each paid sale (or daily digest) | owner | outbox |
| Daily summary | end of day | owner | outbox |
| Low stock alert | daily when at/below reorder | owner | outbox |
| Refund activity | refund recorded | owner | outbox |
| Shift still open | shift open > 12h | owner | outbox |
| Team activity | team change | owner | outbox |
| Customer receipt | paid order + `email_receipts` | customer | outbox |

## 4. Gaps

Priorities: **P0** = revenue, security, or a shipped feature that is silent;
**P1** = operational polish; **P2** = end-customer engagement.

### P0

1. **New online / QR order** — **shipped** (#442): `queue_public_order_note`
   emails owners on `public_submit_order`, gated by the `online_order` toggle.
2. **Subscription payment receipt** — **shipped** (#444): `queue_billing_receipt_email`
   emails the receipt on a successful billing payment.
3. **Payment failed / action required** — **shipped** (#446):
   `queue_billing_failure_email` fires from the reconcile and webhook failure paths.
4. **Password changed** and **new sign-in / new device** — both **shipped**: the
   password-changed notice (#445) and the new-device sign-in alert (#449).
5. **Customer refund confirmation** — **shipped** (#448): the buyer receives a
   confirmation when an order is refunded.
6. **Online-order acknowledgement** — confirm a submitted public order to the
   customer. Needs a contact field on the public form (not stored today).

### P1

7. **Weekly / monthly sales report** — **shipped**: weekly (#455) and monthly
   (#461) summaries behind `weekly_report` / `monthly_report` toggles.
8. **Shift closed / Z-report** — **shipped** (#454): the closing summary is
   emailed, gated by a `shift_report` toggle.
9. **Approval, discount-review, refund-review, stock-transfer** — **shipped**
   (#458): folded into one daily `operations_digest` email rather than one
   message each.
10. **Warranty expiry / service-ticket updates** — **shipped** (#469): a weekly
    reminder for customer warranties expiring within 30 days; service-ticket
    updates remain open.
11. **Quota / limit warnings** — **shipped** (#467): owners are emailed at 90%
    and at their plan's store/member limits.
12. **Mail dead-letter alert** — **shipped** (#453): messages that exhaust their
    retries now alert platform admins.

### P2 (end-customer engagement)

13. Loyalty points earned / balance / expiring; birthday reward.
14. Back-in-stock notification (balances + public menu already exist).
15. Held / abandoned-order reminder.
16. Trade-in assessment result.

## 5. Principles for additions

1. **Queue, never block.** New merchant/customer mail goes through the
   `email_sends` outbox; the request path only enqueues.
2. **Every merchant email gets a toggle** under Settings → Notifications, read
   through `notification_prefs`, and is idempotent per event/day.
3. **Reuse the shared shell.** `transactional_email` for one-off notices;
   `data_table`/`totals_table` for line items.
4. **Transactional vs marketing is explicit.** Customer-facing marketing
   (loyalty, back-in-stock) must honour unsubscribe; receipts and security mail
   must not.
5. **Batch before you blast.** Prefer a digest for low-signal events over one
   email each.
6. **Bilingual-ready.** The web app already localised the setup journey (#435);
   copy should support en/km (and RTL-safe layout) for customer-facing mail.

## 6. Proposed rollout

Each item is its own PR, branch off `origin/main`, green CI as the gate.

| # | Branch | Scope | Status |
|---|---|---|---|
| 0 | `docs/email-notifications-plan` | this document | merged |
| 1 | `feat/online-order-alert` | P0-1: new online/QR order email + `online_order` toggle | shipped (#442) |
| 2 | `feat/billing-payment-emails` | P0-2: payment receipt | shipped (#444) |
| 3 | `feat/billing-payment-failed` | P0-3: payment-failed email | shipped (#446) |
| 4 | `feat/security-password-alert` | P0-4: password-changed notice | shipped (#445) |
| 5 | `feat/new-device-alert` | P0-4: new-device sign-in alert | shipped (#449) |
| 6 | `feat/customer-refund-email` | P0-5: refund confirmation to the buyer | shipped (#448) |
| 7 | `feat/online-order-ack` | P0-6: online-order acknowledgement to the customer | shipped (#462) |
| 8 | `feat/shift-close-report` | P1-8: shift-close summary | shipped (#454) |
| 9 | `feat/mail-dead-letter-alert` | P1-12: mail dead-letter ops alert | shipped (#453) |
| 10 | `feat/weekly-sales-report` / `feat/monthly-sales-report` | P1-7: weekly + monthly summaries | shipped (#455, #461) |
| 11 | `feat/operations-digest` | P1-9: reviews/transfer digest | shipped (#458) |
| 12 | `feat/quota-warnings` | P1-11: quota / limit warnings | shipped (#467) |
| 13 | `feat/warranty-expiry-reminders` | P1-10: warranty-expiry reminder | in review (#469) |
| 14 | `feat/loyalty-emails` | P2: points, birthday, back-in-stock | backlog |

Detailed, event-by-event copy and toggles are decided per PR.

## 7. Open decisions

1. **Inline account mail vs outbox.** Recommendation: move the highest-value
   account mail (billing reminders, invitations) to the outbox for retries, but
   keep it out of scope for the first email PRs.
2. **In-app-only events.** Recommendation: one batched "operations digest"
   rather than an email per `notify_company_managers` event, with per-store
   toggles.
3. **Customer contact capture.** Public ordering has no email/phone field;
   P0-6 depends on adding one (opt-in, with consent) — decide whether it ships
   with P0-1.
4. **Frequency caps.** Decide whether customer mail is capped per day/week to
   protect deliverability.
5. **Localisation default.** Send in the store's locale, or always English first?

## 8. Out of scope

- Push / web-push notifications and Telegram parity (`telegram_digest.py`).
- Inbound email (reply-by-email into support tickets); the support thread stays
  in-app.
- SMS.
- Redesigning the shared template (tracked separately).

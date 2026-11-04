# Free plan change notice

Status: ready to send. Write it only after running the impact report below, so
the message and any goodwill grant go to workspaces that actually used the
feature.

Context: the tier redesign (`docs/plans-redesign.md`) moved online ordering,
combos, serials/warranty and batches from "available to everyone" to Starter.
Paid workspaces were grandfathered for the period they had bought. Free
workspaces have no purchased period, so the change applies immediately.

## 1. Measure first

```bash
python chmabapos_api/scripts/plan_impact_report.py --details
```

It prints how many Free workspaces still use a newly paid capability, and names
them. If the count is zero, this notice does not need to go out at all.

## 2. Send

**Audience:** the Free workspaces the report names. Not the whole list.

**Subject:** Your Free plan has changed

**Body:**

> Hi {{first_name}},
>
> A short, direct note about your Chmaba Free plan.
>
> **What changed.** Online ordering, combos, serial and batch tracking now start
> on Starter. Everything else you had on Free is unchanged, and Starter adds
> refunds, shifts, supplier purchases, staff accounts and email receipts.
>
> **What did not change.** Your products, sales history, customers and settings
> are exactly as they were. Nothing was deleted. Online ordering is switched off,
> not removed - the moment you upgrade, your menu, your QR code and your tables
> are back as they were.
>
> **If you were using one of these.** Starter is $4.99 a month, or $47.90 for a
> year. Reply to this email and we will set your account up with a month on us
> while you decide.
>
> Thank you for running your shop on Chmaba.
>
> {{sender}}

**In-app banner (Free workspace, dismissible, shown once):**

> Online ordering, combos, serials and batches now start on Starter. Nothing you
> created was removed. See what changed ->

## 3. If a workspace needs a softer landing

Reply-driven, one call per account, no code:

```
POST /api/v1/admin/companies/<company_id>/subscription
{
  "action": "grant",
  "plan_code": "starter",
  "billing_cycle": "monthly",
  "reason": "free-tier transition"
}
```

Record the reason. These grants appear in the subscription history, so support
can see why an account is on Starter without a payment.

## 4. FAQ support will get

**"I paid for this."** If a prepaid period was in force, nothing was taken away
until it ends. Ask for the company name and check the subscription view before
replying.

**"My online menu disappeared."** The storefront menu itself is still public; only
submitting an order requires Starter. The setting is off, not deleted.

**"My data?"** Untouched. Plan changes never delete products, orders, customers or
store settings.

**"Can I have it back for free?"** No. Point at the Starter price and offer the
transition month if they were actively using the feature.

## 5. Wording to avoid

- Do not call it a "free trial ending" - it was not a trial.
- Do not imply the merchant did something wrong.
- Do not promise a permanent exception you cannot keep; a dated grant is fine, an
  open-ended one is not.

# Plans redesign

Status: **Phase 1 (quota model + one capability catalog) shipped.** Phase 2 (the
tier matrix below) is agreed but not yet applied to the plan rows or the
endpoint gates. This document is the design of record for both.

Related: `docs/billing-model.md` (prepaid periods, entitlement resolver),
`docs/capabilities-and-gaps.md` (what the product ships),
`chmabapos_api/app/features.py` (`FEATURE_CATALOG`),
`chmabapos_api/scripts/seed.py` (default plan rows).

## 1. Why this redesign

The audit found six problems with the plan as shipped:

1. **Three capabilities were never enforced.** `barcode_scanning`,
   `receipt_customization` and `priority_support` had no backend gate at all, so
   they were permanent marketing bullets rather than entitlements.
2. **Pro had no unique feature.** Starter was defined as "every feature except
   priority support", so a Pro card advertised exactly the Starter card plus a
   ticket flag and larger numbers.
3. **The Free tier was incoherent.** It included loyalty points and
   multi-currency but not refunds or shifts, so a solo merchant could run a
   loyalty programme but could not refund a customer.
4. **Quotas did not mean what they said.** `transaction_limit` was enforced as a
   single period total, so an annual buyer received one month's allowance for
   twelve months of service. Free counted from its subscription start with no
   reset, making its 3,000 a lifetime cap.
5. **The catalog lived in four places** (`features.py`, the admin plan editor,
   the web client, and the vertical capability packs), so adding a gate
   silently dropped it from the editor.
6. **Most shipped product surface had no plan key at all**: online ordering,
   the delivery board, combos, serials/warranty/trade-in, batches, shopper chat,
   approvals and consolidated reports were free for every account.

## 2. Model decisions

These are settled and apply regardless of which tier numbers are chosen.

### 2.1 `transaction_limit` is a monthly rate

`Plan.transaction_limit` means **sales per month**. The allowance for one
prepaid period is that rate times the months the cycle covers
(`services/pricing.py::cycle_months`), so an annual buyer gets twelve months of
quota. Customer-facing bullets say "per month" on every plan.

### 2.2 Free resets monthly

Free has no prepaid period, so its quota is a rolling calendar month ending at
the first of the next month. The window starts no earlier than the free
subscription, so the opening month counts only sales that could exist. This
replaces the previous open-ended window, which bricked a workspace at its limit.

### 2.3 Capability keys are permanent

Keys are persisted three times: on `Plan.capabilities`, inside
`Subscription.plan_terms` snapshots, and in every client. **Renaming a key
silently strips a paid feature from every in-force subscriber**, because their
snapshot still carries the old name. Labels may change; keys may not, except by
a migration that also rewrites `plan_terms`.

That is why `roles_permissions` and `table_management` keep their names even
though their labels are now "Staff accounts and roles" and
"Restaurant mode (tables, kitchen, delivery)".

### 2.4 One catalog

`GET /plans/features` returns `FEATURE_CATALOG` (key + label). The admin plan
editor renders from that response, so a new gate cannot be missing from the
editor. Clients keep only a display list; they never decide what the API allows.

### 2.5 Vertical packs are not entitlements

`app/verticals.py` capability packs (`barcode`, `variants`, `modifiers`,
`tables`, `delivery`, `serials`, `batches`) decide what the UI surfaces first
for a business type. They never gate the API. Plan capabilities gate the API.
`barcode_scanning` and `receipt_customization` are removed from the plan catalog
for this reason; barcode stays a pack, and receipt templates stay core.

## 3. Target tiers

### 3.1 Capabilities

| Capability | Free | Starter | Pro | Gate today |
|---|:--:|:--:|:--:|---|
| `inventory_management` | yes | yes | yes | yes |
| `held_orders` | yes | yes | yes | yes |
| `khqr_payments` | yes | yes | yes | yes |
| `multi_currency` | yes | yes | yes | yes |
| `refunds` | - | yes | yes | yes |
| `shift_management` | - | yes | yes | yes |
| `email_receipts` | - | yes | yes | yes |
| `purchasing` | - | yes | yes | yes |
| `advanced_reports` | - | yes | yes | yes |
| `roles_permissions` | - | yes | yes | yes |
| `table_management` | - | yes | yes | yes |
| `loyalty` | - | yes | yes | yes |
| `online_ordering` (new) | menu only | yes | yes | no |
| `delivery_dispatch` (new) | - | yes | yes | no |
| `combos` (new) | - | yes | yes | no |
| `serials_warranty` (new) | - | yes | yes | no |
| `batches_expiry` (new) | - | yes | yes | no |
| `consolidated_reports` (new) | - | - | yes | partly (inside `advanced_reports`) |
| `custom_roles` (new) | - | - | yes | partly (inside `roles_permissions`) |
| `priority_support` | - | - | yes | flag only |

Notes:

- **Free keeps a readable public menu** but not order submission. That keeps the
  storefront's discovery loop open while making ordering the paid step.
- **Offline mode is never paywalled.** It is a reliability guarantee.
- `consolidated_reports` is split out of `advanced_reports`; the multi-store
  report is a Pro concern. Existing Starter subscribers are grandfathered in the
  migration so a deploy does not take away something they bought.
- `custom_roles` is split out of `roles_permissions`: Starter can assign preset
  roles and store scope, Pro can build custom roles.
- `audit_log` was considered and **dropped**: the workspace "Activity" nav item
  has no view or endpoint behind it, so there is nothing to sell. Build the
  surface first.

### 3.2 Limits and price

| | Free | Starter | Pro |
|---|---|---|---|
| Stores | 1 | 2 | 10 |
| Users (including owner) | 1 | 8 | 40 |
| Sales per month | 300 | 5,000 | 50,000 |
| Price / month | $0 | $4.99 | $14.99 |
| Annual (20% off) | - | $47.90 | $143.90 |
| Support | knowledge base | email, 2 business days | priority, same day |

The previous $0.99 / $4.99 ladder worked out to roughly $0.00007 per
transaction and could not cover support or payment costs. Repricing is safe
because checkout freezes `plan_terms`: existing subscribers keep the terms they
paid for, and the new price applies to new checkouts and renewals only.

## 4. Recommendation logic

`recommend_plan` currently matches only store and member bands, which
under-recommends once Starter covers two stores: the `"2-5"` band resolves to
five stores, so a two-store merchant is pushed to Pro. Phase 2 changes:

- split the store bands into `1`, `2`, `3-5`, `6-10`, `11+`;
- add a sales-per-month band (the dimension that now differs between tiers);
- ask whether the merchant sells online, since `online_ordering` is the most
  common reason to leave Free.

## 5. Rollout

| Phase | Scope | State |
|---|---|---|
| 1 | monthly quota rate, Free monthly window, `GET /plans/features`, admin editor reads the catalog | shipped |
| 2 | catalog keys, endpoint gates, `DEFAULT_FEATURES_BY_PLAN`, plan-row migration, seed, clients, docs | pending |
| 3 | upgrade prompts instead of 403s, pricing comparison table, admin editor grouped by tier | pending |

Phase 2 ships as **one migration** chained to the single Alembic head. It edits
the three built-in plan rows and grandfathers in-force subscriptions by adding
the newly split keys (`consolidated_reports`, `custom_roles`) and the newly
gated features to their `plan_terms` snapshots, so no paying workspace loses
access mid-period. Free follows the live plan row by design, so tightening it
does take effect at deploy; that is the intent of the redesign and should be
communicated before release.

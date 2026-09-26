# Billing enforcement fixes — detailed action plan

Status: **in progress** (Option A confirmed for paused stores, §0.1).
Progress: items 1, 3, 2, 4, 5a and 5b landed; item 6 and item 7 pending.
Base revision: `main` @ `4420936`.

This document turns six agreed billing/enforcement gaps into shippable,
reviewable work. Each item below is a self-contained deliverable with a branch,
a PR, a task checklist, tests, acceptance criteria and a rollback.

Two tracks:

- **Track A — Enforcement & policy (items 1–4):** make the plan gate correct and
  the policy explicit.
- **Track B — Payment reliability & support visibility (items 5–6):** make the
  payment path self-heal and give support the data they need.

| # | Deliverable | Track | Branch | Size |
| --- | --- | --- | --- | --- |
| 1 | Close the grace-window transaction loophole | A | `fix/billing-grace-quota` | S |
| 2 | Let merchants schedule any future plan change | A | `feat/billing-schedule-any-change` | M |
| 3 | Show the real "usable until" date including grace | A | `feat/billing-usable-until-grace` | S |
| 4 | Decide + document the open policy questions | A | `docs/billing-policy-decisions` | S |
| 5a | Fix env-vs-DB payment settings precedence | B | `fix/billing-settings-precedence` | S |
| 5b | Scheduled reconcile job so missed webhooks self-heal | B | `feat/billing-payment-reconcile-job` | M |
| 6 | Admin visibility for billing payments | B | `feat/admin-billing-payments` | M |
| 7* | Paused store readable in history/reports (§0.1 A) | A | `feat/paused-store-read-only` | M |

\* Item 7 becomes its own branch after item 4, per the confirmed decision.

**Explicitly out of scope:** making the payment provider swappable
(improvement-plan §3.2.1 / Phase 4 item 12). ChmabaPay stays the only provider;
this plan only corrects the documentation so it stops implying otherwise.

Line references are against the base revision and will be re-checked in each PR.

---

## 0. Decision log

These decisions gate items 1–6. They are recorded here and land in
`docs/billing-model.md` (Track A item 4) and `docs/deploy.md` /
`docs/chamabapay-golive.md` (Track B items 5–6).

### 0.1 Paused store semantics — **DECIDED: Option A**

When a store is force-paused (expiry/downgrade), it **cannot sell but stays
visible in history/reports**, with a clear "paused — upgrade to reactivate"
message.

- Writes / POS / store-scoped operational endpoints stay blocked for a paused
  store.
- Store-scoped **read** endpoints return "This store is paused — upgrade to
  reactivate" instead of the current generic
  `404 Store not found or not accessible` (`app/deps.py:80`).
- Company-wide reporting and exports continue to include paused-store data.

Rationale: matches the "Your data is safe" copy, avoids the perception that
history was deleted. Delivered as item 7 (`feat/paused-store-read-only`).

### 0.2 Six-month / annual periods — **DECIDED: calendar periods**

Periods are calendar-based (`app/services/pricing.py::period_end` already uses
calendar months with day clamping). Retire the residual fixed-day values.

- `semi_annual` = 6 calendar months; `annual` = 12 calendar months.
- Delete `pricing.cycle_days()` / the fixed `30/182/365` day entries from
  `CYCLE_META` (they now contradict `period_end`).
- Update `tests/test_billing_immutability.py:90-91`, which still asserts
  `cycle_days("monthly") == 30` / `cycle_days("annual") == 365`.
- Confirm the wording in Terms/Refund copy.

### 0.3 Transaction quota reset — **DECIDED: per prepaid period**

- A period's counting window is `[subscription.starts_at, grace_deadline)`.
- An early same-plan renewal stacks: the next period's window starts at the
  previous `ends_at` and gets its own fresh count when it becomes in force.
- A Free fallback starts a fresh window at fallback creation time.
- The limit is enforced at all times a plan is in force, **including grace**
  (item 1).

### 0.4 Grace — **DECIDED: 48h, full access, limits enforced**

- `BILLING_GRACE_HOURS` default `48` (`app/config.py:39`) stays.
- Full paid access during grace; transaction limits still count (item 1).
- The grace deadline is exposed to clients for display (item 3).

### 0.5 Payment provider — **DECIDED: ChmabaPay only, documented**

- No provider abstraction work. Update `docs/billing-improvement-plan.md` to
  state Phase 4 item 12 is intentionally deferred and ChmabaPay is the sole
  provider, so docs match code.

### 0.6 Payment settings precedence — **DECIDED: DB overrides env**

- `load_payment_settings` (`app/services/platform_config.py:26`) is the single
  source of truth: a stored `PlatformSetting` overrides the env default.
- Every call site must honor it; any `settings.chamabapay_*` read that sits
  *before* the DB lookup is a bug (item 5a).

---

## 1. Close the grace-window transaction loophole

### Objective
While a plan is in force — including the 48h grace window — a workspace can
never exceed its `transaction_limit`.

### Merchant impact
Today a merchant past `ends_at` but inside grace is not stopped, because the
counter only looks at sales before `ends_at`. They could take unlimited
transactions during grace. After this change the cap holds.

### Current behavior
`app/services/orders.py::ensure_transaction_available` counts paid orders where
`Order.created_at >= subscription.starts_at AND Order.created_at < subscription.ends_at`.
During grace `now > ends_at`, so new orders are excluded from the count and the
`>= plan.transaction_limit` check never trips.

### Target behavior
Count the effective window ending at the grace deadline:

```
lower = subscription.starts_at
upper = grace_deadline(subscription) or now   # ends_at + BILLING_GRACE_HOURS
count = paid orders with lower <= created_at < upper
if count >= plan.transaction_limit: 403
```

`grace_deadline` already exists in `app/billing.py:37`; import it into
`orders.py`. No schema changes.

### Task checklist
- [ ] `app/services/orders.py`: import `grace_deadline`; replace the
      `ends_at` upper bound with `grace_deadline(subscription)` (fallback to
      `utc_now()` when `None`).
- [ ] Keep the existing 403 body text so the frontend copy is unchanged.
- [ ] Add tests (new `tests/test_billing_quota.py`, or extend
      `tests/test_billing_immutability.py`).
- [ ] `docs/billing-model.md`: state that transaction limits continue to apply
      through the grace window.

### Tests
- [ ] **Regression:** subscription in grace, order count == limit → creating a
      sale returns 403. (This test fails before the fix.)
- [ ] Before `ends_at`, at limit → 403 (existing behavior preserved).
- [ ] Before `ends_at`, below limit → sale succeeds.
- [ ] After grace, with a Free fallback in force → Free limit applies.
- [ ] Stacked renewal: the second period's window starts at the old `ends_at`
      and counts fresh.

### Acceptance criteria
- No code path lets a workspace exceed `transaction_limit` while a paid plan is
  in force, grace included.
- Existing pre-expiry behavior is byte-for-byte unchanged.

### Rollback
Single-line query change; revert the PR.

### Risks / notes
- Optional, separate follow-up (not in this PR): the short window between grace
  end and the daily job leaves the workspace with no in-force subscription, so
  sales 403 with "An active plan is required." It fails closed (safe), but is
  ugly. Consider synthesizing Free in `load_entitlement` in a later change.

---

## 2. Let merchants schedule any future plan change

### Objective
A merchant can queue any *different* plan (upgrade, downgrade, or cancel to
Free) to take effect at their current period end. "Pay now" remains an instant
activation.

### Merchant impact
Today only strictly cheaper plans can be scheduled (`app/api/v1.py:1784`) and
the UI only offers "Schedule" for downgrades (`apps/web/src/features/team.jsx:135`).
A merchant on Starter cannot queue Pro for next period.

### Current behavior
- `PUT /billing/schedule` rejects `target.monthly_price >= ent.plan.monthly_price`
  with "This is not a downgrade; use Billing checkout to upgrade." (v1.py:1784)
- Scheduling stores `scheduled_plan_code` / `scheduled_store_ids` /
  `scheduled_member_ids`; the effective time is implicitly `ends_at` (no
  `scheduled_effective_at` column).
- `fulfill_billing_payment` (v1.py:2183) already starts a scheduled target at
  the boundary for **any** target, including a higher-priced one.
- `reminders.py` already references the scheduled target for any plan.

So the backend machinery already supports scheduled upgrades; only the
validation and the UI block them.

### Target behavior
- Schedule validation: current plan must be paid; target must exist and differ
  from the current plan; keep-lists must fit the target capacity. No price
  comparison.
- Same-plan target stays rejected ("This plan is already active — use renew").
- A scheduled change never charges today; if the renewal is not paid by the
  boundary, existing Free fallback applies.
- Paying early through checkout while a target is scheduled starts the target
  **at the boundary**, not immediately (already implemented at v1.py:2183 —
  add a test to lock it).

### Task checklist — API
- [ ] `app/api/v1.py::schedule_plan_change`: remove the `monthly_price >=`
      rejection; keep same-plan rejection and keep-list validation.
- [ ] Confirm the response/copy for a scheduled upgrade is sensible (no
      "downgrade" wording anywhere in the path).
- [ ] Ensure `create_billing_checkout`'s downgrade guard (v1.py:1837-1847)
      still behaves: paying a scheduled target is allowed and applies at the
      boundary.
- [ ] No migration (effective date remains `ends_at`).

### Task checklist — Web (`apps/web/src/features/team.jsx`)
- [ ] `canSchedule(plan)` (line 135): true for any non-current target while on a
      paid plan (drop the price comparison).
- [ ] Plan cards: for non-current paid plans show two actions — **Upgrade now**
      (checkout) and **Schedule for period end** (opens `PlanScheduleModal`).
      Today `upgradeCard` only checks out (lines 206, 233).
- [ ] Confirm the keep-list picker in `PlanScheduleModal` renders cleanly for an
      upgrade (nothing over capacity → picker hidden).
- [ ] Confirm modal copy ("…stays fully usable until {date}; the change applies
      then — nothing is charged today") reads correctly for upgrades.
- [ ] `onPaidActive` banner / scheduled badge already generic — verify.

### Tests (`tests/test_billing_schedule.py`)
- [ ] **Replace** `test_upgrade_not_allowed_via_schedule` with
      `test_schedule_upgrade_allowed`: PUT pro while on starter → 200 and
      `scheduled_plan_code == "pro"`.
- [ ] Paid scheduled upgrade: fulfill the Pro payment before `ends_at` → Pro
      starts at the old `ends_at`, Starter ends then, capacity expanded.
- [ ] Unpaid scheduled upgrade → expiry job falls the workspace to Free.
- [ ] Same-plan schedule still 400.
- [ ] Scheduled downgrade regression (existing tests) still green.

### Acceptance criteria
- Any plan→plan change is schedulable; a scheduled change charges nothing today
  and applies at period end.
- Unpaid scheduled change → existing Free fallback with audit trail.
- No regression to same-plan stacking or downgrade scheduling.

### Rollback
Reinstate the price guard and the UI branch; no data migration to undo.

### Risks
- UI: the two-action card must clearly separate "pay now" from "schedule".
  Keep "pay now" as the primary button to preserve the money-wins principle.
- Semantics: scheduling an upgrade means "renew into Pro at period end"; the
  reminder already tells the merchant to pay the Pro renewal then.

---

## 3. Show the real "usable until" date including grace

### Objective
No surface shows a bare past `ends_at` while the plan is still usable. The grace
deadline comes from the API; the browser never computes it.

### Merchant impact
A merchant in grace currently sees the old end date and may believe they are
already cut off.

### Current behavior
- `team.jsx:134,158,168` and `settings.jsx` ("Renews / ends") render
  `subscription.ends_at` directly.
- `reminders.py:81` computes the grace date itself.

### Target behavior
Add computed fields to `SubscriptionRead` (`app/schemas.py:209`), derived from
`settings.billing_grace_hours`:

| Field | Type | Meaning |
| --- | --- | --- |
| `grace_ends_at` | `datetime \| None` | `ends_at + grace` for a paid plan; `None` for Free/indefinite |
| `in_grace` | `bool` | `ends_at < now <= grace_ends_at` |

Implement as a Pydantic `computed_field` on the `from_attributes` schema
(`app/schemas.py:13`) so every endpoint returning `SubscriptionRead` gains it
with no per-endpoint work.

### Task checklist — API
- [ ] `app/schemas.py`: add `grace_ends_at` (computed) and `in_grace` (computed)
      to `SubscriptionRead`, using `app.billing.grace_deadline` /
      `settings.billing_grace_hours`.
- [ ] Verify `SubscriptionRead` is used by `GET /billing/subscription`
      (v1.py:1766), workspace setup, schedule responses, and cancel responses
      so all get the fields consistently.
- [ ] Reuse the same helper in `reminders.py` if convenient (no behavior change).

### Task checklist — Web
- [ ] `team.jsx`: when `in_grace`, show "Usable until {grace_ends_at} — renew to
      avoid pausing N stores/team" instead of "Plan ends {past date}".
- [ ] `team.jsx` scheduled-change block (line 168): keep the scheduled effective
      date as `ends_at` (the change still applies at period end, not grace end).
- [ ] `team.jsx` capacity-warning banner (line 174): use the grace date when
      in grace.
- [ ] `settings.jsx`: "Renews / ends" shows `ends_at`; add a secondary "usable
      until {grace_ends_at}" line when `in_grace`.

### Tests
- [ ] `GET /billing/subscription` inside grace → `in_grace == True` and
      `grace_ends_at == ends_at + 48h`.
- [ ] Outside grace → `in_grace == False`.
- [ ] Free plan → `grace_ends_at is None`, `in_grace == False`.

### Acceptance criteria
- Every billing surface shows a future, correct "usable until" date whenever the
  plan is still usable.
- Grace remains fully server-derived.

### Rollback
Remove the computed fields and UI branches; additive and safe.

### Risks
- Display ambiguity between "period ends" (change date) and "usable until"
  (grace end). Mitigate with explicit copy in the scheduled block.

---

## 4. Decide + document the open policy questions

### Objective
Close the "Open questions" section in `docs/billing-improvement-plan.md` §7 and
record the decisions in `docs/billing-model.md`.

### Deliverables
- [ ] Add a **Decisions** section to `docs/billing-model.md` covering §0.1–0.6.
- [ ] In `docs/billing-improvement-plan.md`: mark §4.2 (generalized scheduled
      changes) as landed by item 2; note §7 items resolved; state Phase 4 item
      12 (provider abstraction) is intentionally deferred and ChmabaPay is the
      sole provider.
- [ ] `app/services/pricing.py`: delete `cycle_days()` and the fixed-day
      entries of `CYCLE_META` (calendar periods only); keep `CYCLE_META`'s
      months/discount/label.
- [ ] Update `tests/test_billing_immutability.py:90-91` to assert calendar
      behavior instead of fixed days.
- [ ] Terms/Refund wording review for calendar periods (§0.2).

### Notes
This item ships **after** items 1–3 so the docs describe what actually landed,
but its decisions are locked up front. The paused-store follow-up (§0.1 option A)
becomes item 7 after this.

---

## 5. Harden billing payments (Track B)

### Objective
A missed or dropped provider webhook must never leave a paying merchant
unactivated, and the payment settings a merchant is charged through must obey
the documented DB-overrides-env contract.

### Merchant / business impact
Plan fees are collected via ChmabaPay. If a `payment.completed` webhook is
dropped, the subscription stays `pending` even though money moved — the merchant
paid and is not activated. There is currently no reconcile path for plan-fee
payments (only order payments reconcile, and only when read). Separately, the
platform store that collects plan fees is resolved **env-first**, so an admin
setting in the admin panel can be silently ignored.

### 5a. Fix env-vs-DB payment settings precedence

**Current behavior (bug):** `app/api/v1.py::resolve_platform_store_id`
(line 457) reads:

```python
configured = settings.chamabapay_platform_store_id or (await load_payment_settings(db)).get("chamabapay_platform_store_id")
```

Env wins over DB — the inverse of `load_payment_settings`
(`app/services/platform_config.py:26`, "DB overrides, else env") and of the
admin settings UI.

**Target behavior:** DB setting wins; env is only the fallback. Route every
platform-settings read through `load_payment_settings`.

### Task checklist — 5a
- [ ] `app/api/v1.py::resolve_platform_store_id`: use
      `cfg = await load_payment_settings(db)` and read the key from `cfg`.
- [ ] Audit every `settings.chamabapay_*` read for the same inversion
      (`grep settings.chamabapay`): `active_payment_provider` (v1.py:440),
      webhook secret/mode (v1.py:2305-2307), mock endpoints (v1.py:2350).
      Any read that precedes the DB lookup must be reordered.
- [ ] Confirm `ChmabaPayClient.__init__` (`payments/chamabapay.py:26-29`)
      treats an explicitly-passed `None` correctly and does not reintroduce an
      env-first path.
- [ ] No migration (PlatformSetting already exists).

### 5b. Scheduled reconcile job (missed-webhook self-heal)

**Current behavior:** `reconcile_pending_order_payment` (v1.py:492) re-checks
open **order** payments on read only. `ChmabaPayClient.reconcile`
(`payments/chamabapay.py:117`) returns the authoritative status via
`GET /transactions/check-status/{id}`. **Billing** payments have no reconcile
path at all.

**Target behavior:** a scheduled, idempotent job re-checks stale open payments
against the provider and applies the same fulfillment the webhook would:

- For each open `BillingPayment` (status not terminal, `external_id` set,
  `fulfilled_at is null`, older than the QR TTL), call `provider.reconcile`.
  - `PAID` → `fulfill_billing_payment(external_id, reference_id, approved_at, db)`
    (already idempotent via `fulfilled_at`).
  - `FAILED` / `EXPIRED` → set the terminal status (never downgrade a `paid`).
- For each order with open payments → reuse `reconcile_pending_order_payment`.
- Safe to run often; one scheduler run self-heals within the window.

### Task checklist — 5b
- [ ] Add `run_reconcile_job(db)` in `app/services/billing_lifecycle.py` (or a
      new `app/services/payment_reconcile.py`), returning counts.
- [ ] Query BillingPayment with a small age filter (skip payments newer than
      ~3 min to respect QR TTL) and `status NOT IN terminal` and
      `external_id IS NOT NULL` and `fulfilled_at IS NULL`; cap the batch.
- [ ] Route through `load_payment_settings` (i.e. the 5a-corrected provider).
- [ ] Handle `PaymentProviderError` per row (log/skip, never abort the job).
- [ ] Wire into `scripts/run_billing_jobs.py` alongside expiry + reminders.
- [ ] Document the scheduler in `docs/deploy.md` / `docs/billing-model.md`
      Operations.
- [ ] Reuse for order payments (iterate open orders).

### Tests (`tests/` — new `test_billing_reconcile.py` or extend `test_payment_provider.py`)
- [ ] DB platform_store_id overrides env when both are set (5a).
- [ ] `PAID` reconcile on a pending BillingPayment activates the subscription
      exactly once and issues one receipt.
- [ ] Running the job twice does not double-extend or double-activate.
- [ ] `FAILED`/`EXPIRED` reconcile marks the payment terminal; a later `paid`
      webhook is still rejected by the frozen-terminal guard.
- [ ] Terminal/fulfilled rows are skipped.
- [ ] Provider error on one row does not stop the batch.

### Acceptance criteria
- A dropped plan-payment webhook self-heals within one scheduler run; the
  merchant is activated exactly once.
- The platform store used for plan fees is whatever the admin panel says (DB),
  with env only as fallback.

### Rollback
Additive job + a precedence fix; revert the PR(s). Precedence fix is safe to
revert but should not be — it aligns code with the documented contract.

### Risks
- Batch size / provider rate limits — cap and back off; skip already-terminal.
- `reconcile` currently returns only `{status, source}` in some paths; if
  `approved_at` is unavailable, use `now_utc()` (fulfillment already defaults).

---

## 6. Admin visibility for billing payments (Track B)

### Objective
Support can see plan-fee payment rows (pending/paid/failed) and the resolved
platform store, so a merchant "I paid but I'm not activated" ticket can be
answered without DB access.

### Current behavior
- Admin API has `GET /admin/subscriptions` (admin.py:303) and a refund endpoint
  (`POST /admin/billing-payments/{id}/refund`, admin.py:388), but **no list of
  `BillingPayment` rows**.
- `GET /admin/chamabapay-settings` (admin.py:257) shows the **configured**
  `platform_store_id`, not the auto-resolved internal store that actually
  collects plan fees (`resolve_platform_store_id`, v1.py:450).
- Admin UI is a single `apps/admin/src/App.jsx`.

### Target behavior
- A read-only admin list of billing payments with the fields support needs.
- The ChmabaPay settings pane distinguishes **configured** vs **resolved**
  platform store.

### Task checklist — API
- [ ] `GET /admin/billing-payments` (admin-only) with optional filters
      `status`, `company_id`, `limit` (reuse `validate_limit`), ordered
      `created_at desc`. Return: `id`, `company_id`, `company_name`,
      `subscription_id`, `plan_code`, `billing_cycle`, `amount`,
      `currency_code`, `provider`, `status`, `external_id`, `reference_id`,
      `created_at`, `approved_at`, `fulfilled_at`, `period_start`,
      `period_end`.
- [ ] Add `AdminBillingPaymentRead` to `app/schemas.py`.
- [ ] `resolve_platform_store_id` result exposed as `resolved_platform_store_id`
      on `ChmabaPaySettingsRead` (keep `platform_store_id` as the configured
      value). **Never** include the api_key or webhook secret — keep the
      existing mask/preview pattern.
- [ ] No audit on read (consistent with other list endpoints).

### Task checklist — Admin UI (`apps/admin/src/App.jsx`)
- [ ] Add a "Billing payments" nav item + table with a status filter and the
      company/plan/amount/status/fulfilled columns.
- [ ] Show resolved vs configured platform store on the ChmabaPay settings pane.
- [ ] `apps/admin/src/api.js`: add the client calls.

### Tests
- [ ] Non-admin gets 403; platform admin gets rows.
- [ ] Filters (`status`, `company_id`) narrow correctly; limit validated.
- [ ] Response omits `api_key`/`webhook_secret`.
- [ ] `resolved_platform_store_id` reflects `resolve_platform_store_id`
      (including the auto-detected/cached case).

### Acceptance criteria
- Support can find a merchant's plan payments and see whether they were
  fulfilled, and confirm which store collected the fee.
- No secret material is exposed by the new endpoints.

### Rollback
Additive read-only endpoints + UI; revert the PR.

### Risks
- PII/secret leakage — locked by tests and by reusing the existing mask helper.

---

## 7. Delivery plan

### Branch / PR map

| Order | Branch | PR title | Track |
| --- | --- | --- | --- |
| 0 | `docs/billing-enforcement-fixes-plan` | docs: billing enforcement fixes action plan | — |
| 1 | `fix/billing-grace-quota` | fix(billing): enforce transaction limit during grace | A |
| 2 | `feat/billing-usable-until-grace` | feat(billing): expose usable-until incl. grace | A |
| 3 | `feat/billing-schedule-any-change` | feat(billing): schedule any plan change | A |
| 4 | `docs/billing-policy-decisions` | docs(billing): record policy decisions | A |
| 5a | `fix/billing-settings-precedence` | fix(billing): DB settings override env for platform store | B |
| 5b | `feat/billing-payment-reconcile-job` | feat(billing): scheduled reconcile for missed payments | B |
| 6 | `feat/admin-billing-payments` | feat(admin): billing payments visibility | B |
| 7 | `feat/paused-store-read-only` | feat(billing): keep paused store history readable | A |

### Per-branch procedure (repo workflow)
1. `git fetch origin && git switch -c <branch> origin/main`
2. Implement + tests; keep commits conventional and scoped.
3. `git push -u origin <branch>`; `gh pr create --base main`.
4. Wait for CI: API `pytest` (`chmabapos_api`), Web (`apps/web`), Admin
   (`apps/admin`). No approving review required.
5. `gh pr merge --delete-branch`; `git switch main && git pull --ff-only`.
6. Rebase the next branch on the updated `main` before starting.

### Suggested schedule (≈5–6 dev days)
- Day 1: item 1 (branch/PR/merge); start item 3.
- Day 2: finish item 3; start item 2.
- Day 3: finish item 2 frontend + tests.
- Day 4: item 4 docs + pricing cleanup.
- Day 5: 5a precedence fix, then 5b reconcile job.
- Day 6: item 6 admin visibility; optional item 7 paused-store read-only.

Track B (5–6) can run in parallel by a second person once 5a lands, since 5b
depends on the corrected settings resolution.

---

## 8. Verification / test matrix

| Behavior | Test file | New/Changed |
| --- | --- | --- |
| Limit holds during grace | `tests/test_billing_quota.py` | New |
| Limit before/after period | `tests/test_billing_quota.py` | New |
| Stacked period resets count | `tests/test_billing_quota.py` | New |
| Schedule an upgrade | `tests/test_billing_schedule.py` | Changed |
| Paid scheduled upgrade at boundary | `tests/test_billing_schedule.py` | New |
| Unpaid scheduled upgrade → Free | `tests/test_billing_schedule.py` | New |
| Same-plan schedule rejected | `tests/test_billing_schedule.py` | Existing |
| `grace_ends_at` / `in_grace` fields | `tests/test_billing_entitlement.py` | New |
| Calendar periods | `tests/test_billing_immutability.py` | Changed |
| DB settings override env | `tests/test_payment_provider.py` | New |
| Reconcile self-heals a billing payment | `tests/test_billing_reconcile.py` | New |
| Reconcile idempotent / skips terminal | `tests/test_billing_reconcile.py` | New |
| Admin billing-payments list + secrecy | `tests/test_v1.py` or `tests/test_admin.py` | New |

Manual QA checklist:
- [ ] On a paid plan, past `ends_at`, inside grace: billing UI shows a future
      "usable until"; a sale over the limit is blocked.
- [ ] Schedule Pro from Starter; banner shows "Pro begins {date}, nothing charged
      today"; pay before the boundary → Pro active exactly at the date.
- [ ] Don't pay → Free fallback with "data is safe" copy and correct paused
      counts.
- [ ] Drop a plan-payment webhook in mock/live; run `run_billing_jobs.py` → the
      subscription activates once and a receipt exists.
- [ ] Admin panel lists the payment and shows the resolved platform store.
- [ ] Paused store: cannot sell, still appears in company reports, with the
      "paused — upgrade to reactivate" message.
- [ ] `docs/billing-improvement-plan.md` and `billing-model.md` agree with code.

---

## 9. Risks and open items

- **Item 7 paused-store scope** is the largest Track A change (read/write split
  in `get_store_context`); it is isolated in its own branch.
- **Grace/period date ambiguity** in the UI — mitigated by separate copy.
- **Scheduled-upgrade charging model** — a scheduled upgrade pays at renewal;
  no credit/refund for the current plan, consistent with existing policy.
- **Post-grace pre-job window** — fails closed today; optional follow-up.
- **Reconcile job cadence** must be documented for ops; consider hourly.
- **Doc drift** — each PR must update the relevant doc in the same change.

## 10. Definition of done
- All Track A and Track B branches merged to `main` with green CI.
- `docs/billing-model.md` has a Decisions section and no stale "Open questions".
- `docs/billing-improvement-plan.md` reflects items 1–6 as landed and provider
  abstraction explicitly deferred.
- Missed-webhook reconcile runs on the documented schedule.
- Admin can inspect plan payments without DB access.
- Test matrix green locally and in CI.

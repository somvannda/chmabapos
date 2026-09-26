# Billing enforcement fixes — detailed action plan

Status: **proposed** (awaiting sign-off on one policy decision, see §0.1).
Base revision: `main` @ `4420936`.

This document turns four agreed billing/enforcement gaps into shippable,
reviewable work. Each item below is a self-contained deliverable with a branch,
a PR, a task checklist, tests, acceptance criteria and a rollback.

The four items:

| # | Deliverable | Branch | Size |
| --- | --- | --- | --- |
| 1 | Close the grace-window transaction loophole | `fix/billing-grace-quota` | S |
| 2 | Let merchants schedule any future plan change | `feat/billing-schedule-any-change` | M |
| 3 | Show the real "usable until" date including grace | `feat/billing-usable-until-grace` | S |
| 4 | Decide + document the open policy questions | `docs/billing-policy-decisions` | S |

**Explicitly out of scope:** making the payment provider swappable
(improvement-plan §3.2.1 / Phase 4 item 12). ChmabaPay stays the only provider;
this plan only corrects the documentation so it stops implying otherwise.

Line references are against the base revision and will be re-checked in each PR.

---

## 0. Decision log

These decisions gate items 1–3. They are recorded here and land in
`docs/billing-model.md` under a new **Decisions** section (replacing the
"Open questions" list).

### 0.1 Paused store semantics — **DECISION NEEDED**

Question (§7.7): when a store is force-paused (expiry/downgrade), is it fully
blocked, or still readable?

**Recommended (option A): paused = cannot sell, but still visible in history.**
- Writes / POS / store-scoped operational endpoints stay blocked for a paused
  store.
- Store-scoped **read** endpoints return a clear "This store is paused — upgrade
  to reactivate" message instead of the current generic
  `404 Store not found or not accessible` (`app/deps.py:80`).
- Company-wide reporting and exports continue to include paused-store data.

Rationale: it matches the "Your data is safe" copy shown to merchants and avoids
the perception that history was deleted. Cost: needs a read/write distinction in
`get_store_context`, so it is the one decision with meaningful effort.

**Fallback (option B): paused = fully blocked (current behavior), documented.**
- Almost no code change; just document the behavior and the reassuring copy.

This is the only item blocking a start. Until chosen, item 4 ships option B as
the documented default and option A is tracked as a follow-up.

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
  (this is the item 1 fix).

### 0.4 Grace — **DECIDED: 48h, full access, limits enforced**

- `BILLING_GRACE_HOURS` default `48` (`app/config.py:39`) stays.
- Full paid access during grace; transaction limits still count (item 1).
- The grace deadline is exposed to clients for display (item 3).

### 0.5 Payment provider — **DECIDED: ChmabaPay only, documented**

- No provider abstraction work. Update `docs/billing-improvement-plan.md` to
  state Phase 4 item 12 is intentionally deferred and ChmabaPay is the sole
  provider, so docs match code.

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
- [ ] Add a **Decisions** section to `docs/billing-model.md` covering §0.1–0.5.
- [ ] In `docs/billing-improvement-plan.md`: mark §4.2 (generalized scheduled
      changes) as landed by item 2; note §7 items resolved; state Phase 4 item
      12 (provider abstraction) is intentionally deferred and ChmabaPay is the
      sole provider.
- [ ] `app/services/pricing.py`: delete `cycle_days()` and the fixed-day
      entries of `CYCLE_META` (calendar periods only); keep `CYCLE_META`'s
      months/discount/label.
- [ ] Update `tests/test_billing_immutability.py:90-91` to assert calendar
      behavior instead of fixed days.
- [ ] If §0.1 option A is chosen, add the follow-up task list here; if option B,
      document "paused = fully blocked" and the reassurance copy.
- [ ] Terms/Refund wording review for calendar periods (§0.2).

### Notes
This item ships **last** so the docs describe what actually landed, but its
decisions are locked up front so items 1–3 match them. If the paused-store
decision (option A) is chosen, it becomes its own branch
`feat/paused-store-read-only` after item 4.

---

## 5. Delivery plan

### Branch / PR map

| Order | Branch | PR title | Depends on |
| --- | --- | --- | --- |
| 0 | `docs/billing-enforcement-fixes-plan` | docs: billing enforcement fixes action plan | — |
| 1 | `fix/billing-grace-quota` | fix(billing): enforce transaction limit during grace | item 4 decisions |
| 2 | `feat/billing-usable-until-grace` | feat(billing): expose usable-until incl. grace | item 4 decisions |
| 3 | `feat/billing-schedule-any-change` | feat(billing): schedule any plan change | item 4 decisions |
| 4 | `docs/billing-policy-decisions` | docs(billing): record policy decisions | items 1–3 |
| 5* | `feat/paused-store-read-only` | feat(billing): keep paused store history readable | §0.1 option A only |

### Per-branch procedure (repo workflow)
1. `git fetch origin && git switch -c <branch> origin/main`
2. Implement + tests; keep commits conventional and scoped.
3. `git push -u origin <branch>`; `gh pr create --base main`.
4. Wait for CI: API `pytest` (`chmabapos_api`), Web (`apps/web`), Admin
   (`apps/admin`). No approving review required.
5. `gh pr merge --delete-branch`; `git switch main && git pull --ff-only`.
6. Rebase the next branch on the updated `main` before starting.

### Suggested schedule (≈3–4 dev days)
- Day 1: lock §0.1; item 1 (branch/PR/merge); start item 3.
- Day 2: finish item 3; start item 2.
- Day 3: finish item 2 (backend + UI + tests).
- Day 4: item 4 docs + pricing cleanup; optional paused-store follow-up.

---

## 6. Verification / test matrix

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

Manual QA checklist:
- [ ] On a paid plan, past `ends_at`, inside grace: billing UI shows a future
      "usable until"; a sale over the limit is blocked.
- [ ] Schedule Pro from Starter; banner shows "Pro begins {date}, nothing charged
      today"; pay before the boundary → Pro active exactly at the date.
- [ ] Don't pay → Free fallback with "data is safe" copy and correct paused
      counts.
- [ ] `docs/billing-improvement-plan.md` and `billing-model.md` agree with code.

---

## 7. Risks and open items

- **§0.1 paused-store scope** is the main size risk; tracked as option A/B.
- **Grace/period date ambiguity** in the UI — mitigated by separate copy.
- **Scheduled-upgrade charging model** — a scheduled upgrade pays at renewal;
  no credit/refund for the current plan, consistent with existing policy.
- **Post-grace pre-job window** — fails closed today; optional follow-up.
- **Doc drift** — each PR must update `docs/billing-model.md` in the same change.

## 8. Definition of done
- All four branches merged to `main` with green CI.
- `docs/billing-model.md` has a Decisions section and no stale "Open questions".
- `docs/billing-improvement-plan.md` reflects items 1–3 as landed and provider
  abstraction explicitly deferred.
- Test matrix green locally and in CI.

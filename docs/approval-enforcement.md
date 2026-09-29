# Approval enforcement (Phase 2)

Phase 1 shipped the **policy** (Settings -> Approval policy) and made the audit log
readable by managers. Phase 2 turns that policy into real controls.

## Modes

| Mode | Behaviour |
|------|-----------|
| `off` | Nothing changes. The action still lands in the audit log. |
| `review` | The action executes immediately, but is flagged in the audit log and the approvers are notified. No blocker. |
| `approval` | The action is **held**. An `approval_requests` row is created and only executes once an allowed role approves. |

## Async vs synchronous — the key decision

Some actions happen after the sale, so they can be held safely. Others happen
**mid-sale**, where holding them would block the customer and the queue.

**Async approval (request -> approve -> execute):**
- Refunds
- Cancel / void a paid order
- Large stock adjustment / write-off
- Loyalty point adjustment

**Review only in Phase 2 (no hold):**
- Discounts / price overrides. A discount is applied while the customer is at the
  counter; an async hold would stall the sale, so Phase 2 only **flags** it.

A discount that truly needs to be *blocked* should be a **synchronous manager
override** (an approver enters credentials/PIN at the register, the discount is
applied only if valid). That is a separate feature and is deferred to Phase 3.

## Data model: `approval_requests`

| Column | Notes |
|--------|-------|
| `id` | UUID |
| `company_id` | FK companies |
| `store_id` | FK stores, nullable |
| `action` | e.g. `refund`, `order_cancel` |
| `status` | `pending` / `approved` / `rejected` / `expired` |
| `amount` | optional value used for display / thresholds |
| `reason` | why it was requested |
| `payload` | JSON: everything needed to execute the action later |
| `requested_by` | FK users |
| `decided_by` / `decided_at` / `decision_reason` | the decision |
| `created_at` / `expires_at` | expiry from the policy |

## Lifecycle

`pending` -> `approved` -> executed (the response records the result)
`pending` -> `rejected`
`pending` -> `expired` (past `expires_at`; checked lazily and on read)

## Enforcement

At each guarded endpoint, before doing the work:

1. Load the company policy. If it is disabled or the rule is `off`, proceed as today.
2. Evaluate the threshold. Below it, proceed (still audited).
3. `review` -> proceed, then write an audit entry and notify approvers.
4. `approval` ->
   - If the caller's role is an allowed approver for this action, proceed
     (an owner acting on their own store is not blocked).
   - Otherwise create an `approval_requests` row and return `202 Accepted` with
     the request. Nothing is executed yet.
5. Maker-checker: when the policy enables it, the requester cannot approve their
   own request (except the owner).

First action wired: **refund**. Then cancel/void paid orders, then the rest.

## Decision

- `POST /approvals/{id}/approve` re-runs the stored action as the approver,
  records the result on the request, and audits both the request and the decision.
- `POST /approvals/{id}/reject` closes it with a reason.

## Notifications

- In-app: `Notification` rows to owners and managers.
- Telegram: reuse `record_activity`, which already forwards platform events.
- On decision: notify the requester.

## Rollout

Enforcement only activates when the policy is **enabled** (off by default), so
merging Phase 2 is inert until an owner turns it on.

## Testing

- Below threshold -> executes, no request.
- Above threshold, non-approver -> `202`, request `pending`, nothing executed.
- Approver approves -> action executes, request `approved`, audit present.
- Maker-checker -> the requester cannot approve their own request.
- Expired request cannot be approved.

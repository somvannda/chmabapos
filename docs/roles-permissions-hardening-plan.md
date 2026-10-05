# Roles & permissions hardening plan

Status: proposed — for review before implementation.
Owners: Engineering
Depends on: [`docs/roles-permissions-audit.md`](roles-permissions-audit.md) (merged, #504).
Scope: **harden the existing fixed-role model.** Keep the four tenant roles
(`owner`, `manager`, `inventory_manager`, `cashier`) and the two platform roles
(`admin`, `super_admin`). No custom roles, no permission matrix, no new tables.

## 1. Goal

Close the enforcement gaps the audit confirmed or documented so that the
backend, `apps/web` and `apps/admin` all agree on one role→action matrix, and
add regression tests that keep them aligned. Behavioural hardening only — this
plan does **not** add customer-defined roles or a granular permission system.

### Non-goals

- No custom/tenant-defined roles or per-user permission grants (that is a
  separate, larger product decision).
- No schema change in this plan. DB `CHECK` constraints for the role strings are
  a **separate optional follow-up** (§10) because they require a migration.
- No change to plan-capability semantics beyond making the UI respect them.

## 2. Target matrix (single source of truth)

This is the intended behaviour after hardening. It resolves the current
divergences (backend-permissive / UI-restrictive, and vice-versa).

| Surface | Allowed tenant roles | Plan gate |
|---|---|---|
| POS: sell, orders create, collect, held orders, shifts (own), customers create/update | owner, manager, cashier | held_orders / shift_management where noted |
| Refunds, void/cancel paid order | owner, manager, inventory_manager | refunds |
| Catalog: products, categories, variants, modifiers, combos, media | owner, manager, inventory_manager | inventory_management |
| Inventory: balances, adjust, restock, transfer, serials/trade-ins/warranty | owner, manager, inventory_manager | inventory_management |
| Suppliers + purchase orders (read & write) | owner, manager, inventory_manager | purchasing |
| Reports summary / condition | owner, manager, inventory_manager | advanced_reports |
| Consolidated report, GDT export | owner, manager | advanced_reports |
| Approvals (list/approve/reject) + approval policy (write) | owner, manager (policy write: owner) | — |
| Loyalty points adjust (manual) | owner, manager | loyalty |
| Loyalty redeem (at sale) | owner, manager, cashier | loyalty |
| Dining: areas/tables **config** (create/edit/delete) | owner, manager | table_management |
| Dining: floor operations, reservations | owner, manager, cashier | table_management |
| Notification send-summary / send-low-stock | owner, manager | — |
| Audit/activity log | owner, manager | — |
| Team roster (read) + invite/update/remove | owner | roles_permissions (store scoping) |
| Billing: subscription/payments/receipts/checkout/schedule | owner | — |
| Company & store settings writes | owner | — |
| Currency & exchange-rate config | owner | multi_currency |
| Settings read (managers) | owner, manager read-only | — |
| Support / help / notifications (own) | all four | — |

Platform admin target:

| Surface | Allowed platform roles |
|---|---|
| Reads across all admin modules | admin, super_admin |
| Company/store availability, payment-link status, billing refund, templates, help, support tickets | admin |
| User activation & `platform_role`, plans, mail settings/secrets, AI settings/secrets, session policy, mailing send/queue/drip, suppressions | **super_admin** |
| ChmabaPay settings write + secret reveal (changed) | **super_admin** (§6) |

## 3. API enforcement changes (`app/api/v1.py`)

Add the appropriate `Depends(require_roles(...))` (reuse `owner_roles` /
`catalog_roles`, or a new `manager_roles = require_roles("owner","manager")`)
to:

| Route(s) | Current | Change to |
|---|---|---|
| `GET /billing/subscription`, `/billing/payments`, `/billing/receipts` | any member | `owner_roles` |
| `GET /team` | any member | `owner_roles` |
| `POST /notifications/send-summary`, `/notifications/send-low-stock` | any member | `manager_roles` |
| `PATCH /customers/{customer_id}/points` | any member | `manager_roles` |
| `GET|POST|PATCH|DELETE /suppliers` | any member | `catalog_roles` |
| `GET|POST /purchases`, `/purchases/{id}/cancel`, `DELETE /purchases/{id}`, `/purchases/{id}/receive` | any member (receive already `catalog_roles`) | `catalog_roles` |
| `POST|PATCH|DELETE /dining/areas`, `/dining/tables` | any member | `manager_roles` |

Notes:
- **Shifts stay member-level**: `POST /shifts/open` and `/shifts/{id}/close` are
  legitimate cashier actions; keeping the existing "close another user's shift
  = owner/manager" inline check.
- **Dining reservations stay member-level** (floor operations).
- **Loyalty redeem stays member-level** (happens during a sale); only the
  manual points *adjustment* moves to manager+.
- Existing inline checks (`consolidated_report`, `transfer_stock` destination,
  `list_stores` inactive) should be **converted to named dependencies** where
  possible so the matrix is declarative (§9 testability).

## 4. Approval fixes

1. `reject_approval` (`v1.py`): add the same `rule.approvers` check that
   `approve_approval` has, so a manager cannot reject a request only an owner
   may decide. Keep maker-checker semantics identical to approve.
2. **Product decision (owner maker-checker):** currently owners always bypass
   `maker_checker`. Decide whether to keep (document) or require a second
   owner/manager for owner-raised requests. Not changed without a decision.
3. **Product decision (`ApprovalRule.approvers`):** whether
   `inventory_manager` may approve stock write-offs. If yes, widen the Literal
   in `schemas.py`; if no, document it.

## 5. Notification / digest fixes (`app/services`)

1. `notify_company_managers`: store-scope manager targeting via
   `MembershipStore` (owners still company-wide). Producers already pass
   `store_id`.
2. `mailing.py`: dead-letter recipients → `platform_role.in_(("admin","super_admin"))`.
3. `store_notifications.DIGEST_TYPES`: align with the review kinds actually
   emitted (`price_cost_edit_review`, `stock_write_off_review`,
   `cancel_paid_order_review`, `loyalty_adjust_review`), or document the
   exclusion.

## 6. Platform admin fixes (`app/api/admin.py`)

1. `PATCH /chamabapay-settings` and `POST /chamabapay-settings/reveal` →
   `require_super_admin` (match mail/AI secret handling).
2. `DELETE /mailing/templates/{template_id}` → `require_super_admin`.
3. Add a **last-super-admin guard** in `PATCH /users/{user_id}`: refuse to
   demote/deactivate the final active `super_admin`.
4. **Decision:** keep company/store availability toggles at plain `admin`
   (support) or raise to `super_admin`. Default: keep at `admin`, document why.

## 7. Web client fixes (`apps/web`)

1. **Restore the view gate:** render `contentForRole` (or return
   `TenantAccessDenied`) in `workspace.jsx`; enforce `VIEW_ROLES` on the route in
   `App.jsx`/`routing.js` (not just the sidebar), covering direct URLs.
2. **Reconcile `VIEW_ROLES`** with the matrix in §2 (add/remove
   `inventory_manager` consistently; align suppliers/purchasing/dining).
3. **Pass `memberRole` into settings panes, team and billing** and disable/hide
   owner-only writes for managers, following the `SessionPolicyPane` /
   `BankKhqrPane` pattern. Sections a manager may not write should be read-only.
4. **Plan-feature gating:** expose the plan's enabled capabilities on the
   workspace payload (or add an entitlements field) and gate held orders,
   refunds, shifts, purchasing, loyalty, multi-currency, advanced reports,
   email receipts, `table_management`, `inventory_management` — do not rely on
   vertical capability packs.
5. **Capability helper:** stop failing open for plan features; keep the
   documented pack behaviour or make it explicit. Fix `catalog.jsx`'s
   `useCapabilities(token)` call to pass `storeId`.

## 8. Admin client fixes (`apps/admin`)

1. Pass `user`/`canManage` into `AdminUsers` and `AdminPlans` so a plain `admin`
   does not see enabled super-admin-only controls (Suspend/Restore, plan save).
2. Admit the panel only for `platform_role in {admin, super_admin}` (match the
   backend), not any truthy value.
3. Optionally surface the API-only `platform_role` change (promote/demote) with
   the last-super-admin guard reflected in the UI.

## 9. Test strategy

- **Backend matrix test** (new `tests/test_role_permissions_matrix.py`):
  parametrised over role → (method, path, expected status) for every route in
  §3 plus the existing controls, so a regression fails CI. Reuse the
  register/verify/setup/invite fixture patterns from `test_multistore.py`.
- **Approval test:** manager cannot reject an owner-only rule; manager can
  reject a manager-eligible rule.
- **Admin test:** plain `admin` gets 403 on ChmabaPay write/reveal and template
  delete; last-super-admin demotion is refused.
- **Web tests** (Vitest): `VIEW_ROLES`/`canViewRole` behaviour, the restored
  view gate, and manager vs owner settings save visibility.
- **Admin build/tests:** gating of super-admin-only controls.
- Keep `docs/roles-permissions-audit.md` as the reference and update it when
  items land.

## 10. Out of scope / follow-ups (not this plan)

- **Multi-company resolution** (audit §9.2): pinning the oldest membership. Fix
  needs a tenant selector (e.g. validated `X-Company-ID` or a persisted current
  workspace) and fail-closed behaviour. Separate design.
- **DB role constraints** (audit §9.3): `CHECK`/enum on role columns +
  `server_default`. Separate migration.
- **Custom roles / permission matrix** (audit §1–2): the larger `roles_permissions`
  product decision.
- **`roles_permissions` labelling:** decide whether the plan feature means
  "multi-store staff access" (current reality) or true permissions.

## 11. Suggested PR sequence

1. `fix(api): guard billing, team, notification, loyalty, supplier, purchase and dining routes` (+ matrix tests).
2. `fix(api): enforce rule.approvers on approval rejection`.
3. `fix(admin): super-admin guards for ChmabaPay/templates + last-super-admin protection`.
4. `fix(web): restore the view-level role gate and route enforcement` (+ tests).
5. `fix(web): role-gate owner-only settings/team/billing writes`.
6. `fix(web): gate plan features and fix the capability helper`.
7. `fix(admin): gate super-admin-only controls in the panel`.
8. `fix(api): store-scope manager notifications and align the ops digest`.
9. (separate) multi-company tenant selector; DB role constraints.

Each PR ships independently, off `origin/main`, green CI as the gate.

## 12. Open decisions (need product/owner input)

1. Owner maker-checker bypass — keep or require dual control?
2. May `inventory_manager` approve stock write-offs (`ApprovalRule.approvers`)?
3. Company/store deactivation at `admin` vs `super_admin`?
4. `roles_permissions` = store scoping (rename) or true permissions (feature)?
5. Managers: read-only Settings/Team/Billing, or hidden entirely?

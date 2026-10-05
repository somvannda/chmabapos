# Roles & permissions enforcement audit

Status: audit complete for the tenant/API surface; findings are advisory backlog
items, not yet fixed.
Owners: Engineering
Scope: `chmabapos_api` (tenant + platform roles), `apps/web`, `apps/admin`,
`packages/api-client`, auth/data layer.
Method: static review of all 203 `app/api/v1.py` routes and the surrounding
services/admin routes, **plus runtime probing** of a disposable Pro workspace
with owner + manager + cashier accounts (probe module removed after the run).
Related: `docs/capabilities-and-gaps.md`, `docs/approval-enforcement.md`,
`docs/architecture.md`, `docs/billing-model.md`.

## 1. Summary

The product ships a **fixed four-role model** (owner, manager,
inventory_manager, cashier) plus two **platform roles** (admin, super_admin).
Enforcement is a mix of reusable FastAPI dependencies in `app/deps.py` and
ad-hoc inline `membership.role` checks scattered through `app/api/v1.py`. The
UI (`VIEW_ROLES` in `apps/web` and platform-role gates in `apps/admin`) mirrors
the intent but is **not** a security boundary.

The audit found a consistent, systematic gap: **many write/read routes are
guarded only by "is an active member of the company"**, so a `cashier` (or any
member) can perform actions the UI hides from them. Several of these were
**confirmed live** (§3). There are also platform-admin inconsistencies and one
asymmetric approval check.

Highest-impact items, ordered:

| # | Sev | Area | Finding | Status |
|---|-----|------|---------|--------|
| 1 | High | API | Cashier/manager can directly adjust customer loyalty points (`PATCH /customers/{id}/points`) | **Confirmed** |
| 2 | High | API | Cashier/manager can read billing (subscription, payments, receipts) | **Confirmed** |
| 3 | High | API | `POST /approvals/{id}/reject` never checks `rule.approvers` (asymmetric with approve) | Static |
| 4 | High | Admin | ChmabaPay gateway write + secret reveal require only `admin`, not `super_admin` | Static |
| 5 | Medium | API | Cashier/manager can create suppliers and purchase orders | **Confirmed** |
| 6 | Medium | API | Any member can read the full team roster (`GET /team`) | **Confirmed** |
| 7 | Medium | API | Any member can trigger company-wide emails (`/notifications/send-*`) | **Confirmed** |
| 8 | Medium | Services | Dead-letter alerts exclude `super_admin` (`mailing.py`) | Static |
| 9 | Medium | Services | Approval/review notifications are company-wide, not store-scoped | Static |
| 10 | Medium | Services | Ops-digest event list omits four emitted review kinds | Static |
| 11 | Low-Med | API | Any member can create/edit dining areas & tables (store config) | **Confirmed** |
| 12 | Low-Med | Admin | `admin` (not `super_admin`) can toggle company/store availability and delete mail templates | Static |
| 13 | High | Auth | Multi-company users are pinned to their **oldest** membership; no workspace switcher exists | Static |
| 14 | Medium | Data/Admin | Roles have no DB constraint; admin UI shows super-admin-only actions to plain `admin` | Static |
| 15 | High | Web | The view-level role gate is **dead code** (`contentForRole` is never rendered); owner-only views are reachable by URL | Static (code-evident) |
| 16 | Medium | Web | Plan features are never checked in the UI; only vertical packs, and the capability check fails **open** | Static |

## 2. Roles model

| Axis | Field | Values | Canonical guard |
|------|-------|--------|-----------------|
| Platform staff | `User.platform_role` | `admin`, `super_admin` | `get_platform_admin` (`deps.py:159`, set `{admin, super_admin}`), `require_super_admin` (`deps.py:165`) |
| Tenant member | `Membership.role` | `owner`, `manager`, `inventory_manager`, `cashier` | `require_roles(...)` (`deps.py:150`) |
| Assignable role | `MembershipUpdateRequest.role` / `InvitationCreateRequest.role` | `manager`, `cashier`, `inventory_manager` (owner excluded) | `schemas.py:1422,1429` |

- `ALL_ROLES` is defined once in `app/support_content.py:24` and reused by
  `schemas.py` validation — the one good single source of truth.
- Roles are **free strings in the DB** (`app/models.py:27,158`); there is no
  CHECK/enum constraint. Validity is enforced only at the API boundary, which
  fails closed (an unknown role matches no `require_roles` set).
- Store scoping is separate from roles: non-owners are limited to stores linked
  in `MembershipStore` (`deps.py:100-108`); owners see all company stores.
- `roles_permissions` (`app/features.py:25`) is a **plan capability**, not a
  permission system. It only gates assigning staff to specific stores
  (`v1.py:6089,6153`). Per-role permissions are otherwise fixed in code.

### Endpoint guard distribution (`app/api/v1.py`, 203 routes)

| Guard combination | Count |
|---|---|
| `get_store_context` only | 45 |
| `get_current_membership` only | 34 |
| `catalog_roles` + `get_store_context` | 28 |
| `owner_roles` | 24 |
| `catalog_roles` only | 15 |
| `get_store_context_read` | 11 |
| `get_current_user` only | 7 |
| `require_roles(...)` inline | 3 |
| No guard (public/auth/webhooks) | 25 |
| Other combinations | 11 |

The two "only" rows (79 routes) are the risk surface: they admit **any active
member**.

## 3. Runtime-confirmed findings

A disposable Pro workspace was provisioned with owner, manager and cashier
accounts. Results (role → HTTP status):

| Endpoint | owner | manager | cashier | Expected | Finding |
|---|---|---|---|---|---|
| `GET /billing/subscription` | 200 | 200 | **200** | owner | billing readable by all members |
| `GET /billing/payments` | — | 200 | **200** | owner | payment history exposed |
| `GET /billing/receipts` | — | 200 | **200** | owner | receipts exposed |
| `GET /team` | 200 | 200 | **200** | owner | full roster exposed |
| `POST /notifications/send-summary` | — | 200 | **200** | owner/manager | company email trigger |
| `POST /notifications/send-low-stock` | — | 200 | **200** | owner/manager | company email trigger |
| `POST /dining/areas` | — | 201 | **201** | manager+ | store config writable by cashier |
| `POST /shifts/open` | — | 201 | 201 | cashier+ | acceptable |
| `POST /suppliers` | — | 201 | **201** | catalog_roles | supplier write allowed to cashier |
| `POST /purchases` | — | 201 | **201** | catalog_roles | PO write allowed to cashier |
| `PATCH /customers/{id}/points` | — | 200 | **200** | see #1 | loyalty points changed directly |
| `GET /reports/consolidated` (control) | 200 | 200 | **403** | owner/manager | correct (inline check) |
| `PUT /approval-policy` (control) | — | 403 | **403** | owner | correct |
| `GET /inventory`, `POST /orders` (control) | — | 200/201 | 200/201 | any member | correct |

Controls confirm the probe was sound and that the inline `consolidated_report`
guard (`v1.py:7101`) works — it just does not use the reusable dependency.

## 4. Backend / API findings (static)

### 4.1 Asymmetric approval rejection (High)

`reject_approval` (`v1.py:5859`) is guarded only by
`require_roles("owner","manager")` and never reads `rule.approvers`.
`approve_approval` (`v1.py:5891`) does check `membership.role not in
rule.approvers`. With the shipped default `price_cost_edit.approvers ==
["owner"]` (`schemas.py:1249`), a **manager can reject a request they cannot
approve**. Rejection is also outside maker-checker.

### 4.2 Loyalty points bypass the approval gate (High — confirmed)

`PATCH /customers/{id}/points` (`v1.py:7860`) runs the approval gate, but the
default policy has `enabled: false`, and even when enabled a non-approver only
triggers a `pending` response — yet the route is reachable by any member and a
`review`/`allow` outcome mutates points directly. Confirmed 200 for a cashier.

### 4.3 `notify_company_managers` ignores store scope (Medium)

`v1.py:7406-7409` selects owners/managers by `company_id` only, with no
`MembershipStore` join, even though producers pass a `store_id`. A manager
assigned only to Store A is notified about Store B events.

### 4.4 Owner maker-checker bypass (Medium, design)

The expression `policy.maker_checker and membership.role != "owner"` appears in
`v1.py:2863, 4159, 5086, 5839, 5893, 7876`. Owners can always self-approve, so
"maker-checker" provides no separation of duty for owners. Consistent, but worth
a product decision.

### 4.5 Approval approver list is owner/manager only (Medium, design)

`ApprovalRule.approvers: list[Literal["owner","manager"]]` (`schemas.py:1235`)
means `inventory_manager` can never approve stock write-offs. Revisit if the
inventory role is meant to own that.

### 4.6 Free-form roles in the DB (Low)

`app/models.py:27,158,1097` store roles as unconstrained `String`. Consider a
CHECK constraint or enum so out-of-band writes cannot create mystery roles.

### 4.7 Inline checks duplicate dependency intent (Low)

`v1.py:7101,7111,7386` and `4365` re-implement owner/non-owner logic inline
instead of a named dependency. This is why a signature-only scan misclassifies
`/reports/consolidated`. Consolidating improves reviewability.

## 5. Platform admin findings (static)

| # | Sev | Route | Guard | Should be | Why |
|---|-----|-------|-------|-----------|-----|
| A1 | High | `PATCH /chamabapay-settings` (`admin.py:1183`) | `get_platform_admin` | `require_super_admin` | live gateway mode/URL/keys/secret writable by plain `admin` |
| A2 | High | `POST /chamabapay-settings/reveal` (`admin.py:1203`) | `get_platform_admin` | `require_super_admin` | plaintext gateway secret read by plain `admin`; mail/AI reveals require super admin |
| A3 | Medium | `DELETE /mailing/templates/{id}` (`admin.py:1887`) | `get_platform_admin` | `require_super_admin` | other mailing destructive ops are super-admin |
| A4 | Low-Med | `PATCH /companies/{id}` (`admin.py:951`), `PATCH /stores/{id}` (`admin.py:1086`) | `get_platform_admin` | policy decision | tenant/store lockout + commercial toggle at plain-admin |
| A5 | Low | `PATCH /users/{id}` (`admin.py:821`) | `require_super_admin` | — | a super admin can demote the last super admin (lockout risk) |

All admin routes are guarded (no unguarded route). Reads uniformly use
`get_platform_admin`; sensitive writes (plans, mail, AI, session, user role)
use `require_super_admin`, making the exceptions above stand out.

## 6. Notification / digest findings (static)

- `app/services/mailing.py:386` — dead-letter alerts filter
  `User.platform_role == "admin"`, silently excluding `super_admin`, diverging
  from the canonical `{admin, super_admin}` set (`deps.py:160`).
- `app/services/store_notifications.py:55` — `DIGEST_TYPES` omits the review
  kinds actually emitted (`price_cost_edit_review`, `stock_write_off_review`,
  `cancel_paid_order_review`, `loyalty_adjust_review`), so they never reach the
  ops digest email (the in-app rows still exist).
- Owner/capacity/billing emails (`billing_emails`, `sale_emails`,
  `quota_warnings`, `reminders`, `billing_lifecycle`) consistently target
  `role == "owner"`; that is intended and correct. `billing_lifecycle` keeps at
  least one owner active and revokes non-owners when over capacity — correct.

## 7. Support content (static)

- `app/support_content.py:1181-1186` — the cashier starter-prompt filter falls
  back to the **unfiltered** general list when no prompt contains "sale"/"shift",
  leaking owner/manager setup prompts to cashiers. Guidance leakage only, not a
  privilege escalation.
- `filter_sections` indexes `article["roles"]`/`["verticals"]` directly; safe for
  static data and DB rows (non-null columns) but fragile if the corpus changes.

## 8. Recommendations (backlog, one PR each)

1. **Lock down confirmed API gaps** — add `require_roles`/owner-or-manager guards
   to: billing reads, `GET /team`, both notification-send routes, loyalty points
   adjust, supplier writes, purchase writes, and dining-area/table config. Decide
   explicitly whether shifts stay member-level.
2. **Fix `reject_approval`** to check `rule.approvers` symmetrically with
   `approve_approval`.
3. **Move ChmabaPay write/reveal to `require_super_admin`** and align
   `mailing.py:386` to `{admin, super_admin}`.
4. **Store-scope `notify_company_managers`** via `MembershipStore`.
5. **Align `DIGEST_TYPES`** with emitted review kinds.
6. **Replace inline role checks** with named dependencies so the matrix is
   declarative and testable.
7. **Add a drift test** that pins the intended role→endpoint matrix (billing,
   team, loyalty, suppliers, purchases, notifications, dining) and a test that
   `VIEW_ROLES` matches the backend's intended role map.
8. **Fix multi-company tenant resolution** (`deps.py:70-83`): add an explicit
   workspace selector and fail closed on ambiguous membership.
9. **Constrain roles in the database:** CHECK/enum on `memberships.role`,
   `memberships.status`, `users.platform_role`, `invitations.role`, plus
   `server_default` where a default is intended; wire to `ALL_ROLES`.
10. **Prevent the last-super-admin lockout** (`admin.py:820-839`).
11. **Align the admin UI** with backend guards: pass `user`/capability into
    `AdminUsers`/`AdminPlans` so plain `admin` cannot see super-admin-only
    controls, and optionally add a `platform_role` editor.
12. **Product decisions:** relabel or re-scope `roles_permissions` (store
    scoping vs true permissions), revisit owner maker-checker bypass, and
    `ApprovalRule.approvers` membership.
13. **Restore the web view gate (10.1)** and enforce `VIEW_ROLES` on the route
    (not just the sidebar) in `App.jsx`/`routing.js`.
14. **Pass `memberRole` into settings/team/billing components** and disable or
    hide owner-only saves for managers, following the
    `SessionPolicyPane`/`BankKhqrPane` pattern (10.2).
15. **Gate plan features in the UI (10.3)** — expose plan capabilities on the
    workspace payload and check them, rather than relying on vertical packs.
16. **Fix the fail-open capability helper and the missing `storeId`** in
    `catalog.jsx` (10.4).
17. **Add web role/capability tests** so the dead-gate regression and future
    drift are caught (10.6).

## 9. Auth, data layer & admin UI (static)

### 9.1 Immediate revocation — good

No role or permission is embedded in the JWT. `create_token`
(`app/security.py:29-37`) embeds only `sub`, `exp`, `iat`, `type`, `sid`. Every
request re-reads the user row, the live `AuthSession` (`deps.py:40-42`) and the
membership, so role changes, membership revocation, company/account
deactivation and logout take effect on the next request. `sid` is required and
checked; a token without a live session fails. Platform-admin status is likewise
read fresh from `user.platform_role` on each request. **Verdict: immediate
revocation confirmed.**

### 9.2 Multi-company resolution pins the oldest membership (High)

`get_current_membership` (`deps.py:70-83`) uses
`.order_by(Membership.created_at).first()`, i.e. the **earliest-created active
membership**. There is no company/workspace switch endpoint (`X-Store-ID` only
selects a store within the pinned company). A user who owns company A and was
invited into company B is permanently bound to whichever membership was created
first; if B predates A they are treated as a cashier in B and the owner
workspace A becomes unreachable through the API. This is a functional lockout,
not cross-tenant leakage (all queries are scoped to the pinned
`company_id`). `scripts/audit_catalog.py:89-109` already refuses to guess when a
user has multiple companies, but request handling does not.
Recommendation: add an explicit tenant selector validated against active
memberships, and fail closed (409) when >1 membership exists and none is
supplied.

### 9.3 Role columns are unconstrained (Medium)

No `CheckConstraint` exists anywhere in the backend. `memberships.role`,
`memberships.status`, `users.platform_role` and `invitations.role` are plain
strings (`models.py:27,158,159,1097`), validated only by Pydantic. Unknown
values fail closed (they match no `require_roles` set), so this is an integrity
issue, not an escalation. Also, `role` columns are `NOT NULL` with **no
`server_default`** — the `"cashier"` default is Python-side only, so raw SQL /
migration inserts must supply a role. Consider CHECK constraints (or an enum)
wired to `ALL_ROLES`, plus server defaults where intended. `uq_membership_company_user`
(`models.py:153`) correctly makes one membership per (company, user) impossible
to duplicate.

### 9.4 Platform privilege lockout (Medium)

`PATCH /admin/users/{id}` (`admin.py:820-839`) blocks self-deactivation only; a
super admin can demote **the last super admin** (including themselves) via
`platform_role`. Add a "cannot remove the last super admin" guard.

### 9.5 Admin UI shows actions a plain `admin` cannot perform (Medium)

The admin panel admits any truthy `platform_role` (`main.jsx:71-114`) while the
backend accepts only `{admin, super_admin}` (`deps.py:160`). `AdminUsers` and
`AdminPlans` are rendered without a `user`/capability prop (`App.jsx:2170`), so a
plain `admin` sees enabled Suspend/Restore and plan-save controls that call
`require_super_admin` endpoints (`admin.py:821,1371,1394`) and only learn of the
denial via a 403. There is no UI at all to change `platform_role` even though the
API supports it. Mail/AI/session settings are correctly gated by `canManage` on
the client. `schema.d.ts` role types faithfully match the backend schemas.

### 9.6 Bootstrap reality

`scripts/seed.py` seeds no users; `scripts/bootstrap_admin.py` creates only a
**`super_admin`** (`bootstrap_admin.py:26,32`). A freshly bootstrapped platform
therefore typically has zero `admin` rows, which makes the dead-letter filter
(`mailing.py:386`, `== "admin"`) an active operational gap rather than a
theoretical one.

## 10. Frontend gating (static)

`apps/web` mirrors the backend's intended role matrix in a `VIEW_ROLES` map
(`workspace.jsx:29`) and gates vertical capability packs in
`lib/capabilityPacks.js`, but the enforcement has gaps.

### 10.1 The view-level role gate is dead code (High)

`workspace.jsx:258` computes
`const contentForRole = canViewRole(memberRole, activeView) ? content : <TenantAccessDenied role={memberRole} />`
but then renders `{content}`, never `contentForRole`. `TenantAccessDenied` is
unreachable, and `VIEW_ROLES` only filters the **sidebar**. Because `App.jsx` /
`routing.js` map URLs to views without a role check, any authenticated member
can render owner-only views by navigating directly (`/…/team`, `/…/billing`,
`/…/settings`, `/…/activity`). This is code-evident (single reference to
`contentForRole`). Backend writes still 403, so it is a UI/exposure defect plus
a false sense of enforcement — but it also means the client can now call
any-role **reads** the UI intended to hide (e.g. `GET /team`, billing reads;
see §3).

### 10.2 Managers see editable owner-only settings (High)

`VIEW_ROLES.settings = ["owner","manager"]`, but almost every settings pane
issues owner-only writes with no role check: `saveCompany` (`PATCH /company`),
`saveStore`/`updateStore` (`PATCH /stores/{id}`), feature packs, notifications,
loyalty, POS prefs, customer display, inventory defaults, currencies/exchange
rates, and online ordering (`settings.jsx:39-102,321,953-955`). Only
`ApprovalPolicyPane`, `SessionPolicyPane`, `BankKhqrPane` self-gate on
`memberRole === "owner"` (the correct pattern). `LiveTeamView`
(`team.jsx:343`) and `LiveBillingView` (`team.jsx:96`) likewise render
invite/remove/checkout/schedule controls to non-owners.

### 10.3 Plan features are not checked at all (Medium)

Capability packs (`barcode`, `variants`, `tables`, `serials`, `batches`,
`modifiers`, …) are **vertical** features (`app/verticals.py`), not plan
features (`app/features.py`). The web app never reads plan entitlements
(`grep` for entitlement/`require_plan` returns nothing), so plan-gated surfaces
are always shown: held orders, refunds, shifts, purchasing, loyalty,
multi-currency, advanced reports/GDT, email receipts, `table_management` and
`roles_permissions`. Users hit a 403 only when they act. `reports.jsx` even
gates the condition report on the `serials` pack while the backend gates it on
`advanced_reports`.

### 10.4 Capability check fails open (Medium)

`allowsCapability` (`capabilityPacks.js:32-33`) returns true when
`capabilities == null`, and `useCapabilities` sets `null` on error, so on
loading/error the UI shows every pack. `catalog.jsx:155` calls
`useCapabilities(token)` without `storeId`, so its pack tabs can reflect the
wrong/stale store.

### 10.5 Positive examples

- Order-list refund/void/collect buttons are correctly limited to
  `["owner","manager","inventory_manager"]` (`sales.jsx:180-182`), matching
  `catalog_roles`.
- Approval nav is only surfaced once the policy is enabled; role checks match
  `GET /approval-policy`.
- No role is trusted from the client; every action is ultimately authorized
  server-side.

### 10.6 No role tests

`apps/web` has **no** test covering `VIEW_ROLES`, `canViewRole`,
`TenantAccessDenied`, or any role-gated path, which is why the dead-gate
regression (10.1) shipped unnoticed. The `apps/admin` panel shows
super-admin-only controls (Suspend/Restore, plan save) to plain `admin`
(`App.jsx:2170` passes no `user`), and admits any truthy `platform_role`
(`main.jsx:71-114`) vs the backend's `{admin, super_admin}`.

## 11. Method & limitations

- Static review covered `app/api/v1.py` (all routes), `app/api/admin.py`,
  `app/services/**`, `app/support_content.py`, `app/verticals.py`,
  `app/features.py`, `app/models.py`, `app/schemas.py`, `app/deps.py`.
- Runtime probing used a dedicated database (`chmaba_roles_audit`) migrated and
  seeded from scratch, so results reflect the current schema. The probe module
  was temporary and is **not** committed.
- Frontend findings (§10) and auth/data-layer findings (§9) are static; the
  runtime probe exercised the API only. No browser/Playwright run was performed,
  so the dead view gate (§10.1) is code-evident but not browser-verified.
- Not covered here: non-role operational concerns and a browser-level walkthrough
  of the admin panel.

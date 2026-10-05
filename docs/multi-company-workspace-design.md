# Multi-company workspace resolution — design

Status: proposed — needs a product decision before implementation.
Owners: Engineering
Related: `docs/roles-permissions-audit.md` §9.2 (audit #504),
`docs/roles-permissions-hardening-plan.md` §10.

## 1. Problem

A user can belong to more than one company: `POST /workspaces/setup` creates an
owner membership, and invitations add memberships in other companies
(`accept_team_invitation`, `accept_invitation_as_owner`). But **request
handling cannot choose between them**:

```python
# app/deps.py:70-83
select(Membership)
  .join(Company, ...)
  .where(user_id == user.id, status == "active", Company.is_active)
  .order_by(Membership.created_at)
membership = result.scalars().first()
```

It silently pins the **earliest-created active membership**. There is no
company/workspace switch endpoint — `X-Store-ID` only selects a store inside
the already-pinned company.

Consequences:

- A user who owns company A but was invited into an older company B is treated
  as B's member (possibly `cashier`) and **company A becomes unreachable** —
  a functional lockout, not a data leak (all queries scope to the pinned
  `company_id`).
- `Membership.created_at` has no server default, so equal timestamps make
  `.first()` non-deterministic.
- `scripts/audit_catalog.py:89-109` already refuses to guess for multi-company
  users, proving the ambiguity is real; production does not.

## 2. Goals / non-goals

Goals:
- Let a multi-company user pick which company a session operates in.
- Make the default deterministic and safe (fail closed when ambiguous).
- Keep single-company users unaffected.

Non-goals:
- Cross-company aggregate views (out of scope).
- Changing the role model or permissions.

## 3. Options

### A. Explicit header only — `X-Company-ID`

`get_current_membership` validates an `X-Company-ID` header against the user's
active memberships; missing/invalid header → 409 (or 400) when the user has >1
membership, else use the single membership.

- Pros: stateless, API-friendly, mirrors `X-Store-ID`.
- Cons: every client must send it; a browser page reload without the header
  loses context; needs a "which companies do I have" endpoint for the UI.

### B. Persisted current workspace (recommended)

Store the chosen company server-side and resolve it on each request:
- **B1 — per session:** add `AuthSession.current_company_id` (FK, nullable).
  Switching is per sign-in/device. Requires one migration.
- **B2 — per user:** `User.preferences["current_company_id"]` (the `preferences`
  JSON already exists). No migration; switching follows the user across devices.

`get_current_membership` reads the persisted value if it still maps to an
active membership; otherwise falls back deterministically (prefer an `owner`
membership, then newest), and if there is still genuine ambiguity with no
persisted choice, **fail closed with 409** and a clear message.

### C. Both — persisted default + optional header override

B as the default, plus an optional `X-Company-ID` to override per request
(validated against memberships). Most flexible; slightly more surface.

## 4. Recommended approach

Ship **B1 (per-session)** plus a light **A** override later if API clients need
it. Per-session is the most predictable for the browser (a tab's workspace does
not silently change because of another device) and keeps the resolver honest.

### API

- `GET /api/v1/workspaces` → list the caller's active memberships
  (`company_id`, `name`, `role`, `is_current`).
- `POST /api/v1/workspaces/switch` `{ company_id }` → validate an active
  membership, persist it on the current `AuthSession`, return the workspace
  payload (`workspace_response`).
- `GET /api/v1/workspaces/current` (exists as `/workspaces/current`) → unchanged
  shape; now reflects the persisted choice.
- `get_current_membership` resolution order:
  1. `AuthSession.current_company_id` if it maps to an active membership;
  2. else the only active membership, if exactly one;
  3. else prefer an `owner` membership (deterministic tie-break by newest);
  4. else `409 Ambiguous workspace — choose a workspace`.

### Data model (B1)

- Migration: `auth_sessions.current_company_id UUID NULL`
  (`ON DELETE SET NULL`), no backfill required.
- Alternatively (B2, no migration): `User.preferences["current_company_id"]`.

### Frontend (`apps/web`)

- Fetch `GET /workspaces` after sign-in; if >1 membership show a workspace
  switcher next to the store switcher in `AppHeader`.
- On switch: `POST /workspaces/switch`, then reload the workspace, stores, and
  navigate to the dashboard.
- The existing `workspace.membership_role` drives `VIEW_ROLES`, so switching
  naturally re-gates the UI.

### Tests

- Resolver: single membership always resolves; two memberships without a choice
  fails closed (or uses the persisted choice); switching changes the resolved
  company and role; a user cannot switch to a company they are not an active
  member of; a deactivated membership/company is not selectable.

## 5. Backward compatibility & rollout

- Single-company users: unchanged.
- Multi-company users currently on the (arbitrary) oldest membership: after
  rollout they are placed on the persisted/owner membership; the switcher lets
  them reach the other. This is a **behaviour change** — call it out in release
  notes.
- Order: (1) migration + resolver + endpoints with the deterministic default
  (no 409 yet), (2) emit a one-time log/metric for users with >1 membership,
  (3) enable fail-closed, (4) ship the frontend switcher.

## 6. Open decisions

1. Persist per **session** (B1, migration) or per **user** (B2, no migration)?
2. Is a hard `409` acceptable for API clients with multiple memberships and no
   choice, or should the first call silently pick the owner membership?
3. Do we need the `X-Company-ID` override (option C) for server-to-server use?

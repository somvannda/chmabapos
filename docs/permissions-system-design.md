# User roles & permissions system — design

Status: proposed — for review before implementation.
Owners: Engineering
Related: `docs/roles-permissions-audit.md`, `docs/roles-permissions-hardening-plan.md`.
Depends on the hardening work already merged (fixed-role enforcement, plan gating,
matrix tests). This doc describes the next step: **real, company-defined roles**
with a permission catalog.

## 1. Goal

Replace the fixed four-role model (`owner`, `manager`, `inventory_manager`,
`cashier`) with a **role + permission** system for the customer portal
(`apps/web`):

- A **permission catalog** of named capabilities (e.g. `sales.refund`,
  `catalog.manage`, `reports.consolidated`).
- **Company-defined roles**: the four built-ins remain, and an owner can create
  additional roles (name + ticked permissions) and assign them to members.
- Enforcement is by **permission**, resolved from the member's role.
- **Role-based only** — no per-user permission overrides (a deliberate
  simplification for predictability).

Non-goals: per-user overrides; cross-company roles; changing the platform-admin
(`admin`/`super_admin`) axis.

## 2. Model

### 2.1 Data model

New tables (company-scoped):

```
roles
  id            uuid pk
  company_id    uuid fk companies(id) on delete cascade
  key           varchar(60)            -- stable identifier: "owner", "manager", ..., "role_<slug>"
  name          varchar(80)            -- display name, owner-editable
  is_system     bool default false     -- built-ins cannot be deleted
  created_at    timestamptz
  unique (company_id, key)
  unique (company_id, name)

role_permissions
  role_id       uuid fk roles(id) on delete cascade
  permission    varchar(60)
  pk (role_id, permission)
```

`Membership.role` **stays a string** and becomes the role's `key`. This is the
key design decision that keeps the migration tractable:

- The many existing `Membership.role == "owner"` / `role.in_([...])` queries keep
  working unchanged (the owner key stays `"owner"`).
- Enforcement resolves `membership.role` → the company's `roles` row →
  `role_permissions`.

(Alternative considered: migrating to `Membership.role_id` FK. Rejected for now
because it forces a rewrite of every role comparison across `deps.py`, services,
schemas, and tests. The `key` approach is additive and reversible.)

### 2.2 Built-in roles (seeded)

Seeded per company (on setup and by the migration for existing companies). Their
permission sets reproduce today's hardened behavior:

| key | name | permissions |
|---|---|---|
| `owner` | Owner | `*` (all) — **immutable** |
| `manager` | Manager | sales + catalog + inventory + purchasing + reports + approvals + loyalty + dining + customers |
| `inventory_manager` | Inventory manager | catalog + inventory + purchasing + reports-view, plus approvals decide when rules allow |
| `cashier` | Cashier | sales, customers, held orders, own shifts, support |

Rules:
- The `owner` role is **immutable**: it always holds every permission (current
  `*`), cannot be renamed to another key, deleted, or have permissions removed.
  Company invariants (at least one owner; owner-only billing) rely on this.
- System roles can have their permission set edited, except `owner`.
- Custom roles (`is_system = false`) can be created/renamed/deleted.

### 2.3 Permission catalog

Stable keys grouped by domain, derived from the current endpoint guards
(`owner_roles`, `catalog_roles`, `require_roles(...)`) so the migration is
mechanical:

- **Sales:** `sales.create`, `sales.refund`, `sales.void_paid_order`,
  `sales.collect_balance`, `sales.discount`
- **Orders:** `orders.view`, `orders.cancel`
- **Customers:** `customers.manage`, `loyalty.redeem`, `loyalty.adjust`
- **Catalog:** `catalog.view`, `catalog.manage`
- **Inventory:** `inventory.view`, `inventory.manage`, `serials.manage`,
  `warranty.manage`, `trade_ins.manage`
- **Purchasing:** `purchasing.view`, `purchasing.manage`
- **Reports:** `reports.view`, `reports.consolidated`, `reports.gdt`
- **Approvals:** `approvals.decide`, `approvals.policy_manage`
- **Dining:** `dining.operate`, `dining.config`
- **Operations:** `shifts.manage`, `held_orders.use`, `notifications.send`
- **Workspace:** `team.manage`, `billing.manage`, `settings.manage`,
  `audit.view`, `support.use`

The catalog lives in `app/permissions.py` (one source of truth: key → label →
group), used by the API, the role editor UI, and tests.

## 3. Enforcement

- `app/permissions.py`: `PERMISSIONS` catalog + `resolve_permissions(db, membership)`
  returning the member's permission set (owner ⇒ all).
- `deps.py`: new `require_permission("catalog.manage")` dependency; owner passes
  automatically. `require_roles(...)` stays for the platform/owner invariants
  until Phase 3 replaces guards.
- `WorkspaceRead` gains `permissions: list[str]` so the client renders from the
  real permission set. The web `VIEW_ROLES` map becomes a fallback for older
  payloads and is progressively replaced by `can(permission)` checks.

Resolution is one indexed query per request (role lookup + permissions), cached
on `request.state` for the request’s lifetime. No JWT changes.

## 4. API

- `GET /permissions` — the catalog (key, label, group) for the editor. Any member.
- `GET /roles` — roles with their permissions. Any member.
- `POST /roles` — create a custom role (owner / `team.manage`; plan-gated).
- `PATCH /roles/{id}` — rename and/or set permissions (not for `owner`).
- `DELETE /roles/{id}` — delete a custom role with no members assigned (409 otherwise).
- `PATCH /team/{membership_id}` — already accepts a role; extend validation to
  accept any role key in the company.

Owner/`team.manage` gate, plan-gated by the `roles_permissions` capability
(rebranded "Multi-store staff access"). Built-in roles and the permission
*catalog* are free; **custom roles** are the paid part.

## 5. Web UI

`Settings → Team access`:
- Role list with permission counts; built-in roles shown with the seeded sets.
- Role editor: name + grouped permission checkboxes (from `GET /permissions`).
- Member editor: assign any company role.
- Non-owners with `team.manage` can manage roles; `owner` remains protected.

The workspace payload's `permissions` drives what each member sees (replacing the
current role-key checks over time).

## 6. Migration & backfill

One Alembic migration (chained to the current single head):
1. Create `roles` and `role_permissions`.
2. Insert the four built-in roles for every existing company.
3. Insert their default permission sets.
4. No change to `memberships` (the `role` string remains the key).

New companies get the built-ins seeded in `setup_workspace`. A data test asserts
every company has the four system roles and that `owner` holds all permissions.

## 7. Rollout phases (one PR each)

1. **Schema + catalog + resolution + payload.** Migration, `roles`/`role_permissions`,
   `app/permissions.py`, seed built-ins, add `permissions` to `WorkspaceRead`,
   `require_permission` dependency, tests. Default sets reproduce current behavior
   so nothing changes functionally.
2. **Roles API + validation.** CRUD endpoints, extend team update validation,
   plan gating.
3. **Role editor UI** in `apps/web`.
4. **Migrate endpoint guards** from `require_roles` to `require_permission`,
   preserving owner invariants; extend the role→endpoint matrix test to the
   permission model.
5. **Docs + plan copy** update.

## 8. Risks & open questions

- **Owner invariant:** keep `owner` immutable with all permissions (recommended).
- **Granularity:** the catalog above is endpoint-derived; it may be worth merging
  some keys (e.g. `sales.discount`) to keep the editor manageable.
- **Plan gating:** free plans keep the built-in roles; custom roles require the
  `roles_permissions` capability. Confirm.
- **Performance:** one extra query per request; acceptable, but cache the catalog.
- **Back-compat:** `Membership.role` stays a string, so nothing breaks
  immediately; the permission checks are additive.
- **Testing:** the existing role→endpoint matrix test becomes a
  permission→endpoint matrix test in Phase 4.

## 9. Out of scope

- Per-user permission overrides.
- Platform-admin (`admin`/`super_admin`) permissions.
- Cross-company/shared roles.

## 10. Implementation status

Shipped and merged (green CI):

| Phase | What | PR |
|---|---|---|
| Design | this document | #563 |
| 1 | `roles` + `role_permissions` model, permission catalog, `require_permission`, `WorkspaceRead.permissions`, migration | #566 |
| 2 | `GET /permissions`, `GET/POST/PATCH/DELETE /roles`, custom-role assignment | #571 |
| 3 | Settings → Team access role editor UI | #573 |
| 4 | permission-aware guards: catalog | #577 |
| 4 | inventory, serials, warranty, trade-ins, purchasing, refunds, orders, dining, notifications, loyalty | #580 |
| 4 | owner-level: team / billing / settings / approval-policy | #581 |

Every fixed-role guard in `app/api/v1.py` is now
`require_roles_or_permission(<built-in role tuple>, <permission>)`: the four
built-in roles behave exactly as before, and a company custom role gains access
through its permission set. The `owner` role remains immutable with all
permissions.

Remaining polish (not required for the feature to work):

- Use the company's custom roles in the member invite/edit **role dropdown** in
  the web UI (assignment already works through the API).
- An optional permission→endpoint matrix test mirroring the role matrix test.
- Company custom roles are plan-gated by the `roles_permissions` capability;
  the built-in roles stay free.

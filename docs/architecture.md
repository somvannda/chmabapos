# Chmabapos Architecture & Platform Restructure Plan

Status: Draft for review
Owners: Engineering
Scope: Repo layout, app boundaries, routing/hosting decisions, git & release workflow, and an incremental migration order. No code changes are made by this document.

## 1. Goal

Current state is a single React SPA at the repo root (`src/`) that contains the marketing website, auth flows, the full POS/user portal workspace, **and** the platform admin panel, all wired through one hand-rolled router (`src/routing.js`) and a monolithic `src/App.jsx`. The FastAPI backend lives in `backend/`.

Target state:

- A clear, versioned **monorepo** with one API project and two independent front-end apps.
- `chmabapos_api` (backend) isolated with its own config, migrations, and tests.
- One combined front-end app for **marketing website + user portal + POS** (same origin, same credentials — no subdomain split).
- A separate **admin control panel** app with its own build/deploy lifecycle.

## 2. Decisions (ADRs)

### ADR-001: Monorepo, not multiple repos
Single git repository until there is real, independent team velocity. A monorepo keeps API contract changes in the same PR as the consuming front-end, one version history, and cheap cross-app refactors. Each app still has a hard boundary so it can be extracted into its own repo later without code change.

### ADR-002: Website + portal + POS share one origin and one app
Users authenticate on the marketing site and continue into the workspace without leaving the origin. No cross-subdomain cookies, no CORS, no duplicated login. The `web` app is **one deployable** that routes internally:

| URL path | Section |
|---|---|
| `/` | Marketing site (landing, pricing, privacy/terms/contact) |
| `/login`, `/signup`, `/reset-password` | Auth |
| `/{workspace}/...` | User portal + POS (dashboard, pos, orders, catalog, inventory, reports, team, billing, settings) |

### ADR-003: Admin is a separate app
The admin panel is operationally and trust-wise different (platform-wide data, staff-only). It gets its own directory, own Vite build, and own deploy pipeline. It can be hosted on a separate subdomain (`admin.` ...) **or** under the same origin at `/admin` (recommended while the team is small) — see Deployment below. It authenticates the same JWT used by `web`, but only users whose token carries the platform-admin role may load it.

### ADR-004: Same-origin admin hosting (default, can change later)
To avoid a second login and duplicated token handling, serve the admin build at `/admin` on the same domain via the reverse proxy (separate build artifact directory). If admin usage grows, move it to `admin.` subdomain by changing only the host header config, not the app code.

### ADR-005: One API contract shared by both front-ends
FastAPI already exposes OpenAPI. Generate a TypeScript client from it (`openapi-typescript`/`openapi-fetch`) into a shared package so both apps can never drift from the backend. Hand-written `src/api.js` is replaced incrementally.

### ADR-006: URL design in `web` uses username-scoped workspace paths
Keep the existing scheme (`/{username}/{view}`) already implemented in `src/routing.js`. Replace the hand-rolled router with `react-router` but preserve the same public URL shapes so bookmarks and any early customers keep working.

## 3. Target repository layout

```
Chmaba/
├─ chmabapos_api/            # FastAPI backend (renamed from backend/)
│  ├─ app/
│  │  ├─ api/                # v1.py (tenant), admin.py (platform) — keep split
│  │  ├─ services/
│  │  ├─ models.py
│  │  ├─ schemas.py
│  │  ├─ config.py
│  │  └─ main.py
│  ├─ alembic/
│  ├─ scripts/
│  ├─ tests/
│  ├─ requirements.txt
│  └─ .env.example
├─ apps/
│  ├─ web/                   # marketing + auth + portal + POS (ADR-002)
│  │  ├─ src/
│  │  │  ├─ features/
│  │  │  │  ├─ marketing/
│  │  │  │  ├─ auth/
│  │  │  │  ├─ workspace/    # portal shell + routing
│  │  │  │  │  ├─ pos/
│  │  │  │  │  ├─ orders/
│  │  │  │  │  ├─ catalog/
│  │  │  │  │  ├─ inventory/
│  │  │  │  │  ├─ reports/
│  │  │  │  │  ├─ team/
│  │  │  │  │  └─ billing/
│  │  │  │  └─ admin-views/  # TEMPORARY during migration only
│  │  │  ├─ lib/             # shared api client, auth, theme (until shared pkg)
│  │  │  ├─ components/      # cross-feature UI primitives
│  │  │  └─ main.jsx
│  │  └─ package.json
│  └─ admin/                 # admin control panel (ADR-003)
│     └─ src/
│        ├─ features/        # overview, users, companies, stores, plans,
│        │                   # subscriptions, payment links, audit log
│        ├─ lib/
│        └─ main.jsx
├─ packages/
│  └─ api-client/            # generated TS client + types (ADR-005)
├─ docs/                     # this plan + ADRs
├─ .github/workflows/        # CI (lint, typecheck, tests, build) per app
├─ docker-compose.yml        # postgres + api + web + admin + mailhog
└─ README.md
```

## 4. What moves where

### 4.1 API (lowest risk, do first)
Move `backend/` -> `chmabapos_api/` with no code change. Update:
- Run commands in `backend/README.md` and `start-dev.ps1` (paths).
- `.gitignore` entries prefixed `backend/...` -> `chmabapos_api/...`.
- CI paths.

### 4.2 Admin panel (medium effort)
Current admin UI (nav: overview, users, companies, stores, subscriptions, plans, payments, audit) and its `admin.*` API calls live inside `App.jsx`/`PlatformAdmin` and route under `/admin`.
1. Copy the admin feature components into `apps/admin/` as a new Vite app.
2. Give it its own API client slice (only admin endpoints) + admin auth guard (decode JWT, require platform-admin).
3. Serve at `/admin` (ADR-004). Set Vite `base: "/admin/"`.

### 4.3 Web app (effort reduction first, feature split after)
1. Move current Vite app (`src/`, configs) into `apps/web/` unchanged. It keeps working today.
2. Extract the remaining `App.jsx` top-level UI (marketing, auth, workspace) into the `features/` folders; delete the admin sections now living in a temporary `admin-views/` folder once `apps/admin` is live.
3. Swap `routing.js` for `react-router` while preserving URL shapes (ADR-006).

## 5. API surface map (for contract/client generation)

Current routers (from `chmabapos_api/app/api/v1.py` and `admin.py`), grouped by domain — each becomes a client module in `packages/api-client`:

- **System**: `GET /health`
- **Auth**: register, verify-email, login, request/reset password, me (GET/PATCH), preferences, change-password
- **Workspace**: workspaces setup/current, company PATCH
- **Stores**: GET/POST/PATCH stores
- **Catalog**: categories CRUD, products CRUD + export/import
- **Inventory**: list/adjust, restock, transfers
- **Orders**: create, list, get, cancel, refunds, held orders, email receipt
- **Customers**: list/create/update/detail, points adjust/redeem
- **Purchases**: suppliers CRUD, purchases create/receive/cancel
- **Shifts**: list, open current, open/close
- **Settings**: currencies (GET/PUT), exchange-rates CRUD, quote
- **Reports**: summary, consolidated, GDT CSV
- **Billing**: plans, subscription, checkout, payments
- **Team**: memberships, invitations
- **Notifications**: list, read, read-all, low-stock summary (dev)
- **Payments**: `webhooks/cutluy` (signature-verified, public), mock complete (dev)
- **Audit**: audit-logs
- **Admin** (separate router): overview, users, companies, stores, payment-links, cutluy-settings, subscriptions, plans, audit-logs

## 6. Routing, config, secrets

- One API deployment serves both routers under `/api/v1` (tenant endpoints in `v1.py`, platform endpoints in `admin.py`). The admin app talks to the same origin.
- Per-app `.env.example`: `web` and `admin` use `VITE_API_URL`; `chmabapos_api` uses its existing `DATABASE_URL`, JWT secret, SMTP, CutLuy keys.
- No secrets in the repo. `.env` files stay gitignored. Logs go to gitignored locations (never the repo root).

## 7. Git & release workflow

- `git init` at the `Chmaba` root, trunk-based: short-lived branches off `main`, PR into `main`, protected `main` (require CI green).
- CI (GitHub Actions) runs on every PR: backend tests (pytest) + lint/typecheck, `web` build, `admin` build. Full workflow name: `ci.yml`.
- Releases: semantic versioning. Tag each deployable independently (`api-v1.2.0`, `web-v1.2.0`, `admin-v1.0.1`) or a single release tag with a changelog per app — pick one scheme and document it.
- DB schema versioning stays with Alembic; every release that changes the schema ships an Alembic revision.

## 8. Deployment topology (dev, then prod)

Dev (docker-compose): `postgres` + `mailhog` + `api` (uvicorn, reload) + `web` + `admin` (Vite dev servers with proxy to api).

Prod (single host, recommended to start):
```
browser
  -> https://chmaba.com (root)     -> apps/web build  (marketing + portal + POS)
  -> https://chmaba.com/admin/*    -> apps/admin build (static, SPA)
  -> https://api.chmaba.com/api/v1/* -> chmabapos_api (uvicorn/gunicorn behind proxy)
```
The customer app uses the main domain only (`chmaba.com`) — no `app.` subdomain.

## 9. Migration order (each step is shippable on its own)

1. **Git + CI**: init repo, `.gitignore`, `docs/` in place, minimal `ci.yml` (backend tests + web build).
2. **Rename backend** -> `chmabapos_api`, fix paths/scripts/README. CI now watches the new path.
3. **Move SPA to `apps/web`** unchanged; verify dev + build still work.
4. **Create `apps/admin`** as a second Vite app seeded from the admin feature code; keep `/admin` routing working in `web` (temporary copy) until admin deploy is verified.
5. **Ship admin at `/admin`**, then delete temporary `admin-views/` from `web`.
6. **Feature-split `web`** into `features/` + `react-router` (ADR-006). No URL changes.
7. **Generate `packages/api-client`** from OpenAPI; adopt in both apps.
8. **Prod deploy topology + docker-compose** documented and reproducible.
9. **CutLuy live + webhooks test** in the split topology before customer go-live.

## 10. Out of scope (for a later decision)

- Moving API to its own repo (kept possible by ADR-001).
- Admin on its own subdomain (ADR-004 keeps it a config change).
- Mobile/offline POS app (native) — if it appears, add as `apps/pos-mobile` sharing `packages/api-client`.
- i18n and design-token sharing between `web` and `admin` (recommend a `packages/ui` later once both apps exist).

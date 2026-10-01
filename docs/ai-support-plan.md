# AI Help & Support — Implementation Plan

Status: Draft for review
Owners: Engineering
Scope: In-app AI support assistant (floating panel + dedicated help page), a
vertical-aware help corpus, and the read-only tools the assistant may call.
This document plans the work; it makes no code changes.

Related: `docs/architecture.md` (repo layout, ADRs), `AGENTS.md` (git workflow).

## 1. Goal

Give a merchant a support surface inside `apps/web` that answers two kinds of
questions well:

1. **"How do I …?"** — procedural help ("How do I refund an order?", "How do I
   open a shift?") answered from a curated, versioned help corpus, tailored to
   the merchant's business type and role.
2. **"What is …?" / "How much …?"** — questions about the merchant's *own*
   data ("How many of SKU-123 are left?", "What were today's sales?") answered
   by calling existing read-only, tenant-scoped API endpoints.

Plus a concrete, step-by-step help library that stands on its own without AI.

## 2. Non-goals (this phase)

- No raw database / SQL access for the model. See ADR-101.
- No write actions ("create this product for me"). Those go through the
  existing `approval_requests` flow later, not the chatbot.
- No vector database / embeddings. The corpus is small; keyword + frontmatter
  matching is enough. Revisit only if the corpus grows past ~200 articles.
- No changes to `apps/admin` for this feature.

## 3. Architecture decisions

### ADR-101: Curated corpus + read-only tools, never raw DB access
Direct schema/table access is a tenant-isolation and correctness hazard: the
model can leak another company's rows, invent columns, and answer UI questions
worse by guessing at schema. Instead:

- Procedural answers come from the help corpus (no data access).
- Data answers come from **read-only, tenant-scoped** API calls executed by the
  backend on the caller's behalf, so the existing JWT + `X-Store-ID` +
  membership checks in `app/deps.py` enforce isolation for free.

### ADR-102: Reuse the existing AI provider plumbing
`app/services/ai.py` already handles provider selection (OpenAI / DeepSeek /
Claude), key storage in `platform_settings`, env fallbacks, and errors
(`AINotConfiguredError`, `AIError`). Support must reuse `load_ai_settings`,
`resolve_provider`, `provider_catalog`, and the error types — not a second
integration. Admins keep configuring the key once, in the existing AI settings
screen.

### ADR-103: Vertical-scoped content
Business type is already data: `Company.vertical` (validated against
`COMPANY_VERTICALS` in `app/schemas.py`). Help articles, starter questions and
seeded defaults are keyed by it. We extend the existing set rather than
introducing a parallel concept.

### ADR-104: One engine, two surfaces
A floating launcher (bottom-right, wired to the currently-unused `onHelp` prop
in `AppHeader`) and a dedicated page (`/{username}/help`) render the same
`<SupportChat>` component and share conversation state. The page is the panel
in a full-width layout plus an article browser.

### ADR-105: Stream answers over SSE
`ai.py::_call_provider` is non-streaming. Support adds a streaming sibling
(SSE) so answers appear progressively and long answers don't hit the reverse
proxy read timeout. A non-streaming fallback is kept for tests and providers
that fail to stream.

## 4. Existing assets to reuse

| Asset | Location | Use for support |
|---|---|---|
| AI provider client + settings | `app/services/ai.py` | Provider/dialect/key resolution, errors |
| AI settings API + UI | `app/api/admin.py`, `apps/admin` | Configure provider once |
| Business type field | `Company.vertical`, `CompanyUpdateRequest` | Tailor content |
| Plan feature catalog | `app/features.py` (`FEATURE_CATALOG`) | Only explain enabled features |
| RBAC | `workspace.jsx` `VIEW_ROLES`; `deps.require_roles` | Scope answers by role |
| Read-only store context | `app/deps.py::get_store_context_read` | Tenant-scoped data tools |
| `onHelp` prop (unused) | `workspace.jsx` `AppHeader`/`AppShell` | Launcher trigger |
| Tenant audit trail | `TenantAuditLog`, `app/services/activity.py` | Log support usage |

## 5. Data model changes

### 5.1 Extend business types
Current set in `schemas.py`:

```python
COMPANY_VERTICALS = {"general", "electronics", "coffee", "mart", "shop"}
```

Plan: add `restaurant`, keep existing codes for backward compatibility, and
document the mapping (`coffee` = café, `shop` = general retail). Optionally
introduce human labels in one place so the UI and help index agree:

```python
VERTICAL_LABELS = {
    "coffee": "Café / coffee shop",
    "restaurant": "Restaurant / food service",
    "mart": "Mart / grocery",
    "electronics": "Electronics store",
    "shop": "General retail shop",
    "general": "Other / general",
}
```

Validation stays a set membership check (extend the literal). No migration is
needed for the enum itself (it is a validated `String(20)`), but a data change
is not required.

### 5.2 Optional support tables (phase 3+, one Alembic revision)
Only if conversation history / feedback is wanted. Keep it minimal; chain
`down_revision` to the current single head (`alembic heads` must show one).

- `support_conversations`: `id`, `company_id`, `user_id`, `store_id?`,
  `created_at`, `updated_at`.
- `support_messages`: `id`, `conversation_id`, `role` (`user|assistant|tool`),
  `content`, `tool_name?`, `tool_payload?` (JSON), `created_at`.
- `support_feedback`: `id`, `message_id`, `rating` (`up|down`), `comment?`,
  `created_at`.

If we want zero schema churn at first, defer these and keep the assistant
stateless (client keeps the transcript). Recommend deferring to phase 3.

## 6. Backend design

### 6.1 New service: `app/services/support.py`
Responsibilities:
- `build_context(...)`: assemble the system prompt from company name,
  `vertical`, current store, caller role, and the plan's enabled features
  (`features.py`).
- `select_articles(query, *, vertical, role, limit)`: match the help index by
  frontmatter/keyword; return excerpts to ground the answer.
- `answer(...)`: call the provider (streaming) with the system prompt, retrieved
  excerpts, and a `tools` list.
- `run_tool(name, args, ctx)`: execute a whitelisted read-only tool using the
  caller's `StoreContext`; never accept a company/store id from the model.
- Reuses `ai.load_ai_settings`, `ai.resolve_provider`, `ai.AIError`,
  `ai.AINotConfiguredError`.

### 6.2 Provider call
Add `stream_completion(...)` to `app/services/ai.py` (or `support.py` using the
same provider metadata) that yields tokens. Anthropic uses SSE `/messages`;
OpenAI/DeepSeek use SSE `/chat/completions` with `stream: true`. Keep the
existing 45s timeout discipline; a stream resets the read timeout per chunk.

### 6.3 Tools (function calling)
Whitelist, all read-only and tenant-scoped via `get_store_context_read`:

| Tool | Backed by | Notes |
|---|---|---|
| `get_inventory_level` | inventory read endpoints | accepts product/sku name, not ids |
| `get_sales_summary` | `reports` summary | date range only |
| `list_low_stock` | inventory/notifications | |
| `get_order` | orders GET | order number |
| `list_products` | catalog list | search term |

Rules: the model may only pass business-level arguments; the company/store come
from `ctx`, never from the model. Every tool result is size-capped. Tools are
disabled when the relevant plan feature is off, and the model is told so.

### 6.4 Endpoints (tenant router `app/api/v1.py`, JWT-protected)
- `GET  /support/articles` — help index filtered by vertical/role.
- `GET  /support/starter-prompts` — personalized starter prompts.
- `POST /support/chat` — `text/event-stream`; request body carries the message
  and prior turns (or a conversation id once 5.2 lands).
- `POST /support/feedback` — rating for an answer (phase 3).

New Pydantic models in `app/schemas.py` next to the existing `AISettingsRead`
etc.: `SupportArticleRead`, `SupportStarterPromptRead`, `SupportChatRequest`,
`SupportChatChunk`, `SupportFeedbackRequest`.

### 6.5 Guardrails
- **Tenant isolation** comes from `deps.py`; tools never take ids from the model.
- **Rate limiting**: no limiter exists today. Add a small per-user/per-company
  limiter (in-memory token bucket is enough for one API instance; a DB-backed
  counter if we run multiple workers) and return `429` with a clear message.
- **Cost**: cap retrieved excerpt size, cap `max_tokens`, and cap turns per
  request. Provider key stays server-side (never returned — existing pattern).
- **Audit**: log `support.chat` to `TenantAuditLog`/`PlatformActivity`
  (metadata only, not full message bodies by default).
- **Escalation**: route "talk to a human" to the `priority_support` feature
  (already in `features.py`) instead of pretending the bot always answers.
- **Scope refusal**: instruct the model to decline non-Chmaba questions and
  never to invent prices/features; ground answers in retrieved articles.

### 6.6 Config
No new required env vars — reuse the `ai_*` settings. Optional knobs:
`support_max_turns`, `support_rate_limit_per_hour`, `support_retrieval_limit`
with safe defaults (add to `config.py`, document in `.env.example`).

### 6.7 OpenAPI
CI regenerates `chmabapos_api/openapi.json` and fails on drift. Every PR that
adds/changes endpoints must run:

```powershell
python chmabapos_api\scripts\export_openapi.py
```

and commit the updated `openapi.json` with the change.

## 7. Help content design

### 7.1 Location and format
Markdown under `docs/help/` (shipped in the repo, versioned with the feature it
documents), e.g.:

```
docs/help/
  pos/ring-up-a-sale.md
  pos/hold-and-resume.md
  inventory/restock.md
  inventory/low-stock.md
  products/serials-and-warranty.md      # electronics
  shifts/open-and-close.md
  purchasing/create-a-purchase-order.md
  reports/read-your-sales-summary.md
  team/invite-a-member.md
  billing/change-your-plan.md
```

Frontmatter:

```yaml
---
id: inventory.restock
title: Receive stock into a store
verticals: [coffee, restaurant, mart, electronics, shop, general]
roles: [owner, manager, inventory_manager]
feature_key: inventory_management   # optional; ties to features.py
order: 20
---
```

Body structure: **What it's for → Before you start → Steps → Tips →
Troubleshooting.**

### 7.2 Vertical mapping
Each vertical maps to: default categories (seeded at setup), recommended
features (from `FEATURE_CATALOG`), and a starter-prompt set. Example starters:

- **Café**: "Set up my menu", "Open my first shift", "Ring up a coffee sale".
- **Restaurant**: "Set up a table-friendly menu", "Handle split payments".
- **Mart**: "Add products with barcodes", "Restock low items", "Read today's sales".
- **Electronics**: "Add serial numbers and IMEI", "Track warranty", "Grade a used phone".

### 7.3 Authoring rules
- One task per article; imperative title; no screenshots required for v1.
- Keep each article ≤ ~300 words.
- Reference real UI labels from `NAV_ITEMS` / `pageMeta` so the assistant's
  answers match what the user sees.
- CI could later lint frontmatter (a small `node --test` or pytest check).

## 8. Frontend design (`apps/web`)

### 8.1 Onboarding: ask for business type
`features/onboarding.jsx` currently collects company, store, country, currency,
plan. Add a `vertical` dropdown to `SetupCompany`, seeded from the same list the
backend validates, and include it in the `PATCH /company` call (the request
already accepts and validates `vertical`, so no API change).

### 8.2 Routing and navigation
- `routing.js`: add `help` to `USER_PAGE_TO_VIEW` and `VIEW_TO_USER_PAGE`
  (`/{username}/help` ⇄ view `help`).
- `features/workspace.jsx`: add a `help` entry to `WORKSPACE_ITEMS`, add it to
  `VIEW_ROLES` (all roles), and add a `pageMeta.help` title/subtitle.
- Dispatch the view next to the other workspace views.

### 8.3 Components
- `components/SupportChat.jsx` — message list, input, starter prompts, article
  links; consumes the SSE stream. Shared by both surfaces.
- `components/SupportLauncher.jsx` — floating button (bottom-right, above the
  existing toast at `z-50`) that opens `SupportChat` in a side panel. Wire it
  to the existing `onHelp` prop; pass `activeView`, `storeId`, and
  `workspace.vertical` as context.
- `features/help.jsx` — dedicated `/{username}/help` page: full-width chat +
  searchable article browser + vertical "getting started" checklist.

### 8.4 API client
Add to `apps/web/src/api.js` using the existing `request` helper:

```js
supportArticles: (token, params = {}) => request(`/support/articles?${new URLSearchParams(params)}`, { token }),
supportStarterPrompts: (token, storeId) => request("/support/starter-prompts", { token, storeId }),
supportFeedback: (token, body) => request("/support/feedback", { ...json("POST", body), token }),
```

Streaming chat uses `fetch` directly (the helper buffers JSON) with
`Authorization` + `X-Store-ID` headers and reads the SSE body via
`ReadableStream`.

### 8.5 Frontend tests
Add `node --test` coverage for any pure helpers (SSE parsing, starter-prompt
selection). e2e (Playwright) smoke: open the launcher, ask a starter question,
assert an answer region renders (mock the API in the test).

## 9. Phased delivery (one branch/PR each)

Each phase is independently shippable and keeps CI green.

### Phase 1 — Help content + static help page (no AI)
- Extend `COMPANY_VERTICALS` with `restaurant`; add `VERTICAL_LABELS`.
- Add `docs/help/**` and a small help index loader.
- Onboarding vertical field.
- `/{username}/help` page + searchable article browser + floating launcher
  showing articles only.
- **Branch**: `feat/help-center-static`.

### Phase 2 — AI Q&A over the corpus
- `app/services/support.py` + `/support/articles`, `/support/starter-prompts`,
  `/support/chat` (non-streaming first).
- Retrieval by frontmatter/keyword; system prompt from company/vertical/role/
  plan features.
- `SupportChat` wired to the API; regenerate `openapi.json`.
- **Branch**: `feat/ai-support-qa`.

### Phase 3 — Data tools + streaming + feedback
- SSE streaming for `/support/chat`.
- Read-only tools via `get_store_context_read`.
- Rate limiting; `support_*` tables + migration; `/support/feedback`.
- Escalation to `priority_support`.
- **Branch**: `feat/ai-support-tools`.

## 10. Testing & CI checklist

- API: pytest for `support.py` (prompt composition, retrieval selection, tool
  argument validation, refusal of non-whitelisted tools, tenant scoping). Mock
  the provider with `httpx` mock — never call a real provider in CI.
- Regenerate and commit `chmabapos_api/openapi.json`.
- Web: `npm test` (pure helpers) and `npm run build`.
- Admin: unchanged (still must build).
- e2e: add a mocked support-panel smoke test.
- Migration PRs: `alembic heads` must show exactly one head.

## 11. Risks & open questions

1. **Rate limiting design** — in-memory vs DB-backed depends on whether the API
   runs multiple workers/instances. Decide before phase 3.
2. **Conversation storage** — stateless (client-held transcript) vs DB. Affects
   the 5.2 tables and privacy posture. Recommend stateless at first.
3. **Language** — Khmer is present in the app fonts; decide whether the
   assistant must answer in Khmer and whether articles are bilingual.
4. **Content ownership** — who authors/approves `docs/help/**`? Treat it like
   code (PR review) per `AGENTS.md`.
5. **Provider cost/latency** — set the token and turn caps in 6.5 before beta.
6. **Escalation channel** — where does "talk to a human" actually go (email,
   Telegram, ticket)? `priority_support` exists as a feature flag only today.

## 12. Suggested first PR

Phase 1 only: vertical onboarding field + `docs/help/**` skeleton for **café,
mart, and electronics** + static `/{username}/help` page and launcher. It
delivers real value with no AI cost, and it produces the corpus the assistant
needs in phase 2.

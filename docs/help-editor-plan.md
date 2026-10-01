# Admin Help Editor — Implementation Plan

Status: Draft for review
Owners: Engineering
Scope: Let platform admins edit the in-app help content without a code deploy.
This document plans the work; it makes no code changes.

Related: `docs/ai-support-plan.md`, `chmabapos_api/app/support_content.py`.

## 1. Goal

Today the help corpus lives in `chmabapos_api/app/support_content.py` (English)
and its Khmer overlay (`KH_TRANSLATIONS`, `STARTER_PROMPTS_KM`). Changing a step
means a code change + PR + deploy. The goal is a platform-admin surface where ops
can edit article titles, steps and tips (in English and Khmer) and see changes
live, with review and fallback safety.

## 2. Non-goals (this phase)

- Rich text / images / video embeds.
- Multi-version history and one-click revert (phase 2; see §8).
- Merchant-authored content (platform admins only).
- Translations beyond English and Khmer.

## 3. Current state (read this before changing anything)

- `support_content.SUPPORT_SECTIONS` is the authored corpus; `articles_for()` /
  `starter_prompts_for()` are **pure, synchronous** functions.
- `GET /support/articles` and `GET /support/starter-prompts` call them directly.
- `app/services/support.py::build_prompt()` is **synchronous** and calls
  `articles_for()`; it is shared by the one-shot and streaming chat paths.
- Tests (`test_support_content.py`, `test_support_eval.py`) assert on the static
  corpus and on keyword retrieval behaviour.

## 4. Design decision: DB-backed, seeded, with a static fallback

Store articles in a `help_articles` table that becomes the source of truth; seed
it from the current static module via a data migration. Keep the static module as
the **fallback baseline** so a missing/empty table never breaks the help center or
the assistant.

Rejected alternatives:
- **Overrides-only table** (base in code, DB overrides on top): less duplication
  but two places to reason about and awkward for adding new articles.
- **Full DB with no static base**: a bad migration or manual row deletion becomes
  an outage; the fallback is cheap insurance.

## 5. Data model

`help_articles` (one row per article; sections are a grouping field, not a table):

| column | type | notes |
|---|---|---|
| `id` | text PK | stable slug, e.g. `inventory.restock` (matches today's ids) |
| `section_id` | text | e.g. `inventory` |
| `section_title` | text | English section title |
| `section_title_km` | text null | Khmer section title |
| `section_blurb` | text | English blurb |
| `section_blurb_km` | text null | |
| `title` | text | English |
| `title_km` | text null | |
| `steps` | JSON | list[str], English |
| `steps_km` | JSON null | list[str] |
| `tip` | text null | |
| `tip_km` | text null | |
| `verticals` | JSON | list[str] |
| `roles` | JSON | list[str] |
| `position` | int | ordering within a section |
| `is_active` | bool | hide without deleting |
| `updated_at` | timestamptz | |
| `updated_by` | uuid null → users.id | |

Starter prompts get a small companion table `help_starter_prompts`
(`id`, `vertical`, `language`, `prompt`, `position`, `is_active`), seeded from
`STARTER_PROMPTS` / `STARTER_PROMPTS_KM`.

## 6. Serving refactor

1. **Repository module** `app/services/help_repo.py`:
   - `async def load_articles(db) -> list[Article]` (active rows, ordered).
   - `async def load_starter_prompts(db, vertical, language)`.
   - In-process cache with a short TTL (e.g. 30s) plus a bump on admin write, so
     reads are cheap and edits appear quickly. Single-process is fine now; if the
     API scales, the TTL bounds staleness.
   - If the table is empty/unavailable, return the static corpus (fallback).
2. `articles_for` / `starter_prompts_for` gain an **async DB-backed** sibling
   (`articles_for_db`, `starter_prompts_for_db`) or become async with a `db`
   argument. Prefer explicit async functions to keep the pure helpers (and their
   tests) intact as the fallback path.
3. `support.build_prompt()` becomes **async** (it needs the DB) — or takes the
   already-loaded guide list. Preferred: split it — `build_prompt(..., guides=...)`
   stays pure, and callers load guides first. This keeps the streaming path and
   tests simple.
4. Endpoints `/support/articles` and `/support/starter-prompts` read via the repo.
5. `support.answer` / `stream_answer` load guides via the repo before building the
   prompt.

## 7. Admin API + UI

- `GET /admin/help/articles` — list (incl. inactive), for the editor.
- `POST /admin/help/articles` — create.
- `PATCH /admin/help/articles/{id}` — update fields (title/steps/tip per language,
  verticals/roles/position/is_active).
- `DELETE /admin/help/articles/{id}` — soft delete (`is_active = false`).
- `POST /admin/help/preview` — optional: render for a vertical/role.
- Every write calls the existing `audit()` helper (`admin.help_article_updated`
  etc.) and bumps the repo cache.
- Admin UI: a new **Support → Content** view in `apps/admin` mirroring the existing
  list/editor patterns; bilingual fields side by side; a "preview as" selector.

## 8. Phasing (each independently shippable)

1. **Table + seed + read path with fallback.** Migration + `help_repo` + switch the
   read endpoints and `build_prompt` to DB, falling back to static. No UI. Verify
   with the existing content/eval tests (they must stay green against the seed).
2. **Admin API.** CRUD + audit + cache bump, with tests.
3. **Admin UI.** Support → Content view.
4. **Versioning (optional, later):** append-only `help_article_revisions` + revert.

## 9. Risks & mitigations

- **Async refactor of `build_prompt`** touches the chat/stream paths and tests.
  Mitigate by keeping `build_prompt` pure and loading guides at the call site.
- **Drift between static fallback and DB seed**: seed is generated from the same
  module, and a test asserts the seeded DB yields the same guide ids/ordering as
  the static corpus.
- **Cache staleness**: TTL + explicit bump on write.
- **Migration on an existing corpus**: purely additive (new table); safe rollback.
- **Translations**: nullable `_km` columns fall back to English exactly as today.

## 10. Test plan

- Seeding test: after migration, `load_articles` matches `SUPPORT_SECTIONS` ids
  and ordering; Khmer fields match `KH_TRANSLATIONS`.
- Read-path test: endpoints return DB content; when the table is emptied, they
  fall back to the static corpus.
- Retrieval/eval tests (`test_support_eval.py`) continue to pass against the DB
  path.
- Admin CRUD tests (create/update/soft-delete, audit row written, cache bumped).
- Regenerate `openapi.json` for the new admin endpoints.

## 11. Open questions

1. Should ops edit `verticals`/`roles` per article, or only text? (Recommend text
   first; expose verticals/roles later.)
2. Is a 30s cache acceptable, or do edits need to be instant? (Instant = bump the
   cache on write, which we already plan.)
3. Do we need a "draft" state, or is `is_active` enough for v1?

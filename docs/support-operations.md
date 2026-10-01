# Support & Help — Operations Runbook

How to configure, operate and troubleshoot the in-app help center and the AI
support assistant. For the design history see `docs/ai-support-plan.md` and
`docs/help-editor-plan.md`.

## What's included

- **Help center** (`/{username}/help` in the web app): a searchable, business-type
  aware guide library, available in English and Khmer.
- **AI support assistant** (same page): grounded, streaming answers with cited
  guides, plus answers about the merchant's own stock/sales.
- **Support insights** (admin panel): answer feedback and the questions that need
  attention.
- **Help content editor** (admin panel): edit guides without a deploy.

## Configure the assistant

The assistant reuses the platform AI settings — the same ones the Mailing tool
uses.

- **Admin panel → Settings → AI writing**: choose a provider (OpenAI / DeepSeek /
  Claude), model, and API key. The key is stored in `platform_settings` and never
  returned to the browser.
- Use **Test** to validate the key.
- Env fallbacks (used when no DB setting is present): `AI_PROVIDER`, `AI_API_KEY`,
  `AI_MODEL`, `AI_BASE_URL`.
- If nothing is configured, the chat endpoint returns **400** with a fixable
  message (not a 502).

## Edit help content

- **Admin panel → Help content**.
- Create / edit / deactivate articles. Fields: section id/title/blurb, title,
  steps (one per line), tip, verticals, roles, position, active — each with an
  optional Khmer counterpart.
- **Changes apply immediately** to both the help center and the assistant (no
  cache; no deploy). Deactivation is a soft delete (`is_active = false`) and is
  reversible with **Restore**.
- Every write is recorded in the audit log (`admin.help_article_created/_updated/
  _deleted`).
- The `help_articles` table is seeded from `app/support_content.py`; that module
  remains the fallback if the table is ever empty, so the help center never
  breaks.

## How the assistant is grounded

1. **Help corpus** — articles are filtered by the company's `vertical` and the
   caller's role, and localized to the requested language. Answers cite the
   matched guides, which render as clickable chips in the UI.
2. **Live store data** (read-only) — for stock/sales questions the backend runs a
   small, fixed set of store-scoped queries (`app/services/support_tools.py`) and
   injects the result. The model never runs SQL and never writes data.
3. **Conversations** are persisted (`support_conversations` / `support_messages`)
   so a merchant can resume a chat.
4. **Escalation** — "Talk to a human" records a platform activity (forwarded to the
   ops Telegram group), flagged for `priority_support` workspaces.

## Guardrails & configuration

| Setting | Default | Meaning |
|---|---|---|
| `support_rate_limit_per_hour` | 60 | Per-user chat requests per hour (in-process). |
| `support_max_question_chars` | 1000 | Truncates an over-long question. |
| `support_max_history_turns` | 8 | History turns sent to the provider. |
| `support_max_output_tokens` | 800 | Cap on the answer length. |

The rate limiter is **per API process**; if the API scales to multiple workers,
move it to shared storage.

## Support insights

- **Admin panel → Support**: helpful / not-helpful counts, satisfaction rate,
  escalations, "questions needing attention" (ranked by down-votes), and recent
  feedback over a 7/30/90/365-day window.
- Feedback is captured from the thumbs up/down in the chat and stored as
  `support.feedback` platform activities (not forwarded to Telegram).

## Health & troubleshooting

- **Assistant unavailable / errors**: check the AI provider and key (Admin →
  Settings → AI writing → Test).
- **Help page error**: the web bundle and API must be from compatible releases;
  redeploy after merging web changes.
- **Answers ignore an edit**: confirm the article is **Active** in Help content.
- **429 from chat**: the caller hit the hourly limit.

## Deployment notes

- New migrations ship with the API release: `alembic -c chmabapos_api/alembic.ini
  upgrade head`. `alembic heads` must show exactly one head.
- `chmabapos_api/openapi.json` is committed; regenerate with
  `python chmabapos_api/scripts/export_openapi.py` whenever endpoints change
  (CI fails on drift).

## Where the code lives

- Corpus + localization: `chmabapos_api/app/support_content.py`
- Chat service + grounding: `chmabapos_api/app/services/support.py`
- Read-only data tools: `chmabapos_api/app/services/support_tools.py`
- Help read path: `chmabapos_api/app/services/help_repo.py`
- Provider client: `chmabapos_api/app/services/ai.py`
- Endpoints: `chmabapos_api/app/api/v1.py` (tenant support routes) and
  `chmabapos_api/app/api/admin.py` (insights + help CRUD)
- Web help UI: `apps/web/src/features/help.jsx`, `apps/web/src/components/SupportChat.jsx`
- Admin UI: `apps/admin/src/App.jsx` (`AdminHelpContent`, `AdminSupportInsights`)

## Deployment order reminder

Merge → confirm CI green on `main` → the Deploy workflow runs automatically
(`workflow_run` after CI on `main`) → verify the live bundle changed. A green CI
does **not** mean deployed.

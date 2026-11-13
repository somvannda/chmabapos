# Support & Help — Operations Runbook

How to configure, operate and troubleshoot the in-app help center and the AI
support assistant. For the design history see `docs/ai-support-plan.md` and
`docs/help-editor-plan.md`.

## What's included

- **Help center** (`/{username}/help` in the web app): a searchable, business-type
  aware guide library, available in English and Khmer.
- **AI support assistant** (same page): grounded, streaming answers with cited
  guides, plus answers about the merchant's own stock/sales.
- **Live support chat** (web POS and admin panel): one realtime thread where the
  assistant answers first and a human can join the same conversation. Hand-offs
  page the internal Telegram group with a deep link.
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
3. **Conversations** are persisted in the live support thread
   (`support_chat_conversations` / `support_chat_messages`), so the floating
   assistant, the Support page and the ops inbox all resume the same conversation.
   The older `support_conversations` / `support_messages` tables still hold
   historical chats created before the unification.
4. **Escalation** — "Talk to a human" hands the same thread to the ops inbox and
   pages the Telegram group, with a `priority_support` flag when the plan includes it.

## Guardrails & configuration

| Setting | Default | Meaning |
|---|---|---|
| `support_rate_limit_per_hour` | 60 | Per-user chat requests per hour (in-process). |
| `support_max_question_chars` | 1000 | Truncates an over-long question. |
| `support_max_history_turns` | 8 | History turns sent to the provider. |
| `support_max_output_tokens` | 800 | Cap on the answer length. |

The rate limiter is **per API process**; if the API scales to multiple workers,
move it to shared storage.

## Live support chat

The merchant opens **Support → Live chat** (`/{username}/support`). The thread
starts in **Assistant** mode: `/support/chat/conversations/{id}/ask` streams a
grounded answer into the same thread. **Talk to a human** moves the thread to
**Waiting** and alerts the ops group; an agent reply moves it to **Live**. The
merchant keeps every message and the assistant's answers when a human joins.

The floating **Ask Chmaba** panel on any workspace page is the same thread, not a
separate assistant history: it resumes the caller's own latest conversation
(`mine=1`). A question asked there is already visible in the ops inbox before the
merchant ever asks for a human.

### Operate it

- **Admin panel → Support → Live chat** lists conversations (All / Waiting /
  Live / Assistant / Mine). Open one to see the merchant, workspace, store,
  assignee and the full assistant transcript.
- **Take over** claims the thread and moves it to Live. **Resolve** closes it;
  a new merchant message reopens it. **Prioritise** pins it to the top. **Notes**
  holds internal context the merchant never sees.
- **Suggest from assistant** drafts a reply from the help corpus. It flags when
  no guide matched, which is a signal to add one.
- Replies reach the merchant's in-app chat immediately and ring their
  notification bell with a link back to the thread.
- Owners and managers see every workspace thread; a cashier or custom role sees
  only the threads they opened, so billing conversations stay with management.

### Telegram hand-off

A hand-off records a `support.chat_handoff` platform activity and forwards it to
the group configured by `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`. The alert names
the workspace, store, reference, topic and last message. When `PLATFORM_ADMIN_URL`
is set it also includes a link to the thread:

```
{PLATFORM_ADMIN_URL}/support?conversation=<conversation id>
```

Alerts are **one per unanswered burst**. The first hand-off (or the first
merchant message of a new burst) sets `agent_alert_pending`; an agent reply
clears it. Further messages while it is set do not page again, so a chatty
merchant cannot flood the group. If Telegram is unconfigured the send is a
no-op and the thread still appears in the admin list.

### Realtime contract

History loads over REST, then the client streams
`GET .../support/chat/conversations/{id}/stream?after_seq=<last seq>`. The
stream polls a database identity column, so the API stays single-process with no
broker; `after_seq=0` means "from now". Reconnect with the newest `seq` and
nothing is missed or replayed.

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
- **A hand-off did not page Telegram**: confirm the bot token and chat id are
  set on the API host, then check the ops activity feed for
  `support.chat_handoff`. An alert is sent once per unanswered burst; a duplicate
  merchant message intentionally does not page again.
- **The "Open" link is missing from a Telegram alert**: set `PLATFORM_ADMIN_URL`;
  without it the alert still carries the reference.
- **Merchant does not see an agent reply**: the thread's status must be Live;
  check the admin conversation and the merchant's notification bell. A thread
  whose store was deleted has no bell entry (notifications are store-scoped) but
  the reply is still in the thread.

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
  `chmabapos_api/app/api/admin.py` (insights, help CRUD, live chat ops)
- Live chat service: `chmabapos_api/app/services/support_chat.py`
- Live chat tables: `support_chat_conversations`, `support_chat_messages`
  (migration `d1f3a7c9e2b4`)
- Web help UI: `apps/web/src/features/help.jsx`, `apps/web/src/components/SupportChat.jsx`
- Web live chat: `apps/web/src/features/supportChat.jsx`,
  `apps/web/src/features/support.jsx`
- Admin UI: `apps/admin/src/App.jsx` (`AdminHelpContent`, `AdminSupportInsights`,
  `AdminSupportChat`)
- Design notes: `docs/support-live-chat-plan.md`

## Deployment order reminder

Merge → confirm CI green on `main` → the Deploy workflow runs automatically
(`workflow_run` after CI on `main`) → verify the live bundle changed. A green CI
does **not** mean deployed.

# Live support chat — design & status

Status: implemented on `feat/support-live-chat` (API, web POS, admin inbox,
Telegram hand-off). Android and iOS are a follow-up.

Related: `docs/support-operations.md`, `docs/storefront-chat-improvements.md`,
`docs/ai-support-plan.md`.

## Why

Merchants already had two support surfaces: the **Ask Chmaba** assistant and an
email-based **support ticket**. Neither was a conversation the team could join
while the merchant was at the counter. Ask Chmaba answered into its own history;
a ticket arrived later and asked the merchant to repeat the issue.

Live support chat makes the assistant and a human share **one thread**:

1. the merchant asks the assistant and gets an immediate answer;
2. if that is not enough, "Talk to a human" moves the same thread into the ops
   inbox and pings the internal Telegram group;
3. an agent opens the thread with the assistant's answers already in front of
   them and replies in real time.

The email ticket flow is unchanged and remains the fallback for long-form or
off-hours requests.

## Data model

Two additive tables, shaped like `store_chat_*` so the proven realtime pattern
is reused:

- `support_chat_conversations` — reference (`SUP-XXXXXX`), company, store,
  merchant user, subject, status, priority, assigned admin, internal notes,
  last-message denormalisation, per-side unread counts, read/delivered stamps,
  hand-off time, and `agent_alert_pending`.
- `support_chat_messages` — `seq` identity cursor, author type
  (`merchant`/`assistant`/`agent`/`system`), body, one attachment, guide ids,
  timestamps.

Lifecycle:

| Status | Meaning | Next |
|---|---|---|
| `ai` | Assistant answering; ops can read but not interrupt | merchant asks for a human → `waiting`; any agent reply → `live` |
| `waiting` | Hand-off alerted; merchant can keep typing | agent reply → `live`; merchant closes → `closed` |
| `live` | A human is in the conversation | resolve/close; a new merchant message reopens |
| `resolved` / `closed` | Finished | any merchant message reopens to `waiting` or `live` |

Unread counters describe the **other** side: a merchant message increments
`agent_unread_count` only while the thread is `waiting`/`live`; an agent reply
increments `merchant_unread_count`. Assistant turns never raise a badge.

## Realtime

REST returns history; an SSE stream over `after_seq` delivers new turns:

- `GET /api/v1/support/chat/conversations/{id}/stream`
- `GET /api/v1/admin/support/chat/conversations/{id}/stream`

`after_seq=0` means "from now"; both clients load history first and then start at
the newest `seq`, so a reconnect misses nothing and replays nothing. Polling
inside the stream keeps the API single-process with no broker, matching the
storefront chat decision.

## Telegram hand-off

`POST /support/chat/conversations/{id}/handoff`:

- moves the thread to `waiting`, stamps `handoff_requested_at`, increments the
  ops unread count;
- records a `support.chat_handoff` platform activity and forwards it to the
  configured Telegram group, with company, store, reference, topic, the last
  message, and a deep link when `PLATFORM_ADMIN_URL` is set:
  `{PLATFORM_ADMIN_URL}/support?conversation=<id>`.

Cadence is **one alert per unanswered burst**, tracked by
`agent_alert_pending`: the hand-off sets it; an agent reply clears it; further
merchant messages while it is set do not page again. A merchant message after a
reply starts a new burst and pages once.

If Telegram is not configured, the alert is a no-op; the thread still appears in
the ops inbox.

## Surfaces

### Merchant (`apps/web`)

- **Support → Live chat** is the default tab; **Requests** keeps the email-ticket
  form and history.
- Thread list with status, unread and preview; thread view with assistant,
  agent and merchant bubbles, live updates, typing indicator, attachments,
  "Talk to a human", close.
- A support unread badge on the sidebar; agent replies also ring the existing
  notification bell and link to `support?conversation=<id>`.
- The floating **Ask Chmaba** panel's "Contact support" carries its recent turns
  into a new live thread, so the agent starts with context.

### Ops (`apps/admin`)

- **Support → Live chat** is the default tab; **Tickets & insights** is unchanged.
- Lists AI-only, waiting, live and resolved threads; filters for waiting/live/AI
  and "mine"; search is a follow-up.
- Thread view shows the merchant, workspace, store, assignee and internal notes;
  actions: take over, prioritise, resolve/reopen, AI-suggest a reply, send a
  reply. A Telegram deep link opens the right thread.

## Configuration

| Setting | Effect |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Enable Telegram alerts (shared with all ops alerts). |
| `PLATFORM_ADMIN_URL` | Adds the "Open" deep link to a hand-off alert. Without it the alert still names the reference. |
| AI provider settings | Used by `/support/chat/conversations/{id}/ask` and the agent's "Suggest from assistant". |

## Access rules

- Merchant endpoints are company-scoped. Owners and managers see every workspace
  thread; a cashier or custom role sees only threads they opened, so an owner's
  billing conversation is not readable from the till account. A different
  company gets `404`, not a partial read.
- Ops endpoints require `get_platform_admin`; a merchant token gets `401/403`.
- Attachments are images/documents under the platform media prefix; the merchant
  composer uploads through `/support/chat/upload`, the agent through
  `/admin/support/chat/upload`.

## Tests

`chmabapos_api/tests/test_support_chat.py` covers:

- hand-off → waiting, agent reply → live, the merchant sees the agent's name, and
  the merchant bell is written with the thread link;
- company isolation, the cashier-only-own-threads rule and the platform-admin
  gate;
- Telegram hand-off content and the once-per-unanswered-burst rule;
- a closed thread reopening on a new merchant message.

## Follow-ups

- **Android and iOS** live chat (API is ready; each native app needs a screen).
- **Search** across live conversations in the ops inbox (status/assignee filters
  exist today).
- **Surface the floating assistant's own `support_conversations` history** in the
  ops inbox for questions that never reach a hand-off. Today the live thread and
  the widget's older AI history are separate stores; the hand-off transcript is
  what an agent sees.
- **Agent presence** ("Dara is viewing") beyond the existing typing indicator.

# Storefront chat — improvements

The chat shipped in #847: a floating widget on a store page, a customer inbox in
the account, a seller **Inbox** in the workspace, text/photos/documents/voice,
emoji reactions, and SSE delivery over an `after_seq` cursor. Guests are
identified by an unguessable `visitor_token`; a signed-in shopper claims the
thread they started.

This is the agreed backlog for what comes next. It is ordered so that the
cheapest things that make the feature *trustworthy* land first; capability comes
after. Everything below item 12 is still open; the status of the rest is noted
here.

## Status

- **Phase 1 (items 1–7) — shipped** (#864, #865), plus a follow-up that anchors
  the widget and hides the seller's real name from the customer (#865, #867).
- **The seller label — shipped** (#870): the store can name a thread from the
  inbox; the label is private to the store.
- **The reliability tier (items 8–12) — shipped**: unanswered-message email
  alert, new-message sound, idle auto-close, and scrollback paging.
- **Canned replies (item 14) — shipped**: save a reusable reply per store and drop
  it into a thread with a tap.
- **Items 13, 15–26 — open.**

## Two things to know before reading

**The guest name is never captured.** `POST .../chat/messages` accepts a `name`
and the API stores it as `guest_name`, but `StoreChat` never sends one — so every
conversation arrives in the inbox as "Guest". Item 4 fixes this, and it is the
reason the seller cannot tell two customers apart today.

**Realtime assumes a single process.** Delivery is DB polling inside the SSE
handler, so there is no broker. True today (the API image sets no `--workers`).
Items 16 and 25 are the ones that would change this.

## Phase 1 — quick wins

Small diffs, high trust. Ship as one PR.

1. **Hide the "Ask Chmaba" launcher on the chat inbox.** A support launcher
   floating over the conversation list is confusing. `SupportLauncher` already
   accepts a `hidden` prop, so this is one condition in `workspace.jsx`
   (`activeView === "inbox"`).
   *Done when:* the launcher is absent on `/{username}/inbox` and unchanged elsewhere.

2. **Say "Chat with the store", not "Chat".** The launcher's visible label is
   terse, ambiguous next to the "Ask Chmaba" support launcher, and hidden on
   phones (`hidden sm:inline`) — so exactly the users most likely to be confused
   see only an icon. Use "Chat with the store" and show it at every width.
   *Files:* `apps/storefront/app/components/StoreChat.jsx`.
   *Done when:* the label reads unambiguously on a 360px-wide phone and the
   button still clears the fixed cart bar.

3. **Images open in a modal, not a new tab.** Both clients render
   `<a target="_blank"><img/></a>`, which throws the customer out of the
   conversation. Replace with an overlay: click to enlarge, click or `Esc` to
   close, no navigation.
   *Files:* `apps/storefront/app/components/ChatThread.jsx`,
   `apps/web/src/features/inbox.jsx`.
   *Done when:* opening and closing an image never changes the URL.

4. **Capture the guest's name.** Add an optional "Your name" field to the widget,
   sent with the first message (`name` on the send payload). Signed-in shoppers
   already supply it from their account.
   *Files:* `StoreChat.jsx`; `lib/chat.js` to remember it in the visitor record.
   *Done when:* a new guest thread shows the typed name in the inbox list and
   thread header, not "Guest".

5. **Show who is who in the thread.** Label the customer's messages with their
   guest or shopper name, and seller messages with the replying person's name
   (`sender_user_id` is already stored — join to `users`). Needed the moment two
   staff share the inbox.
   *Files:* `services/store_chat.py` (author name in the message payload),
   `ChatThread.jsx`, `inbox.jsx`.
   *Done when:* a two-seller thread reads unambiguously.

6. **Stop promising a fast reply when the store is shut.** The header always says
   "Usually replies within a few minutes". Use the store's own open state
   (`store_open_state`, already exposed as `is_open`) to say "Closed now — we'll
   reply when we open" instead.

7. **Links and phone numbers are clickable.** A pasted map link is dead text
   today. Detect URLs (`https://`, `www.`) and phone numbers; render anchors and
   `tel:` links, `rel="noopener noreferrer"`, never `javascript:`.
   *Done when:* a message containing a URL yields a working link in both clients.

## Phase 2 — reliability

This is what decides whether the feature actually works in a busy shop.

8. **Email the owner/manager when a message goes unanswered.** The in-app bell
   only helps someone already looking at the app; a store that closes at 6pm
   should still learn at 7pm that a customer is waiting. Scan for conversations
   with `seller_unread_count > 0` older than N minutes and queue a note through
   the existing `email_sends` outbox. Needs a marker column
   (`seller_notified_at`) so a repeated scan does not re-send, and a per-store
   toggle in `store.preferences`.
   *Done when:* an unanswered message produces exactly one email, and settling it
   produces none.

9. **New-message sound in the POS inbox.** Merchants at the counter will not
   watch a badge. Reuse the existing `sale_sound` preference pattern; make it
   opt-in and never autoplay-blocked into silence.

10. **Idle threads close themselves.** `status` exists but nothing sets it. Close
    after ~3 days of silence and reopen on the next message, so "Open" means
    something. Cheapest correct place is a lazy sweep when the list is read,
    rather than a new background worker.

11. **Scrollback past the first page.** `_chat_thread_messages` returns the last
    200 only; older messages are unreachable. Add `before_seq` paging and a
    "Load earlier" control.
    *Done when:* a 500-message thread can be read from the top.

12. **Per-conversation send guard.** The blanket public limit (10 writes/min per
    IP) is coarse: it punishes a chatty customer and does not stop one thread
    being flooded from many IPs. Add a per-conversation cap and dedupe an
    identical message sent twice within a second (double-tap on Send).

## Phase 3 — capability

Only after Phase 2 has been in a real store for a while.

13. **Order cards.** "Where's my order?" is the likeliest question. `kind="order"`
    plus a nullable `order_id`, rendered as a card linking to the existing
    `/order/<public_token>` page, with a "recent orders" picker for the seller.

14. **Canned replies.** Opening hours, delivery area, returns — one tap. Highest
    time-saved per line of code, and it makes fast replies realistic at a counter.

15. **Read receipts.** "Seen" stops duplicate messages. Design decision to settle
    first: a read timestamp per side, or simply surfacing the existing unread
    counters to the other side.

16. **Typing indicators.** In-process state keyed by conversation, delivered as an
    SSE event. Explicitly single-process; do not build this if item 25 is on the
    horizon.

17. **Claim and internal notes.** Two staff answering the same thread is already
    possible. Add "handled by" and a notes field invisible to the customer.

18. **Email the customer when the store replies.** Guests lose the thread if they
    clear storage, and will not see a reply with the tab closed. Optional email on
    the first message, then a "the store replied" note.

19. **Analytics.** Conversations started, median first-reply time, resolved vs
    abandoned. Compute from existing rows; no new table. Needed to judge items 22
    and 25.

20. **Product cards, and "Ask about this item".** Same mechanism as order cards,
    plus an entry point on `/.../product/:productId` that seeds the first message
    with the product as context.

21. **Store-level chat toggle.** Some merchants will not want a chat widget.
    `store.preferences` already holds similar switches.

## Phase 4 — housekeeping

22. **Plan gating**, if chat becomes a paid capability: a `storefront_chat` key in
    `app/features.py` checked with `load_entitlement` on the chat routes, and the
    Inbox nav item hidden when `hasPlanFeature` is false.

23. **Retention and export.** Auto-delete closed conversations after N months;
    provide an export. Chat holds customer-identifying content.

24. **Seller-inbox e2e spec.** The POS half has no automated coverage, so a change
    to nav wiring, `api.js`, or `roleViews` could break it silently. Model it on
    `e2e/dashboard.spec.js`.

25. **Multi-worker decision.** If the API ever runs with `--workers`, replace DB
    polling with a broker (Redis pub/sub) or accept that every connection polls
    independently. Decide deliberately, not by accident.

26. **Push the two commits already written.** Branch `fix/storefront-chat-followups`
    holds the order-confirmation widget and a Playwright round-trip spec,
    verified locally. Unrelated to everything above; it should not sit unmerged.

## Cross-cutting requirements for every PR here

- Migrations chain `down_revision` to the **current single head** (`alembic heads`
  must show exactly one).
- Regenerate `chmabapos_api/openapi.json` and
  `packages/api-client/src/schema.d.ts`; CI diffs both.
- New endpoints go under `/api/v1/public/...` (automatic rate limiting) or use
  `get_store_context*` (seller), matching what already exists.
- Tests: API integration in `chmabapos_api/tests/`, pure helpers in `apps/web/src/lib/*.test.js`
  and `apps/storefront/app/lib/*.test.js`, plus the Playwright spec for anything
  with a round trip.
- All ten CI jobs green before merge.

## Non-goals

- File transcription, video messages, or AI auto-replies.
- Bridging the thread to email-to-chat or WhatsApp/Messenger gateways. Worth
  revisiting later as a channel strategy, but it is a different feature.

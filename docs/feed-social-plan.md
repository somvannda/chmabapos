# Feed — workspace social wall

Status: Design only — no code changes in this document's PR.
Owners: Engineering
Scope: Plan/spec only. Implementation lands in follow-up `feat/feed-*` branches.

Related: `docs/architecture.md` (ADR-005 generated API client),
`docs/permissions-system-design.md`, `docs/multi-company-workspace-design.md`,
`chmabapos_api/app/models.py` (`MediaAsset`, `Membership`, `PlatformActivity`),
`chmabapos_api/app/media.py`, `apps/web/src/features/workspace.jsx`,
`apps/web/src/routing.js`.

## 1. Goal

Give each workspace a **Feed**: a company-scoped social wall where members post
status updates, images and links, and react to each other with likes/reactions,
comments (and threaded replies), and shares — the familiar Facebook-style loop,
inside the product.

The tab label is **“Feed”** (chosen over “Wall”, “Buzz”, “Pulse”, “Community”,
“Lounge”): it is a single plain noun that matches “share / like / comment”, reads
naturally next to the existing **Team access** and activity nav, and carries no
trademark baggage (“Timeline”) or settings-category feel (“Social”).

> ⚠️ Shell assumption. The screenshot's bottom bar (**People**, **Connect apps**,
> workspace switcher) does **not** exist in `apps/web` today — the web app uses a
> left sidebar that becomes a drawer on mobile. This plan adds **Feed** to that
> existing sidebar. If the screenshot is a different surface (e.g. a separate
> “Botifyr” client), confirm the target app before Phase 2 so the tab is wired
> into the right shell.

## 2. Current state

- There is **no** post/comment/reaction/share UI or API anywhere in the repo.
- The closest existing building blocks:
  - **Member/contact list** — `apps/web/src/features/team.jsx` (`LiveTeamView`):
    initials avatar + name + role/status `Badge` rows.
  - **Thread + composer + attachments** — `apps/web/src/features/support.jsx`
    (ticket thread, reply composer) and `components/SupportChat.jsx` (message list
    with per-message feedback).
  - **Rich text** — `components/RichTextEditor.jsx` (`RichTextEditor` + `RichBody`),
    already used for support replies.
  - **Image library/picker** — `features/media.jsx` (`MediaLibraryGrid`,
    `MediaLibraryModal`) backed by `POST /media/assets`.
  - **Notification row** — `NotificationsDropdown` in `workspace.jsx` (unread list,
    title/body/timestamp).
- Tenancy, media, permissions, migrations and the generated OpenAPI client all
  have established patterns this feature reuses (§5–§9).

## 3. Design principles

1. **Company-scoped, not store-scoped.** A feed belongs to the workspace
   (`company_id`); store/team filtering is a later refinement, not the default.
2. **Reuse the media pipeline.** Images go through `read_image_upload` +
   `upsert_media_asset`; posts reference `MediaAsset` rows, never raw paths.
3. **Reuse auth, permissions and plan gating.** No new auth mechanism; new
   `feed.*` permission keys and an optional `feed` plan capability.
4. **Soft-delete and moderate.** Posts/comments are hidden or deleted, not
   physically removed, so a shared/threaded item doesn't vanish under people.
5. **Additive and reversible.** One additive migration; every new table/column
   has a `downgrade()`. Nothing existing is rewritten.
6. **Plain SQL conventions.** `String(n)` status/kind columns with defaults and a
   documented value set — matching the rest of `models.py` (no SQLAlchemy enums).

## 4. Data model

All tables follow `models.py` conventions: `UUID(as_uuid=True)` PK,
`DateTime(timezone=True)` `created_at`/`updated_at`, `company_id` FK with
`ondelete="CASCADE"` and an index, and `__table_args__` for constraints.

- **`FeedPost`** — one wall post or share.
  - `company_id` FK → `companies` CASCADE, indexed.
  - `author_user_id` FK → `users` `SET NULL` (posts survive a removed author).
  - `body` `Text`, nullable (media-only posts allowed).
  - `kind` `String(20)` default `"post"` — `post | announcement | share`.
  - `visibility` `String(20)` default `"company"` — `company | store`.
  - `store_id` FK → `stores` `SET NULL`, nullable (set when `visibility="store"`).
  - `status` `String(20)` default `"published"` — `published | hidden | deleted`.
  - `shared_post_id` FK → `feed_posts` `SET NULL`, nullable (self-ref for shares).
  - `pinned` bool default `false`.
  - Denormalized counters: `comment_count`, `reaction_count`, `share_count`
    (int, default 0) so the stream needs no per-row aggregate.
  - `edited_at` nullable.
  - Indexes: `(company_id, created_at)` for the stream,
    `(company_id, author_user_id, created_at)` for a profile filter.
- **`FeedPostMedia`** — ordered attachments, mirroring `ProductSerialPhoto`.
  - `post_id` FK → `feed_posts` CASCADE, indexed; `position` int default 0.
  - `media_asset_id` FK → `media_assets` `SET NULL`, nullable; `url` `String(500)`
    (denormalized so the post still renders if the asset row is removed).
- **`FeedComment`** — comments and one level of replies.
  - `post_id` FK → `feed_posts` CASCADE, indexed; `company_id` FK CASCADE
    (carried for direct scoping/deletes).
  - `author_user_id` FK → `users` `SET NULL`.
  - `parent_id` FK → `feed_comments` `SET NULL`, nullable (one nesting level).
  - `body` `Text`; `status` `String(20)` default `"published"`; `edited_at`.
- **`FeedReaction`** — one reaction per member per post.
  - `post_id` FK → `feed_posts` CASCADE, indexed; `company_id` FK CASCADE.
  - `user_id` FK → `users` CASCADE.
  - `kind` `String(20)` default `"like"` — `like | love | haha | wow | sad | angry`.
  - `UniqueConstraint("post_id", "user_id", name="uq_feed_reaction_post_user")`.
- **`FeedRead`** — per-member read marker for an unread nav badge (Phase 3).
  - `company_id` FK CASCADE, `user_id` FK CASCADE, `last_seen_at`
    `DateTime(timezone=True)`; unique `(company_id, user_id)`.

Shares reuse `FeedPost.shared_post_id` (a share **is** a `kind="share"` post that
points at the original) instead of a separate `FeedShare` table; `share_count` is
maintained on the original. Reaction-on-comment is deliberately deferred (§12).

## 5. API

New endpoints in `app/api/v1.py`, tagged `["feed"]`, all scoped by
`membership.company_id`. List routes follow the codebase's ad-hoc
`limit`/`offset` `Query` style (there is no `Page[T]` envelope), and every
mutation re-checks ownership.

| Method | Path | Purpose | Gate |
|---|---|---|---|
| `GET` | `/feed/posts` | newest-first stream; filters `author_id`, `kind`, `store_id` | `feed.view` |
| `POST` | `/feed/posts` | create a post (`body`, `media_asset_ids[]`, `visibility`, `store_id`) | `feed.post` |
| `GET` | `/feed/posts/{post_id}` | single post with author + media | `feed.view` |
| `PATCH` | `/feed/posts/{post_id}` | edit body / pin / visibility (author or moderator) | owner or `feed.moderate` |
| `DELETE` | `/feed/posts/{post_id}` | soft-delete (`status="deleted"`) | owner or `feed.moderate` |
| `POST` | `/feed/posts/{post_id}/reactions` | upsert my reaction (`kind`) | `feed.post` |
| `DELETE` | `/feed/posts/{post_id}/reactions` | remove my reaction | `feed.post` |
| `GET` | `/feed/posts/{post_id}/comments` | comment page | `feed.view` |
| `POST` | `/feed/posts/{post_id}/comments` | add comment/reply (`body`, `parent_id`) | `feed.post` |
| `DELETE` | `/feed/comments/{comment_id}` | soft-delete | owner or `feed.moderate` |
| `POST` | `/feed/posts/{post_id}/share` | create a `kind="share"` post (`body` optional) | `feed.post` |
| `POST` | `/feed/media` | validate + catalogue an image for a post | `feed.post` |
| `POST` | `/feed/read` | stamp `last_seen_at` (Phase 3) | `feed.view` |
| `GET` | `/feed/unread` | unread count for the nav badge (Phase 3) | `feed.view` |

**Schemas** (`app/schemas.py`): `FeedPostRead`, `FeedPostCreateRequest`,
`FeedPostUpdateRequest`, `FeedPostMediaRead`, `FeedCommentRead`,
`FeedCommentCreateRequest`, `FeedReactionRequest`, `FeedShareRequest`,
`FeedUnreadRead`. Read models extend `APIModel` (`from_attributes=True`).

`FeedPostRead` embeds a lightweight `author` (`id`, `full_name`, `role`) — the
member row already exposes role via `Membership` — plus `media[]`,
`shared_post` (brief nested post or `null`), the counters, and `my_reaction`
(resolved for the caller) so the client renders reactions without a second call.
Follow the existing custom-serializer pattern (`order_read`, `customer_read`) if
lazy relationships need shaping.

**Media**: add `POST /feed/media` that calls `read_image_upload` then
`upsert_media_asset`, returning `MediaAssetRead`, so authors don't need
`catalog.manage` (which the generic `POST /media/assets` requires). The client
uploads first, then posts `media_asset_ids`.

## 6. Permissions & plan gating

Add to `PERMISSIONS` in `app/permissions.py` and seed into the relevant
`DEFAULT_ROLE_PERMISSIONS` sets:

- `feed.view` — owners, managers, inventory managers, cashiers.
- `feed.post` — owners, managers, inventory managers, cashiers.
- `feed.moderate` — owners and managers (hide/delete/pin anyone's post).

Declare dependency aliases next to the existing ones in `v1.py`:
`feed_view_roles = Depends(require_roles_or_permission((...), "feed.view"))`, etc.
Owner already receives `ALL_PERMISSIONS`, so owners pass automatically.

The feed is a **baseline collaboration surface** and is **not plan-gated** by
default. If it should be monetized, add a `feed` key to `FEATURE_CATALOG`,
seed `DEFAULT_FEATURES_BY_PLAN`, and call `require_plan_feature(..., "feed")`
like `table_management`/`purchasing` (§11 decision 6).

## 7. Activity & notifications

Emit `record_activity(db, "feed.posted" | "feed.commented" | "feed.shared", ...)`
immediately before the request commit, and add matching labels to `EVENT_TITLES`
in `app/services/activity.py`. Call with `notify=False` **unless** the team wants
Telegram noise, because `record_activity` otherwise posts to Telegram for every
event. Feed-specific in-app notifications (someone liked/replied to your post)
reuse the existing notifications surface and are **Phase 3**.

## 8. Frontend (`apps/web`)

A new view module `src/features/feed.jsx` exporting `LiveFeedView`, wired into the
existing hand-rolled view switcher (there is no router element list):

1. **Nav** — add `{ id: "feed", label: "Feed", icon: Newspaper }` to `NAV_ITEMS`
   in `features/workspace.jsx` (primary group, near Overview; it is a
   high-frequency destination). Optional unread dot from `/feed/unread`.
2. **Header** — add a `feed` entry to `pageMeta` in `workspace.jsx`.
3. **Render** — add `feed: <LiveFeedView token={token} workspace={workspace}
   notify={notify} />` to the `content` map in `workspace.jsx`.
4. **Access** — add `feed: ["owner","manager","inventory_manager","cashier"]` (or
   `"*"`) to `VIEW_ROLES` in `src/lib/roleViews.js`.
5. **Route** — add `feed` to **both** maps in `src/routing.js`
   (`USER_PAGE_TO_VIEW` and `VIEW_TO_USER_PAGE`), or `/<user>/feed` resolves to
   `not-found`.
6. **API** — add methods to `src/api.js`: `feedPosts`, `createFeedPost`,
   `updateFeedPost`, `deleteFeedPost`, `feedComments`, `createFeedComment`,
   `deleteFeedComment`, `reactToFeedPost`, `removeFeedReaction`, `shareFeedPost`,
   `uploadFeedMedia` (mirroring `uploadMediaAsset`).

**UI composition** (reusing `components/ui.jsx` primitives, `RichTextEditor`/
`RichBody`, and the `MediaLibraryModal`/`AttachmentPicker` upload pattern):

- **Composer** — text area, image picker (limit ~4 images, 5 MB each), visibility
  select (Company / Store), Post button; disabled while uploading.
- **Post card** — initials avatar + name + role + relative time, body
  (`RichBody`), media grid, a reaction bar (reaction picker + count), comment
  count and a share action. Header menu exposes Edit / Hide / Delete when the
  caller is the author or a moderator.
- **Comments** — inline expandable list with one level of replies and a compact
  reply composer.
- **Reactions** — a small hover/tap picker; the caller's reaction is highlighted.
  Optimistic update, reconciled from the mutation response.
- **Empty/loading/error states** — skeleton rows on first load, the shared
  `notify()` toast on failure.

**Styling** — reuse existing inline Tailwind tokens (`#6957f5` primary, `#e9e9ef`
borders, `#92939d` muted, card radius) so nothing new is needed in the
`styles.css` dark-mode override block. If a new surface hex is introduced, add its
`.dark` counterpart there too.

Mobile needs no extra work: the sidebar is already a drawer and Feed is a normal
view.

## 9. Migration & codegen

- **One additive Alembic revision** creating `feed_posts`, `feed_post_media`,
  `feed_comments`, `feed_reactions` (+ `feed_reads` in Phase 3), chained via
  `down_revision` to the current single head (today `b7d1e2f3a4c5`; re-check with
  `alembic -c chmabapos_api/alembic.ini heads` before writing, since the head
  moves). `downgrade()` drops the tables in reverse dependency order.
- **Regenerate and commit** `chmabapos_api/openapi.json`
  (`python chmabapos_api/scripts/export_openapi.py`) and
  `packages/api-client/src/schema.d.ts`
  (`cd packages/api-client && npm run generate`) together with the API change, or
  CI drift checks fail.
- **Schema drift** — CI runs `scripts/check_schema_drift.py`, so the migration
  must land in the same PR as the models.

## 10. Tests

- **API** (`chmabapos_api/tests/`): a `test_feed.py` built on the existing
  `_owner_workspace` / register→verify→login→workspace-setup helper pattern, plus
  a second member joined to the same company. Cover: create/list (newest-first,
  company isolation, `limit`/`offset`), reaction upsert + remove + unique
  constraint, comments + replies, share creating a `kind="share"` post and
  bumping `share_count`, soft-delete visibility, `feed.moderate` gating, and
  media upload via `files={"file": ("p.png", b"...", "image/png")}`.
- **Web unit** (`node --test`): add `src/lib/*.test.js` coverage for any extracted
  pure helpers (e.g. `feedHelpers.js` for time/count formatting), and add
  `features/feed.jsx` to `FEATURE_FILES` in `src/lib/apiSurface.test.js` so every
  `api.*` call is validated against `src/api.js`.
- **E2E** (Playwright): `apps/web/e2e/feed.spec.js` — seed a member, inject the
  token, `goto('/<username>/feed')`, post, react, comment, and assert the stream.

## 11. Rollout

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/feed-social-plan` | this document |
| 1 | `feat/feed-api` | models + migration, `feed.*` permissions, endpoints, tests, regenerated OpenAPI/client |
| 2 | `feat/feed-ui` | Feed tab, composer, stream, reactions, comments, shares |
| 3 | `feat/feed-media-notify` | image posts, unread badge/`FeedRead`, in-app notifications |

Each branch follows `AGENTS.md`: cut from `origin/main`, conventional commits, PR
to `main`, merge on green CI (API + Web + Admin).

## 12. Open decisions

1. **Scope of a feed** — one company-wide wall (recommended) vs per-store feeds vs
   per-department/team rooms. Store scoping is modelled (`visibility`/`store_id`)
   but off by default.
2. **Reaction model** — one reaction per member (recommended, matches Facebook) vs
   multiple/emoji-counts. Modelled as unique `(post_id, user_id)`.
3. **Tab placement** — primary nav group near Overview (recommended) vs the
   “Manage” group next to Team access. Also confirm the target shell (see §1).
4. **Media upload gate** — dedicated `POST /feed/media` (recommended, avoids
   granting `catalog.manage` to cashiers) vs relaxing `POST /media/assets`.
5. **Avatars** — `User` has no avatar field today; render initials (recommended,
   matches `team.jsx`) vs add `users.avatar_url` in a follow-up.
6. **Monetization** — baseline for every plan (recommended) vs a gated `feed`
   capability for higher tiers.
7. **Moderation policy** — who may hide/delete/pin, whether a hidden post keeps
   its comments, and any retention/export rules.
8. **Notifications** — in-app only, vs also Telegram digest events for feed
   activity (token/volume trade-off).

## 13. Out of scope

- Direct messages / chat, group chat, stories, and video/audio posts.
- Groups, pages, and external/federated sharing.
- Algorithmic ranking or a “For you” sort (v1 is strict newest-first).
- Reaction-on-comment and mention autocomplete (safe Phase 3+ additions).
- Mobile apps and browser push; the web drawer covers navigation.

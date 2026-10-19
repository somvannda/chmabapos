# Public storefronts & a store directory

Status: Proposed. Decisions agreed (§4): **dedicated origin
(`shops.chmaba.com`)**, **dedicated SSR app (`apps/storefront`)**, **full shopper
accounts incl. Google**, and a **public consumer directory**. The design below
implements those; only the items in §13 are still unanswered.

Progress: **phases 1–5 and 7 are shipped.** Short store links + slugs (#629),
design tokens (#630), the slug-addressed storefront API (#633), the SSR storefront
app (#634) and its own host (#635), branding API + branded page + merchant editor
(#636–#638), slug-based ordering + the cart/checkout UI (#639–#640), and the
public directory (#642) with a header link (#643). Correcting the plan's own
sequencing (#631) and recording the decisions (#632) shipped alongside.

**What still stands between this and a live storefront:**

1. **It is not publicly reachable.** `VITE_STOREFRONT_URL` stays blank until
   `shops.chmaba.com` has a DNS record and a certificate covering it — those are
   operator tasks. With the variable blank, production behaviour is unchanged.
2. **KHR** (§13.1) — blocked on the ChmabaPay contract, see §13.
3. **Phases 8 and 9** — SEO and custom domains. Shopper accounts (phase 6) are
   shipped; the remaining gaps are listed in §12.
4. Smaller gaps called out in the §12 table.
Owners: Engineering / Product
Scope: a new public storefront app, URL and identity design, the customer
storefront experience, the store directory ("Stores"), shopper authentication,
and the phased rollout that keeps every existing printed QR code and shared link
working.

Related: `docs/online-ordering-plan.md` (the tokenised public menu this builds on),
`docs/architecture.md` (ADR-002/ADR-003/ADR-005/ADR-006 — app boundaries, one API
contract), `docs/restaurant-mode.md`, `docs/capabilities-and-gaps.md`.

---

## 1. Goal

Turn the existing single-purpose public ordering page into a real, brandable
storefront that a merchant can treat as *their own website*, and add a directory
page that lets a shopper discover every store on Chmaba and open one.

Three requests drive this:

1. A **directory link** (candidate names: *Stores* / *Marketplace*) that lists
   every store as cards; clicking a card opens that store's public page in a new
   window.
2. Replace the long `https://chmaba.com/order/<token>` link with a clean
   `https://<business>/<store>` shape.
3. Make that page **e-commerce grade and merchant-branded**, with sign-in
   (Google) *and* guest checkout.

## 2. Current state (facts this plan is built on)

| Area | Reality today |
|---|---|
| Public store link | `https://chmaba.com/order/<32-hex>` where the hex is `Store.public_order_token` (`uuid4().hex`). **It identifies a store, not an order.** |
| Public API | `GET/POST /api/v1/public/order/{token}` and `GET /api/v1/public/order/{token}/payment/{held_id}`. Unauthenticated; resolve store by token, or by `DiningTable.qr_token`. |
| Submit semantics | A public submit creates a **`HeldOrder`** (open ticket), not an `Order`. `Order` has no public identifier — `order_number` is unique only per store. |
| Table QR flow | Table QR codes encode `/order/<qr_token>`; the same resolver falls back to `DiningTable.qr_token`. **Printed QR codes already point at `/order/...`.** |
| Store identity | `Store` has `public_order_enabled`, `public_order_token` (unique), `name`, `address`, `phone`, `currency_code`, `preferences` JSON, `is_active`. **No slug, no branding, no hours, no policies.** |
| Company identity | `Company` has name/contact/tax/settings. **No slug.** |
| Merchant-side public URL | Built in `apps/web/src/features/settings.jsx` as `${origin}/order/${publicToken}`. Copy-only — not editable. |
| Routing (`apps/web`) | Vite + React; `react-router` v7 is a dependency but routes are dispatched by hand in `src/routing.js` → `parseRoute()`. Shapes: `/`, `/order/:token`, `/display`, `/login`, `/signup`, `/reset-password`, `/privacy\|terms\|contact\|refund-policy`, `/:username/setup/:step`, `/:username/:view`, `/app`, else 404. |
| `/:username/:view` | `username` is derived from the user's **email local part** (`usernameFor`); `view` must be one of the 17 `USER_PAGE_TO_VIEW` keys, else 404. `/admin/*` is deliberately 404 here. |
| Theming | `ThemeProvider` supports only light/dark. Tailwind colors are **hard-coded hex** with hand-written `.dark [class~="bg-[#…]"]` overrides. No design tokens, no per-store color. Store logo/name/address are used **only** on the customer display. |
| Auth (staff) | Email+password, **Google OAuth shipped**, 6-digit email verification, password reset, Turnstile bot protection. `User` is staff-only and drives memberships, roles, plan seat counts and the admin Users list. |
| Shopper auth | **None.** `Customer` is a per-company CRM row with no credentials and no global identity. |
| Payments | Cash / KHQR via ChmabaPay, funded by the merchant's ABA PayWay link. **USD only.** No Stripe. |
| Rate limiting | None on the public endpoints. Only support chat and QZ printing have limiters. |
| Deploy | `Dockerfile.front` builds `apps/web` + `apps/admin` into **one static nginx image**; `deploy/nginx.conf` has server blocks for `chmaba.com` and `admin.chmaba.com`; `deploy/docker-compose.prod.yml` runs `db` + `api` + `front`. `CORS_ORIGINS` is already a comma-separated env var. CI is `.github/workflows/ci.yml`. |

**Requests 1 and 2 are the same primitive: the store needs a stable, public,
human-readable identity.** Today it only has an opaque token. Fix that once and
both requests fall out of it.

## 3. Naming: "Stores" vs "Marketplace"

Recommendation: **use "Stores". Reserve "Marketplace" for later.**

"Marketplace" has a specific meaning in commerce UX — *multi-vendor with a single
cross-store cart and checkout* (Amazon, Shopee, Etsy). "Stores" is a directory:
a browsable index of shops you visit individually. Request 1 describes a
**directory**. Calling it "Marketplace" today promises something you are not
shipping (one cart across several merchants).

- Directory page: **"Stores"**.
- Merchant entry point inside the workspace: **"View store page"**.
- Rename to "Marketplace" only if/when a cross-store cart ships.

## 4. Decisions

Agreed. Each row is marked as a decision you made, or as my recommendation that
will be implemented unless you say otherwise.

| # | Item | Status | Resolution |
|---|---|---|---|
| D1 | Origin | ✅ Your decision | **Dedicated origin**, separate from `chmaba.com`. |
| D1a | Hostname | ✅ Locked | **`shops.chmaba.com`** — the host named in the option you chose (§5.1). |
| D2 | URL shape | ✅ Your decision | `/<company-slug>/<store-slug>` on the storefront origin. |
| D3 | Namespace collision | ✅ Resolved by D1 | **Solved by origin separation.** `/{username}/{view}` lives on `chmaba.com`; a different origin cannot collide with it. No reserved-word blocklist required. |
| D4 | Legacy link | ✅ Required | `/order/<token>` on `chmaba.com` becomes a **permanent 301** to the storefront URL. Never removed (printed QR codes, shared links, IG bios). |
| D5 | Storefront app | ✅ Your decision | New **`apps/storefront`**, server-rendered, own build and deploy. |
| D6 | Shopper accounts | ✅ Your decision | **Full accounts, incl. Google**, on a **separate shopper identity** (§6.4). |
| D7 | Checkout gate | ➡️ My recommendation | **Guest-first, always available.** Accounts are the retention layer, not the gate (§6.5). |
| D8 | Directory | ✅ Your decision | **Public consumer directory** at `/stores` on the storefront origin. |
| D9 | Listing policy | ➡️ My recommendation | **Opt-in** per store + admin moderation (§7.4). |
| D10 | Rendering | ✅ Your decision | **SSR** in `apps/storefront`. |
| D11 | SSR framework | ✅ Decided | **React Router v7 framework mode** — `react-router-dom@^7` is already a dependency in `apps/web` (§10.4). |
| D12 | Theming | ✅ Shipped (#630) | **Design tokens** live in `packages/ui` (§6.3). The change was additive, so nothing changed visually. Migrating `apps/web` off hard-coded hex is optional cleanup, **not** a gate on the storefront. |
| D13 | Rate limiting | ✅ Required | Before public launch (§11). |

---

## 5. URL, host and identity design (request 2)

### 5.1 Hostname: `shops.chmaba.com`

Locked. The dedicated-host option you selected was described as
`shops.chmaba.com/businessname/storename`, so that is the host and the path shape
is exactly what you originally asked for — only the host differs from
`chmaba.com`.

```text
https://shops.chmaba.com/<company-slug>/<store-slug>              storefront (canonical)
https://shops.chmaba.com/<company-slug>/<store-slug>/order/<tok>  one order (unguessable)
https://shops.chmaba.com/<company-slug>/<store-slug>/track        order lookup
https://shops.chmaba.com/stores                                   directory
https://chmaba.com/order/<token>           → 301 → the storefront URL (legacy)
```

**Later upgrades (not in this programme).** Each is additive — the data model and
the `/<company>/<store>` path shape do not change, so none of these force a
rewrite:

| Upgrade | Example | Cost |
|---|---|---|
| Shorter host for QR/signage | `chmaba.shop/acme/downtown` | A second domain registration. |
| Per-store subdomain | `acme.chmaba.com` | Wildcard DNS + wildcard cert; fragments SEO authority per store. |
| Merchant custom domain | `shop.acme.com` | TLS per merchant, DNS verification. A credible paid tier. |

### 5.2 Why the collision problem disappears

The earlier concern was that `parseRoute()` owns the first path segment for
usernames (`/{username}/{view}`), so a store slugged `orders` would make
`/acme/orders` resolve as a workspace route. On a **dedicated origin** that
cannot happen: `chmaba.com/acme/orders` is a different origin from
`shops.chmaba.com/acme/orders`, and the workspace routes simply do not exist on
the storefront host. **No reserved-word blocklist, no slug-vs-username
uniqueness rule.** This is the main structural win of the decision.

What remains is much smaller: a short list of **reserved paths on the storefront
origin itself** — `stores`, `order`, `track`, `api`, `media`, `assets`, `_next`,
`healthz`, `robots.txt`, `sitemap.xml`, `favicon.ico` — because those are real
routes on that host.

### 5.3 Slug rules

- Lowercase `a-z0-9` and single hyphens; length 3–50; no leading/trailing hyphen.
- Auto-suggest from the store/company name; allow one manual edit; then treat as
  effectively permanent.
- **Renames keep the old slug working** via a slug-history table (301 to the
  current slug). Merchants *will* print the URL on signage.
- Company slug is set once during onboarding and is the tenant's public identity;
  **globally unique**.
- Store slug is unique per company.

### 5.4 The two link types — do not conflate them

| Link | Purpose | Guessable? | Lifetime |
|---|---|---|---|
| `/<company>/<store>` | Storefront / menu | Yes (intentionally, for sharing & SEO) | Permanent, redirect-safe |
| `/…/order/<public-token>` | One order's status, receipt, "ready for pickup" | **No** — unguessable token | Revocable, optional expiry |

Today there is **no** public order link, because `/order/<token>` is a *store*
token. If the goal is "the customer can follow up on their order", that needs a
new `orders.public_token` (`secrets.token_urlsafe`), returned on submit and
included in the confirmation email. Never expose the order UUID and never expose
`order_number` alone — both are enumerable and would leak other customers' orders.

### 5.5 Migration of the existing link

1. Add `company.slug`, `store.slug` (nullable at first), backfill, then enforce
   uniqueness. Stores without a slug keep working through the token path.
2. New canonical URL = `https://shops.chmaba.com/<company>/<store>`.
3. `chmaba.com/order/<token>`:
   - matches `Store.public_order_token` → 301 to the storefront URL;
   - matches `DiningTable.qr_token` → 301 to the storefront URL with
     `?table=<table-qr-token>`;
   - `public_order_enabled` is off → a friendly "ordering is not available" page
     (not a 404).
4. Settings shows the new URL plus a note that the old link still works; keep a
   rotate-token action for merchants who need to kill a leaked link.

**Redirect at the edge.** Do the 301 in nginx (or the API) rather than in the
SPA — it is better for SEO and faster, and it keeps working even if the
referenced store is later unlisted.

---

## 6. Storefront UX (request 3)

Goal: a shopper landing from an Instagram bio or a QR believes they are on the
merchant's own shop, and can order in under a minute on a mid-range Android
phone over mobile data.

### 6.1 Page anatomy (mobile-first)

```
┌──────────────────────────────────────────────┐
│ [logo] Store name        ⏰ Open · 9:00–21:00 │  sticky header
│ 📍 address · 📞 phone        [search] [cart]  │
├──────────────────────────────────────────────┤
│  Cover image / banner (optional)              │
│  Tagline · rating/orders count (optional)     │
│  Fulfilment: [Pickup] [Delivery] [Dine-in]    │
├──────────────────────────────────────────────┤
│  Category chips  (sticky, horizontal scroll)  │
├──────────────────────────────────────────────┤
│  Product grid / list                          │
│  [img] Name            $2.50      [+]         │
│  [img] Name (sold out) $2.50      [–]         │
├──────────────────────────────────────────────┤
│  Footer: hours, map, policies, socials,       │
│  "Powered by Chmaba"                          │
└──────────────────────────────────────────────┘
        floating cart bar: "3 items · $12.50 →"
```

Non-negotiables:

- **Mobile-first.** One column at ~360 px. Desktop is the wide variant, not the
  design target.
- **States, not just the happy path.** Loading skeletons; empty category;
  sold-out items (visible but disabled — never silently hidden, it makes the
  store look broken); store **closed** (hours + "opens at 9:00" + optional
  pre-order); store **paused** ("not accepting orders right now",
  merchant-controlled); invalid/disabled link; network error with retry.
- **Product detail** as a bottom sheet, not a full page: image, description,
  variants/modifiers, quantity, "Add to cart". Preserves context and scroll.
- **Cart** as a bottom sheet / drawer with a persistent summary bar.
- **One-click quantity** on the card for single-variant items; open the sheet
  only when the product actually has options. Biggest single conversion lever.
- **A merchant "pause online orders" switch**, instantly effective — a kitchen at
  capacity must be able to stop the flow without disabling the store.
- **SSR note:** the initial HTML must already contain the store name, logo, hours
  and menu so the page is useful before hydration and unfurls correctly.

### 6.2 Branding: what merchants control

| Control | Notes |
|---|---|
| Logo, cover image | Media library already exists. |
| Accent colour | From **vetted presets**, not a free picker (§6.3). |
| Tagline / short about | Plain text, length-capped. |
| Opening hours + "temporarily closed" | Drives the open/closed state. |
| Address (+ map pin), phone | Trust; also local SEO. |
| Fulfilment modes, min order, delivery fee/zones | Drives checkout options. |
| Policies: returns, delivery, privacy | Required for trust. |
| Social links | Instagram/Telegram/Facebook — how Cambodian merchants reach customers. |
| Banner / announcement strip | "Free delivery over $10" — high value, low effort. |

### 6.3 Theming architecture — shipped as `packages/ui`, and not a gate

The approach this document originally proposed (hard-coded hex + hand-written
`.dark [class~="bg-[#…]"]` rules) **cannot** support per-store theming; every new
colour doubles the override list.

**Status: step 1 shipped (#630).** `packages/ui` now holds the palette as CSS
custom properties (space-separated RGB channels, so Tailwind can build
`bg-brand/10` variants) plus a Tailwind preset mapping colour names onto them.
Crucially the change was **additive**: the preset only adds utilities and changes
no existing class, so adoption is a visual no-op and components can migrate one
at a time.

Because the values are variables, a *scoped* override rebrands a subtree rather
than the whole app — which is exactly the mechanism branding needs:

```jsx
<div style={{ "--color-brand": "220 38 38" }}>…</div>
```

Remaining work, in priority order:

1. ✅ **Design tokens in `packages/ui`** — done (#630).
2. **Provide preset palettes** with pre-computed contrast-safe pairs. Do not allow
   arbitrary text-on-background combos: enforce WCAG AA (4.5:1 body, 3:1 large
   text/UI) and reject or auto-correct failures.
3. **Isolate the storefront theme from the POS shell.** The storefront is a public
   marketing surface; the workspace stays Chmaba-branded. The merchant's colours
   must never leak into the cashier UI.
4. **Optional cleanup that gates nothing:** delete the `apps/web` dark-override
   block once components have been converted. It can only be removed after every
   component has moved off hard-coded hex, so it is a large mechanical change
   needing visual review — and it is **not** on the storefront's critical path
   (see §12).

### 6.4 Auth: full shopper accounts on a separate identity

**Decided: full accounts including Google.** Two constraints shape how.

🚩 **Do not reuse the staff `User` table.** `google_sub` and `/auth/google` map to
`User`, and `User` drives memberships, roles, plan seat counts, staff invitations
and the admin Users list. Putting shoppers there would pollute admin analytics,
consume plan seats and confuse staff invites.

So shopper identity is its own model (§9.3):

- `shopper_accounts` — platform-level identity: `email` (unique), `phone`,
  `full_name`, `google_sub` (unique), `email_verified_at`, `is_active`.
- `shopper_sessions` — rotating refresh token, mirroring `AuthSession`.
- `customers.shopper_id` — links the global shopper to the per-company CRM row
  without duplicating it.
- `held_orders.shopper_id` / `orders.shopper_id` — so order history and loyalty
  work without touching `created_by` (which FKs `users.id`).
- A shopper is **platform-level**: one account can shop at many stores. Order
  history is therefore scoped per store *within* the account.

Sign-in methods — **all three ship in the first shopper-auth release** (decided):

1. **Email + 6-digit code** (passwordless). Reuses the existing email-code
   machinery and Turnstile — near-zero new auth code, no new password surface.
2. **Google** — reuses `verify_google_id_token`, but needs its own redirect URI
   (§10.3) and must upsert a *shopper*, not a `User`.
3. **Telegram Login** — the highest-adoption provider in Cambodia, so it is part
   of the first release rather than a follow-up. The identity model must be
   **multi-provider from the outset**, so each provider is an endpoint plus
   configuration rather than a later migration.

### 6.5 Checkout: guest-first, always

**Recommendation: guest checkout stays the default and the primary path, even
though accounts now exist. Building accounts is not the same as gating checkout.**

Rationale: forced sign-in is one of the best-documented causes of cart
abandonment. You are selling a coffee, not building a user base. Accounts matter
for *retention* (order history, reorder, saved address, loyalty points) — they
should be offered at the moment of highest motivation.

The pattern:

1. **Guest checkout**: name + phone/email + fulfilment (+ address if delivery) +
   payment. No password, no account required.
2. **"Continue with Google"** offered *alongside* guest checkout — never as the
   only door. It pre-fills name/email and skips typing.
3. **After** confirmation: "Save your details for next time" — one tap with
   Google, or a 6-digit email code. This is where accounts convert best.
4. **Order history / reorder** requires sign-in, and is the reason a returning
   shopper signs in at all.
5. **Guest → account merge**: a shopper who buys as a guest then later signs up
   with the same email should have those past orders attached. Decide and
   implement the merge rule explicitly; it is easy to get wrong.

Other checkout requirements:

- **Fulfilment first, then payment.** Pickup needs no address; the storefront
  should not ask for one. Pickup default for restaurant/counter verticals.
- **Payment options**: KHQR (ChmabaPay) primary, cash on pickup/counter fallback,
  pay-at-store as the zero-integration default for merchants without ABA. Note
  KHQR is currently **USD-only** — KHR support is a real prerequisite for many
  local merchants (§13).
- **Show the total before payment**, including delivery fee and tax. No surprises.
- **Confirmation screen** with order number, pickup time/ETA, store address and
  phone, the KHQR receipt if paid, and a **tracking link** (§5.4). Email
  it too.
- **Never lose the cart on error.** Persist to `localStorage` keyed by store; a
  failed payment must not empty the basket.
- **Abandoned-cart recovery** is a later, high-ROI add-on.

### 6.6 Localisation and locale defaults

- **Khmer + English** from day one. The font stack already includes Noto Sans
  Khmer; the layout must tolerate Khmer's lack of inter-word spaces and its
  taller line-height without overflow.
- **Dual-currency display** (`$2.50 / 10,000 ៛`) is the norm here. Even when the
  charge is USD, shoppers read KHR.
- Locale-aware dates and the store's `timezone` (`Asia/Phnom_Penh`) for hours and
  "ready at" times.
- SSR must render the right locale server-side (per-store locale, or
  `Accept-Language` + a `?lang=` override) — not after hydration.

### 6.7 Trust, accessibility, performance

- **Trust**: physical address, phone, hours, a verification badge (verified vs
  new), return/delivery policy, and a visible "Powered by Chmaba" footer.
- **Accessibility**: WCAG 2.2 AA — keyboard-navigable product sheet and cart,
  visible focus, `aria-live` for cart updates, alt text per product image, tap
  targets ≥ 44 px.
- **Performance**: LCP < 2.5 s on a mid-range phone over 4G. Product images are
  served raw from `/media`; the storefront needs responsive `srcset`,
  `loading="lazy"`, fixed aspect-ratio boxes and cache headers. SSR plus a CDN in
  front is the lever.
- **Merchant analytics**: views, add-to-cart rate, orders, conversion, top
  products — surfaced in the workspace. Merchants will ask on day one, and it is
  the honest measure of whether this feature worked.

---

## 7. Directory UX (request 1)

### 7.1 Placement

- **Public**: a **"Stores"** link in the marketing header, and the page at
  `https://shops.chmaba.com/stores` (linked from `chmaba.com`).
- **Merchant side**: a "View store page" link in
  Settings → Online ordering (that card already shows the public link).

### 7.2 Card anatomy

```
┌────────────────────────────┐
│  [ cover image 16:9 ]      │   fallback: brand gradient + logo
│  [logo] Name       ✔verified│
│  Restaurant · Phnom Penh   │
│  ● Open now · closes 21:00 │   or ○ Closed · opens 9:00
│  Pickup · Delivery          │
│  ⭐ 4.8 (126)               │   only once reviews exist
└────────────────────────────┘
```

- Open in a **new tab** (`target="_blank" rel="noopener"`) as requested, so the
  directory stays behind the shopper.
- The whole card is a single link, not just the title.

### 7.3 Controls

- **Search** by store or business name (and later product name — "who sells this
  near me" is the killer feature).
- **Filters**: category/vertical, city/area ("near me" via opt-in geolocation),
  open now, fulfilment mode.
- **Sort**: relevance, open first, recently added.
- **States**: skeleton grid, friendly empty state, "no results" with a clear
  reset, and **server-side pagination or infinite scroll** — never load all stores.
- **URL-encoded filters** (`/stores?category=cafe&city=phnom-penh&open=1`) so
  results are shareable and indexable.

### 7.4 Listing policy

Recommendation: **opt-in**, not "list every store".

- New `Store.listed_in_directory` (default **off**), enabled by the merchant or by
  platform admin.
- Rationale: stores with no branding, suspended stores, stores with online
  ordering disabled, and internal/test stores should not appear. A directory full
  of broken entries destroys the trust the page exists to build.
- **Admin moderation**: review/approve listing and be able to unlist. `apps/admin`
  already has a Stores surface to extend.
- Add a **verification** concept (verified business) so the card badge means
  something. Admin-side verification does not exist today and is new work.

### 7.5 SEO for the directory

`/stores` and every storefront must be indexable: unique `<title>` and meta
description per store, Open Graph + Twitter tags with a per-store OG image
(Facebook/Telegram unfurls are how these links actually spread), `LocalBusiness`
and `Product`/`Offer` JSON-LD, canonical URLs, `robots.txt` and a generated
`sitemap.xml`. The SSR decision (D10) makes this straightforward.

---

## 8. Data model changes

All additive, one revision each, chained to the single Alembic head
(`b7d1e2f3a4c5` at time of writing).

**companies** — `slug: str(50) | None`, globally unique.

**stores**

- `slug: str(50) | None` — unique per company.
- `slug_previous` history (table or JSON) for rename redirects.
- `listed_in_directory: bool` (default false) + `listing_status`
  (`unlisted | pending | approved | rejected`).
- `storefront` JSON (or a dedicated table): logo, cover, accent preset, tagline,
  hours, policies, socials, banner, min order, delivery fee/zones, accept-orders
  flag.
- `verified_at: datetime | None`.
- Keep `public_order_token` — **repurpose it as the rotation/revocation
  credential**, not the primary URL.

**orders** — `public_token: str | None` (unique, unguessable),
`public_token_expires_at: datetime | None`, `shopper_id` FK.

**shopper identity** (new — D6)

- `shopper_accounts` (as §6.4).
- `shopper_sessions` (rotating refresh token).
- `customers.shopper_id` FK.
- `held_orders.shopper_id` FK.

**Principles**: nullable → backfill → enforce; slugs are data, not code; never
turn a rotatable token into a printed URL.

## 9. API surface changes

### 9.1 Public (unauthenticated)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/public/stores` | Directory: paged, filtered, searchable. Only `approved` + active + opted-in stores. No PII, no costs. |
| `GET` | `/public/store/{company_slug}/{store_slug}` | Storefront: branding, hours, policies, fulfilment, menu, availability. |
| `GET` | `/public/store/{company_slug}/{store_slug}/menu` | Menu, kept separate for cacheability. |
| `POST` | `/public/store/{company_slug}/{store_slug}/orders` | Submit → `HeldOrder`, returns order number + public token. |
| `GET` | `/public/orders/{public_token}` | Order status/receipt (unguessable). |
| `GET` | `/public/order/{token}` | **Kept forever** as the legacy resolver (§5.5). |

Responses carry only what the shopper needs: no costs, no supplier data, no
inventory counts (in-stock/out-of-stock flag only), no other customers' data.

### 9.2 Shopper auth (new)

- `POST /public/auth/email-code` → 6-digit code (reuse email-code + Turnstile).
- `POST /public/auth/verify` → shopper session.
- `POST /public/auth/google` → verify ID token, upsert **shopper** (not `User`).
- `GET /public/auth/me`, `POST /public/auth/logout`, `POST /public/auth/refresh`.
- Order-history endpoints scoped to the authenticated shopper, grouped by store.
- Guest checkout endpoints take **no** auth.

### 9.3 Merchant (authenticated)

- `PATCH /stores/{id}` — extend with `slug`, `listed_in_directory`, storefront
  branding/policy fields; require `settings.manage`.
- A slug-change path that writes the history row so old URLs keep resolving.
- `GET /stores/{id}/storefront/analytics` — views, add-to-carts, orders,
  conversion, top products.

---

## 10. Deployment and platform plumbing

These are the concrete consequences of D1 + D5 (dedicated origin + SSR app), and
they are easy to underestimate.

### 10.1 A fourth deployable

`apps/storefront` is **server-rendered**, so unlike `web`/`admin` it cannot be a
static stage in `Dockerfile.front`. It needs a Node runtime:

- New service in `deploy/docker-compose.prod.yml` (e.g. `storefront`, listening on
  an internal port), with `front`/nginx depending on it.
- New `server` block in `deploy/nginx.conf` for the new host: `location /` →
  `storefront`, plus `location /api/` and `location /media/` → `api` (see §10.2).
- A DNS record and a **TLS certificate covering the new hostname**. The current
  cert is a Cloudflare Origin CA cert; a SAN for the new host must be added (or a
  wildcard used).
- A new CI job in `.github/workflows/ci.yml` and a deploy step in
  `.github/workflows/deploy.yml`, matching the existing per-app pattern.

### 10.2 Keep the API same-origin (avoid CORS and cookie pain)

If the storefront calls `https://chmaba.com/api/v1/...` directly it becomes a
**cross-origin** request: `CORS_ORIGINS` must include the new host, credentials
must be allowed, and the refresh cookie needs `SameSite=None; Secure`, which is
fragile and blocked by some browsers.

**Recommended: terminate the new host in the same nginx and proxy `/api/` and
`/media/` to the `api` container.** The browser then sees a same-origin API
relative to the storefront host: cookies work normally, no CORS, no
`SameSite=None`. `CORS_ORIGINS` stays as-is.

The SSR process additionally talks to the API **server-side** on the internal
network (`http://api:8000/api/v1`), so the app needs two base URLs: a public
relative one for the browser and an internal absolute one for SSR.

### 10.3 A second Google redirect URI

`settings.google_redirect_uri` is a **single** value and defaults to
`https://chmaba.com/api/v1/auth/google/callback`. Google requires every redirect
URI to be pre-registered in the console. Shopper Google sign-in on the storefront
origin therefore needs:

- a second config field (e.g. `GOOGLE_STOREFRONT_REDIRECT_URI`) or a validated
  `redirect_uri` selection in the authorize endpoint;
- the new URI added in the Google Cloud console;
- the OAuth `state` cookie scoped to the storefront host.

### 10.4 Framework: React Router v7 framework mode

My recommendation, and what the plan below assumes:

- **React Router v7 framework mode** (the Remix successor) — `react-router-dom@^7`
  is **already a dependency in `apps/web`**, so it is the smallest conceptual
  leap: same router, same React, same Tailwind, SSR/loaders/actions built in.
- Next.js (App Router) would win on ecosystem polish (ISR, `next/image`, metadata
  API) at the cost of adopting a second set of conventions across the repo.

Either way, share `packages/api-client` (ADR-005) and `packages/ui` (D12), and
keep `apps/storefront` free of any POS imports so it stays independently
deployable.

### 10.5 Admin additions

- Shopper visibility for support ("customer cannot sign in") — **read-only and
  scoped**, and explicitly *not* mixed into the existing Users list.
- Directory moderation (approve/unlist/verify).

---

## 11. Hardening (must ship with the public surface)

- **Rate limiting** on all `/public/*` endpoints (per IP and per store token).
  `docs/online-ordering-plan.md` promised it; it is not implemented. A public
  directory makes scraping and enumeration cheap.
- **Turnstile** on shopper sign-up/sign-in (the staff flow already uses it).
  On order submit, prefer rate limiting + a honeypot over a visible CAPTCHA —
  friction here costs orders.
- **Server-side price and availability recomputation** — never trust client
  prices or modifiers.
- **Enumeration**: order lookup by unguessable token only; never by sequential
  `order_number` alone.
- **IDOR check**: a public order token must resolve to exactly one store and never
  expose another store's or customer's data.
- **PII**: limit retention on guest orders; no emails/phones in public responses.
- **Abuse**: image moderation for storefront branding (media library exists) and
  admin unlist.
- **Cacheability**: storefront metadata and menus are highly cacheable — add
  cache headers/ETags so a directory click is fast.

## 12. Phased rollout

| # | Branch | Scope | Ships independently |
|---|---|---|---|
| 0 | `docs/marketplace-storefront-plan` | ✅ This document (#628) | — |
| 1 | `feat/store-slugs` | ✅ Shipped (#629) — `company.slug`, `store.slug` + history, backfill, legacy-link redirect, Settings and the All stores list show the store page link | ✅ Request 2 |
| 2 | `feat/ui-design-tokens` | ✅ Shipped (#630) — `packages/ui` tokens + Tailwind preset, additive so nothing changes visually | ✅ |
| 3 | `feat/storefront-app` | ✅ Shipped (#633–#635) — slug-addressed storefront API, SSR `apps/storefront`, its own host (nginx + compose). **Operator still needs to add DNS and a certificate for the host** | ✅ Unblocks everything below |
| 4 | `feat/storefront-branding` | ✅ Shipped (#636–#638, and the accept-orders switch in #648) — branding settings + accent presets, branded page, merchant editor and the pause-orders control | ✅ |
| 5 | `feat/storefront-ecommerce` | ✅ Shipped (#639–#640) — slug-based ordering API and the cart/checkout UI. **Outstanding: KHR (§13.1), rate limiting, and a browser test of the flow** | ✅ Request 3 core |
| 6 | `feat/shopper-accounts` | ✅ Shipped — shopper identity, email code + Google + Telegram, order history, the sign-in UI, guest→account merge, the `Customer.shopper_id` link, and revocable sessions (sign-out kills the token). **Outstanding: a rotating refresh cookie** | ✅ D6 |
| 7 | `feat/store-directory` | ✅ Shipped (#642, #643) + opt-in listing (#645, in review) — `GET /public/stores`, `/stores` page + cards + search, header link. **Outstanding: admin moderation and filters** | ✅ Request 1 |
| 8 | `feat/storefront-seo` | Per-store meta + JSON-LD, OG images, sitemap, robots, merchant analytics | ✅ |
| 9 | `feat/store-custom-domains` | `shop.<merchant>.com` upgrade path | ✅ Later |

Order: the critical path was **1 → 2 → 3 → 4** — public identity, then the token
package, then the SSR app, then branding. Phases 1–7 have all shipped, so **nothing on the critical path is untaken**; what
remains is phase 8 (SEO) and phase 9 (custom domains), plus the specific gaps
called out in the table above and in §13.

**Correction (2026-10-14).** An earlier version of this document treated the
`apps/web` token migration as a prerequisite for the storefront. It is not. The
storefront is a *new* app and consumes `packages/ui` from day one, so it never
inherits the hard-coded hex or the ~300-line dark-override block. Migrating
`apps/web` is worthwhile cleanup — it is what lets that block be deleted — but it
gates nothing and must not be scheduled ahead of the storefront.

Your original requests land in the order you listed them — the short URL first,
then the storefront, then the directory — because the URL is the foundation, the
storefront is the destination, and the directory merely links to it.

## 13. Decisions on the remaining questions

Two of the four were answered on 2026-10-14 and are now settled:

1. ⛔ **KHR payments — in scope, but blocked.** KHQR is USD-only today, which
   blocks checkout for any merchant who prices in ៛. **Blocker, not a decision:**
   `ChmabaPayClient.create_payment()` has no currency argument and its request body
   sends no `currency` field at all — currency appears only in the *response*,
   defaulting to `"USD"` (`app/services/payments/chamabapay.py`). So KHR depends on
   the ChmabaPay API contract: does `POST /payments` accept a currency, or is it
   derived from the merchant's ABA PayWay store configuration? Until that is known
   the feature must not be guessed at — a parameter the provider ignores would look
   like riel support while silently charging dollars, which is worse than no support.
2. ✅ **Telegram sign-in — in the first shopper-auth release**, alongside email
   code and Google (see §6.4). No longer a follow-up.

Still open. Neither blocks phases 3–5:

3. **Business verification** — introduce admin-reviewed verification alongside the
   directory (so the card badge means something), or ship the directory without
   badges and add it later? Blocks phase 7.
4. **Custom domains** — is `shop.<merchant>.com` a near-term ask, or a later paid
   tier? Only affects when phase 9 is scheduled, not the design.

## 14. Out of scope

- Multi-vendor cart / single checkout across stores (that is what would justify
  the name "Marketplace").
- Delivery dispatch, driver tracking, live rider ETAs.
- Reviews and ratings (card layout reserves space; data model deferred).
- Promotions/coupons engine on the storefront.
- Native mobile apps.
- Email/SMS marketing automation (see `docs/email-notifications-plan.md`).

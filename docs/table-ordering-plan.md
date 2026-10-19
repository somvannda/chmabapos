# Table ordering & the restaurant kitchen path

Status: Proposed — design + rollout plan. No code changes in this document's PR.
Owners: Engineering / Product
Scope: the table-QR entry URL, the storefront's dine-in mode, the API's table
context, kitchen/tenant gating, dine-in auto-fire, modifiers on the public menu,
table-QR printables, public rate limiting, tests, and the rollout that keeps every
already-printed QR code working.

Related: `docs/online-ordering-plan.md` (the tokenised menu this builds on),
`docs/marketplace-storefront-plan.md` (§5.4 link types, §5.5 legacy migration,
§11 hardening), `docs/restaurant-mode.md` (§4 table model, §7 gating),
`docs/seat-course-plan.md` (§5 firing), `docs/storefront-golive.md`,
`docs/capabilities-and-gaps.md` (G11).

---

## 1. Goal

A guest sitting at table 7 scans a QR on the table and lands on a branded ordering
page that already knows **which store** and **which table** they are at. Their order
is a **dine-in** ticket on that table, it reaches the **Kitchen** board, and it is
settled at the counter or paid online — all through the existing order engine.

At the same time, the same store keeps a normal public storefront for **online
selling** (pickup/delivery). The two entry points must not be confused, and the
kitchen must continue to appear only for workspaces that actually run a dining room.

The work is deliberately **not** a second storefront: one page, one price engine,
one order engine, two entry modes.

## 2. Current state (verified)

Facts this plan is built on, with the file that proves each one.

| # | Fact | Evidence |
|---|---|---|
| F1 | Every `DiningTable` gets an opaque `qr_token` at creation | `app/api/v1.py` (`DiningTable(..., qr_token=uuid.uuid4().hex)`), `app/models.py` |
| F2 | Settings renders a QR per table | `apps/web/src/features/settings.jsx` — `` `${origin}/order/${table.qr_token}` `` |
| F3 | The legacy token path resolves a table and creates a **dine-in** ticket | `_resolve_public_store()` + `_submit_public_order()`: `order_type="dine_in" if table else "takeaway"`, `source="qr" if table else "online"`, `table.status="occupied"` |
| F4 | The slug storefront **cannot** express a table | `public_store_submit_order()` calls `_submit_public_order(db, store, None, ...)` |
| F5 | The storefront app has **no** table handling at all | no `table` reference in `apps/storefront/app`; loader is `fetchStore(companySlug, storeSlug)` |
| F6 | The legacy page *generates* `?table=` when it hands off to the storefront | `apps/web/src/features/publicOrder.jsx` → `storefrontUrl(..., { tableToken })`; `apps/web/src/lib/storefront.js` |
| F7 | `PublicMenuRead.table_name` and `_public_menu_payload(db, store, table)` already exist | `app/schemas.py`, `app/api/v1.py` |
| F8 | The submit API already prices `modifiers`, but the public menu never exposes a modifier group | `PublicOrderItemRequest.modifiers` vs `PublicMenuItem` (variants only) |
| F9 | The Kitchen **nav and view** are gated on the `tables` capability **and** the `table_management` plan feature | `apps/web/src/features/workspace.jsx` (`NAV_ITEMS` filter), `kitchen.jsx` (`allowsCapability(..., "tables")`) |
| F10 | Only `restaurant` enables `tables` by default, but any store can opt in | `app/verticals.py`: `"restaurant": ("variants","modifiers","tables")`, `"general": ()`; `Settings → Feature packs` writes `capability_overrides` |
| F11 | A public order creates a `HeldOrder` for **every** store, not only restaurants | `_submit_public_order()` — unconditional `HeldOrder(...)` |
| F12 | That held row carries the online payment state | `HeldOrder.payment_status/payment_qr_string/payment_checkout_url`, polled by `GET /public/order/{token}/payment` |
| F13 | A public order is **not** fired; lines are written `fired_at: null` | the item snapshot in `_submit_public_order()` |
| F14 | No public endpoint is rate-limited | only support chat and QZ printing call `check_rate_limit()` |
| F15 | Alembic has a single head | `e2b6c4a8f1d3` at time of writing |
| F16 | Every CI job must be green | `.github/workflows/ci.yml`: `api`, `web`, `storefront`, `admin`, `e2e`, `api-client`, `ops-config`, `front-image`, `android`, `ios` |

### 2.1 What was proven locally

A throwaway Playwright spec was run against the real dev stack (API 8001, web 5173,
storefront 3000) and then deleted. Results:

| Scenario | Result |
|---|---|
| Table created | ✅ `qr_token = 0d4cdd…ef04`, status `available` |
| Scan `…/order/<qr_token>` | ✅ menu opens, store name and **"T1"** shown |
| Place order from that page | ✅ ticket `source=qr`, `order_type=dine_in`, `table_id` set, `label=T1`; table → **`occupied`** |
| Storefront `/<company>/<store>?table=<qr_token>` | ❌ table not shown; ticket `source=online`, `order_type=takeaway`, `table_id=null` |
| Existing storefront cart→order spec | ✅ 2/2 |

**Conclusion:** the dine-in path works today only because the legacy token URL is
still served inline. The moment `VITE_STOREFRONT_URL` is set, every printed table QR
is redirected to a storefront that drops the table (F6 + F4/F5). That is the bug this
plan closes.

## 3. Decisions

The user has accepted these; they are requirements, not options.

| # | Decision | Consequence |
|---|---|---|
| D1 | **Separate entry link, one page.** Table ordering gets its own URL; it does not fork the storefront app. | One catalog, one cart, one `_submit_public_order()`. |
| D2 | **Path segment, not a query param.** `/<company>/<store>/t/<table_code>` | Survives copy/paste, sharing and redirects; renders an explicit mode. |
| D3 | **Opaque, rotatable table code.** Never the table number. | `qr_token` (or a rotation of it); `/table/4` is forbidden — it is spoofable. |
| D4 | **Stable printed link.** The QR encodes a slug-independent link and 301s into the branded route. The legacy `/order/<token>` keeps working forever. | Merchants may already have printed table tents. |
| D5 | **Table routes are `noindex`** and never appear in the sitemap, the directory, or directory cards. | A competitor cannot enumerate a restaurant's tables through search. |
| D6 | **`tables` capability is the kitchen gate**, not the literal vertical. | Restaurant is the default; a café that opts into the pack gets it too. |
| D7 | **Every public order keeps its held ticket.** | It is the payment-state carrier (F12); removing it for non-restaurants would break online KHQR. |
| D8 | **Hide non-POS tickets from the POS held-orders drawer on stores without `tables`.** | No phantom "tickets" a retail merchant cannot act on; the `Order` still exists. |
| D9 | **Dine-in orders auto-fire on submit.** Online pickup/delivery stays manual. | A guest scanning a table QR reaches the pass without a cashier pressing Fire. |
| D10 | **Rate-limit all `/public/*` endpoints** before the directory grows. | Reuse the existing sliding-window limiter; document the single-process caveat. |
| D11 | **Expose modifiers on the public menu.** | The submit API already prices them (F8); the menu must let the guest choose. |
| D12 | **Print/download table QR codes.** | Settings currently renders them on screen only (F2). |

### 3.1 Functional requirements

- **R1** A guest who scans a table QR lands on a page that names the store **and the
  table**, and orders in **dine-in** mode.
- **R2** The resulting ticket is attributed to that table (`table_id`, `order_type =
  dine_in`, `source = qr`) and appears on the Kitchen board.
- **R3** The same store still offers normal online selling (pickup/delivery) at its
  store page, with no table context.
- **R4** Floor/Kitchen appear only when the store has the `tables` capability **and**
  the `table_management` plan feature.
- **R5** A merchant can rotate a table's code; the old QR then resolves to a friendly
  "link no longer active" state and creates nothing.
- **R6** Guests can choose a product's modifiers on the public menu, and the server
  prices them.
- **R7** A merchant can print or download one QR card per table.

### 3.2 Non-functional requirements

- **N1** A printed QR must never stop working: the legacy token URL is permanent and
  the redirect preserves the table.
- **N2** Table URLs are unguessable (opaque code), `noindex`, and never enumerable
  from the directory or sitemap.
- **N3** Every `/public/*` endpoint is rate-limited before the directory grows.
- **N4** One catalogue and one price/order engine: both entry modes call
  `_submit_public_order()`; no second pricing path.
- **N5** No migration for v1; any later change is additive and chained to the single
  Alembic head.
- **N6** The table route must keep the storefront's existing mobile-first,
  keyboard-navigable, ≥44 px tap-target standard.
- **N7** Every CI job is green before merge (section 13).

## 4. URL and identity design

### 4.1 The four addresses

```text
https://shops.chmaba.com/stores                                   directory        indexable
https://shops.chmaba.com/<company>/<store>                        online selling   indexable
https://shops.chmaba.com/<company>/<store>/t/<table_code>         dine-in          NOINDEX
https://chmaba.com/order/<table_token>   → 301 → the /t/ route    printed QR       permanent
```

On the storefront origin, the first path segment `order` is already the **order
status** page (`routes/orderStatus.jsx`), so table ordering must live under the store
path, not at `/order/...`. The QR therefore encodes the POS-origin legacy link and
redirects into the store's route.

`t` is a **third** segment, so it does not collide with `RESERVED_STORE_SLUGS`
(`api`, `assets`, `healthz`, `media`, `order`, `track`), which govern segments 1–2.
No slug-reservation change is needed; `routes.js` must still declare the more
specific `:companySlug/:storeSlug/t/:tableCode` route alongside `product`.

### 4.2 Why the printed link stays slug-independent

A store slug can be renamed (the slug-history 301 exists), and the storefront host is
new. A physical sticker must not depend on either. So:

- the QR encodes `chmaba.com/order/<table_token>` (or a future `chmaba.com/t/<code>`);
- the server resolves the token to the store **and** the table;
- it 301s to the current canonical `/<company>/<store>/t/<table_code>`.

### 4.3 Table code rules

- Opaque; generated server-side; unique; **scoped to one store**.
- Resolvable only when the store has `public_order_enabled` and is active.
- Rotatable by the merchant (a leaked/lost table tent must be killable without
  reprinting the whole restaurant).
- Never the table's human name (`T1`), never a sequential id.
- Reuse `DiningTable.qr_token` for v1. A shorter display code is optional later
  (section 11) — not a reason to migrate now.

### 4.4 Legacy permanence

`chmaba.com/order/<token>` must never be removed. It resolves:

1. a `Store.public_order_token` → the store page;
2. a `DiningTable.qr_token` → the table route;
3. otherwise a friendly "ordering is not available" page (not a bare 404).

Redirect **at the edge/API** (301) rather than in the SPA where possible; the SPA
fallback in `publicOrder.jsx` must use the `/t/` target, not `?table=`.

### 4.5 Indexing and directory

- `/<company>/<store>/t/<code>` returns `<meta name="robots" content="noindex">`
  and is excluded from `sitemap.xml`.
- The directory (`/stores`) and its cards link only to `/<company>/<store>`.
- No table URL is ever emitted in the store page's canonical, OG tags or JSON-LD.

## 5. Storefront dine-in mode

### 5.1 Loader

`routes/store.jsx` gains the table segment:

```js
export async function loader({ params }) {
  const store = await fetchStore(params.companySlug, params.storeSlug, params.tableCode);
  if (!store) throw new Response("Store not found", { status: 404 });
  return { store };
}
```

The API returns the same `PublicMenuRead`, with `table_name` populated when the code
resolves to a table **of this store**. No new page component: the same store page
renders, switched into dine-in mode.

### 5.2 States

| State | Behaviour |
|---|---|
| Valid code | Dine-in mode; table shown; no pickup/delivery choice |
| Code belongs to another store | 404, identical to an unknown code (never reveal that it exists) |
| Rotated/revoked code | Friendly "this table link is no longer active — ask a member of staff" |
| Ordering disabled | Existing "ordering is not available" state |
| Network/API failure | Existing retry state; never a blank page |

### 5.3 Page differences (dine-in)

- Header shows **"Table T1"** (or the table name) next to the store name.
- Fulfilment is fixed to **dine-in**; pickup/delivery controls are not rendered.
- Copy: "Order for your table" instead of "Order for pickup".
- Payment default: **pay at the counter**; online KHQR remains available if the
  store requires it.
- Cart/confirmation keep the table label; the confirmation says "the kitchen has
  your order".
- `meta()` returns `noindex` for this route.

### 5.4 Backward compatibility

`apps/web/src/lib/storefront.js` currently supports `{ tableToken }` → `?table=`.
Change it to emit `/t/<code>`. Keep `?table=` accepted by the storefront loader for
one release (302 to `/t/`) so any link already generated in the wild still lands
correctly.

## 6. API surface

### 6.1 Additions

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/public/store/{company_slug}/{store_slug}` **+ `?table=<code>`** | Same menu payload; `table_name` set when the code is valid for this store. |
| `POST` | `/public/store/{company_slug}/{store_slug}/orders` **+ `table_token`** | Submit with table context → dine-in ticket on that table. |
| `GET/POST` | `/public/order/{token}` | Unchanged legacy resolver (table token still works). |
| `GET` | `/public/order/{token}/payment/{held_id}` | Unchanged. |

### 6.2 Schema changes (no migration)

- `PublicOrderSubmitRequest` gains `table_token: str | None = Field(default=None, max_length=64)`.
- `PublicMenuRead` already carries `table_name`; no change.
- `PublicMenuItem` gains `modifier_groups` (section 8) — additive.

### 6.3 Resolution and scoping

A new helper:

```python
async def _resolve_public_table(db, store, code) -> DiningTable | None:
    return await db.scalar(
        select(DiningTable).where(
            DiningTable.store_id == store.id,
            DiningTable.qr_token == code,
        )
    )
```

- `public_store()` reads `table` from the query, resolves it **scoped to the store**,
  and passes it to the existing `_public_menu_payload(db, store, table)`.
- `public_store_submit_order()` resolves `payload.table_token` the same way and passes
  it to the existing `_submit_public_order(db, store, table, payload, shopper_id)`.
- A code that does not resolve for this store is a **404**, not a 403, and not a
  silent `None` (silently dropping it recreates the bug).
- A code that resolves must still pass the store's normal gates
  (`public_order_enabled`, `is_active`).

### 6.4 Pricing stays single-sourced

Both the legacy and slug paths already share `_submit_public_order()`, which
recomputes prices, validates stock and writes `Order` + `HeldOrder`. Table context
must be passed **into** that function, never priced separately.

### 6.5 Rate limiting

- Apply the existing sliding-window limiter (`app/services/support.py::check_rate_limit`)
  to every `/public/*` route: key = client IP + token, with a per-store ceiling.
- New config: `PUBLIC_RATE_LIMIT_PER_MINUTE` (default conservative), plus a
  submit-specific ceiling.
- Return `429` with `Retry-After`.
- Document the known limitation: the limiter is in-process, so it is per worker; a
  shared store (Redis) is a later upgrade, not a blocker.

## 7. Kitchen, gating and auto-fire

### 7.1 The gate

The kitchen surface stays gated on:

```
allowsCapability(workspace.capabilities, "tables")
  AND hasPlanFeature(workspace.plan_features, "table_management")
```

This is already how `NAV_ITEMS` and `kitchen.jsx` behave (F9). **Do not** add a
`vertical == "restaurant"` check anywhere. A store on `general` that enables the
`tables` pack in Settings → Feature packs gets Floor/Kitchen too (F10).

### 7.2 The held ticket is universal

Every public order continues to create a `HeldOrder` (F11). It is the kitchen work
item **and** the online-payment state carrier (F12). The slug path and the token path
share `_submit_public_order()`, so this stays true for both.

### 7.3 Hide phantom tickets from retail POS

On a store without `tables`, the POS held-orders drawer must not list online/QR
tickets that no one can work. Filter non-POS tickets out of that drawer when the
capability is off. The `Order` remains visible in Orders and reporting.

### 7.4 Auto-fire for dine-in

- If `table is not None`, stamp `fired_at` on every line when the ticket is created.
- Keep online pickup/delivery lines unfired (staff fire when they start the order).
- The Kitchen board already renders unfired lines with a bullet; auto-fired dine-in
  lines simply lose the bullet.
- Firing stays a kitchen signal only — stock, tax and payment are still settled at
  the normal point.

**Open sub-decision:** fire all lines, or only the first course? Recommendation: fire
all lines for v1 (a table QR order is a complete order), and revisit when course
timing ships.

## 8. Modifiers on the public menu

The submit API already accepts and prices `modifiers` (F8); the menu never offers
them, so a restaurant's add-ons are unusable by guests.

- `PublicMenuItem` gains `modifier_groups: list[PublicModifierGroup]`, each with
  `id`, `name`, `min_select`, `max_select`, `required`, and `modifiers[]`
  (`id`, `name`, `price_delta`).
- Only active groups attached to an active product are returned. No costs.
- The storefront product sheet renders the groups (radio for single-select,
  checkboxes for multi), enforces min/max, and adds the deltas to the displayed price.
- The server still recomputes every delta (never trust client prices).
- Combos are out of scope for this phase.

## 9. Table QR printables

Today the QRs are on-screen only (F2). Add:

- a **Print** action in Settings → Online ordering that renders a print stylesheet
  with one card per table: store name, table name, QR, and a short "Scan to order
  from your table" line;
- a **Download** action (PDF or a self-contained HTML page) for merchants without a
  printer attached to the POS;
- a **Regenerate** action per table (rotation, section 4.3) that warns the old QR
  will stop working.

Print output must use the stable printed link (D4), not the storefront slug URL.

## 10. Directory relationship

- The directory is a **discovery** surface; table ordering is **contextual**. They do
  not link to each other.
- Directory cards keep linking to `/<company>/<store>` only.
- Optional later: a "Dine-in" badge/filter on cards, driven by the `tables`
  capability. Not required for this programme.

## 11. Data model and migrations

**No migration is required for v1.** The plan reuses:

- `DiningTable.qr_token` (opaque, unique, already generated);
- `HeldOrder.table_id`, `order_type`, `source`, `payment_*`;
- `PublicMenuRead.table_name`;
- `_submit_public_order(db, store, table, ...)`.

If a shorter, human-friendly table code is wanted later, add a nullable
`DiningTable.display_code` with a backfill and keep `qr_token` as the authority. That
is a separate, additive revision chained to the single head (`e2b6c4a8f1d3`), not
part of this work.

## 12. Testing strategy

### 12.1 API (pytest)

- A table token still resolves through the legacy `GET/POST /public/order/{token}`
  and produces `source=qr`, `order_type=dine_in`, `table_id`, table `occupied`.
- `GET /public/store/{c}/{s}?table=<code>` returns `table_name` for a valid code.
- The same code on **another store's** slug returns 404.
- `POST .../orders` with `table_token` produces a dine-in ticket; without it, a
  takeaway ticket.
- A rotated/unknown code is rejected; nothing is created.
- Auto-fire: a dine-in ticket has `fired_at` set on every line; an online pickup
  ticket has `fired_at: null`.
- Modifiers: the menu exposes groups; submit prices them; a tampered delta is ignored.
- Rate limit: the N+1th submit in the window returns 429 with `Retry-After`.

### 12.2 Storefront (node tests)

- Loader passes the `tableCode` through to `fetchStore`.
- Cart totals include modifier deltas.
- Dine-in mode hides pickup/delivery and shows the table label.
- `meta()` returns `noindex` on the table route.

### 12.3 End-to-end (Playwright)

Extend `apps/web/e2e/storefront-order.spec.js` (or a new
`storefront-dine-in.spec.js`) with:

1. Create a workspace on a paid plan, complete the mock billing payment, create a
   product, create a table via `POST /dining/tables`, enable online ordering.
2. **Legacy scan:** visit `http://127.0.0.1:5173/order/<qr_token>`, assert the store
   name and table name, place an order, assert "Order placed".
3. **Attribution:** `GET /held-orders` contains a ticket with `source=qr`,
   `order_type=dine_in`, `table_id=<table>`; `GET /dining/tables` shows `occupied`.
4. **Storefront table route:** visit
   `http://127.0.0.1:3000/<company>/<store>/t/<qr_token>`, assert the table label is
   visible, place an order, and assert the same dine-in attribution.
5. **Isolation:** visit another store's `/<company>/<store>/t/<code>` with the wrong
   store and assert 404.
6. **Regression:** the existing cart/flows in `storefront-order.spec.js` still pass.

The temporary spec used to verify the current behaviour (and the bug) is described in
section 2.1 and must not be committed; the permanent version belongs here.

### 12.4 Manual checklist

- Settings → Online ordering: print a table QR, scan it with a phone, confirm the
  table label and dine-in copy.
- Kitchen board: the ticket appears, auto-fired, with the table label and QR badge.
- Cancel/rotate a table code: the old QR shows the friendly expired state.
- A `general` store with online ordering: no Floor/Kitchen nav; the POS drawer does
  not show the online ticket.
- A `general` store that enables the `tables` pack: Floor/Kitchen appear.

## 13. Rollout

One branch and PR per row. Every CI job must pass before merge — `api`, `web`,
`storefront`, `admin`, `e2e`, `api-client`, `ops-config`, `front-image`, `android`,
`ios` (see `.github/workflows/ci.yml`).

| # | Branch | Scope | Status |
|---|---|---|---|
| 0 | `docs/table-ordering-plan` | this document | ✅ shipped (#875) |
| 1 | `fix/storefront-table-qr` | API table context (`?table=`, `table_token`), a `/t/<code>` route, dine-in mode, `/t/` redirect target, API + e2e tests | ✅ shipped (#877) — table QR survives go-live |
| 2 | `feat/dine-in-auto-fire` | auto-fire dine-in lines; keep pickup manual; kitchen assertions | ✅ shipped (#879) |
| 3 | `feat/pos-held-filter` | hide non-POS tickets from the POS drawer when `tables` is off | ✅ shipped (#881) |
| 4a | `feat/public-menu-modifiers` | publish a product's add-on groups on the public menu; re-price add-ons from the catalogue on submit | this PR — D11 (API) |
| 4b | `feat/storefront-modifier-picker` | storefront product sheet: groups, min/max, deltas; the cart carries the selection | D11 (UI) |
| 5 | `feat/table-qr-printables` | print/download/rotate table QRs | D12 |
| 6 | `feat/public-rate-limit` | limiter on `/public/*`, config, 429 tests | D10 |
| 7 | *(optional)* `feat/directory-dine-in-badge` | "Dine-in" card badge/filter | later |

Order rationale: **1 is urgent** (it prevents a silent regression at go-live), **2–3
are small and make the kitchen honest**, **4 is the biggest product gap for a
restaurant menu**, **5–6 are launch hardening**, **7 is optional**.

## 14. Deliverables and acceptance criteria

### 14.0 File-level change map

| Phase | File | Action |
|---|---|---|
| 1 | `chmabapos_api/app/schemas.py` | add `table_token` to `PublicOrderSubmitRequest`; add `modifier_groups` to `PublicMenuItem` (phase 4) |
| 1 | `chmabapos_api/app/api/v1.py` | add `_resolve_public_table()`; read `?table=` in `public_store()`; resolve `table_token` in `public_store_submit_order()`; pass the table into `_submit_public_order()` |
| 1 | `chmabapos_api/openapi.json`, `packages/api-client/src/schema.d.ts` | regenerate for the schema change |
| 1 | `apps/storefront/app/lib/api.js` | `fetchStore(companySlug, storeSlug, tableCode)` appends `?table=` |
| 1 | `apps/storefront/app/routes.js` | add `:companySlug/:storeSlug/t/:tableCode` alongside `product` |
| 1 | `apps/storefront/app/routes/store.jsx` | read `params.tableCode`; dine-in mode; table label; `noindex` in `meta()`; accept `?table=` for one release |
| 1 | `apps/web/src/lib/storefront.js` | emit `/t/<code>` instead of `?table=` |
| 1 | `apps/web/src/features/publicOrder.jsx` | redirect target uses the `/t/` route |
| 1 | `chmabapos_api/tests/test_online_ordering.py` | table-context resolution, scoping, 404 isolation |
| 1 | `apps/web/e2e/storefront-dine-in.spec.js` (new) | scan → dine-in → attribution → isolation |
| 2 | `chmabapos_api/app/api/v1.py` | stamp `fired_at` on dine-in lines in `_submit_public_order()` |
| 2 | `chmabapos_api/tests/test_online_ordering.py` | auto-fire vs manual cases |
| 3 | `apps/web/src/features/workspace.jsx` / `sales.jsx` | filter non-POS tickets from the POS held list when `tables` is off |
| 3 | `apps/web/e2e/*` | a retail store does not show the online ticket as a held order |
| 4 | `chmabapos_api/app/schemas.py` | `PublicModifierGroup`, `PublicModifier`, `PublicMenuItem.modifier_groups` |
| 4 | `chmabapos_api/app/api/v1.py` | `_public_menu_payload()` loads active groups for the returned products |
| 4 | `apps/storefront/app/routes/store.jsx` | product sheet: groups, min/max, deltas |
| 4 | `apps/storefront/app/lib/*.test.js` | totals include deltas |
| 5 | `apps/web/src/features/settings.jsx` | print view, download, per-table rotate |
| 5 | `chmabapos_api/app/api/v1.py` | `POST /dining/tables/{id}/rotate-qr` (writes a new `qr_token`) |
| 6 | `chmabapos_api/app/config.py` | `PUBLIC_RATE_LIMIT_PER_MINUTE`, submit ceiling |
| 6 | `chmabapos_api/app/api/v1.py` | apply the limiter to every `/public/*` route; `429` + `Retry-After` |
| 6 | `chmabapos_api/app/services/support.py` | reuse the existing sliding-window helper (no new dependency) |

### Phase 1 — `fix/storefront-table-qr`

- [ ] `GET /public/store/{c}/{s}?table=<code>` resolves a table **scoped to the store**;
      invalid/foreign codes are 404.
- [ ] `POST /public/store/{c}/{s}/orders` accepts `table_token` and creates a dine-in
      ticket via the shared `_submit_public_order()`.
- [ ] Storefront route `/<company>/<store>/t/<table_code>` renders the store page in
      dine-in mode with the table label.
- [ ] `?table=` still works (302 to `/t/`) for one release.
- [ ] `apps/web/src/lib/storefront.js` emits `/t/<code>`.
- [ ] The legacy `/order/<token>` still resolves and redirects to `/t/<code>` when the
      storefront host is configured.
- [ ] `meta()` marks the table route `noindex`.
- [ ] E2E covers scan → order → dine-in attribution → 404 isolation.
- [ ] No migration; `openapi.json` regenerated if the API schema changed; `api-client`
      drift job is green.

### Phase 2 — `feat/dine-in-auto-fire`

- [ ] Dine-in lines are written with `fired_at`.
- [ ] Pickup/delivery lines remain unfired.
- [ ] Kitchen board shows no "unfired" bullet for auto-fired dine-in lines.
- [ ] API test covers both cases.

### Phase 3 — `feat/pos-held-filter`

- [ ] On a store without `tables`, the POS held-orders drawer excludes non-POS tickets.
- [ ] The `Order` remains in Orders; no data is deleted.
- [ ] A `tables` store still sees every ticket.

### Phase 4 — `feat/public-menu-modifiers`

- [ ] `PublicMenuItem.modifier_groups` is populated for active groups only, with no costs.
- [ ] The storefront sheet enforces min/max and shows deltas.
- [ ] Submit re-prices server-side; a client-supplied delta is ignored.
- [ ] E2E adds an item with a modifier and asserts the ticket line and total.

### Phase 5 — `feat/table-qr-printables`

- [ ] Print view renders one card per table (store, table, QR, instruction).
- [ ] Download produces a saved file.
- [ ] Rotate invalidates the old code and states the consequence before doing it.

### Phase 6 — `feat/public-rate-limit`

- [ ] Every `/public/*` route is limited by IP + token.
- [ ] Submit has its own ceiling; 429 includes `Retry-After`.
- [ ] Config is documented; the in-process limitation is noted.

## 15. Risks and rollback

| Risk | Mitigation |
|---|---|
| A printed QR stops working after a slug rename | D4: QR encodes the slug-independent token; slug history 301s |
| A table code is leaked/screenshotted | Opaque code + rotate action (Phase 5); no table numbers in URLs |
| Table route gets indexed | `noindex` + sitemap exclusion + directory never links it |
| A retail store gets phantom kitchen tickets | D8 filter; the `Order` is the source of truth |
| Auto-fire surprises staff | It applies only to dine-in/table orders; pickup stays manual |
| Rate limiter is per worker | Documented; Redis-backed limiter is a later upgrade |
| Two pricing paths drift | Both entry modes must go through `_submit_public_order()` |

**Rollback:** the storefront host switch is independent (`VITE_STOREFRONT_URL`); the
legacy token path is never removed. Phase 1 can be reverted without data changes
(no migration). Auto-fire and the drawer filter are UI/creation-time behaviour and
revert cleanly.

## 16. Open decisions

1. **Auto-fire scope** — all lines or first course only? Recommendation: all lines
   for v1.
2. **Table code length** — keep the 32-hex `qr_token`, or add a short display code?
   Recommendation: keep `qr_token`; QR carries length for free. A short code is a
   later additive column.
3. **Printed link host** — `chmaba.com/order/<token>` (works today) or a new
   `chmaba.com/t/<token>`? Recommendation: keep the existing shape forever; add an
   alias only if merchants complain about the long path.
4. **Directory "Dine-in" badge** — now or later? Recommendation: later, once the
   storefront host is live.

## 17. Out of scope

- Multi-vendor cart or one checkout across stores (the thing that would justify the
  word "marketplace").
- Delivery dispatch, driver tracking, live ETAs.
- Table reservations/waitlists and deposits.
- Per-seat billing (split-by-line already ships).
- Custom merchant domains.
- KHR online payment (blocked on the ChmabaPay contract; see
  `docs/marketplace-storefront-plan.md` §13.1).

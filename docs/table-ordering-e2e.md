# Table ordering — end-to-end test design

Status: Verified — the full run passed in local dev on 2026‑10‑19 (§7).
Owners: Engineering
Scope: the manual/exploratory test design for the table-ordering programme, plus
the result of running it. The automated counterparts live in the test suites; this
document is the map between them.

Related: `docs/table-ordering-plan.md` (the phases under test),
`docs/online-ordering-plan.md`, `docs/restaurant-mode.md`.

How to verify the table-ordering programme (phases 1–5) against a **local dev
stack in a real browser**. This is the manual/exploratory companion to the
automated suites (Playwright specs in `apps/web/e2e`, pytest in
`chmabapos_api/tests`).

## 1. What is under test

| # | Phase | Behaviour to see |
|---|---|---|
| P1 | table QR survives go-live | a table code resolves to the branded store page **in dine-in mode**, not a takeaway |
| P2 | dine-in auto-fire | a table order's lines arrive **already fired** on the kitchen board |
| P3 | retail POS held filter | a store **without** the `tables` capability does not list online/QR tickets as held orders |
| P4a | public add-on API | the menu publishes add-on groups; the submit re-prices from the catalogue and refuses unknown add-ons |
| P4b | storefront picker | a guest can choose an add-on; required groups block the add; the choice reaches the ticket |
| P5 | printables + rotate | a table's QR can be printed/downloaded; rotating retires the old code and only the new one resolves |

## 2. Environment

Start three processes (the API on **8001** so the repo's own dev API on 8000 can
stay untouched — note it may be a stale binary):

```
# API (current code, local dev database)
cd chmabapos_api
PUBLIC_ORDER_RATE_LIMIT_PER_MINUTE=0 PUBLIC_READ_RATE_LIMIT_PER_MINUTE=0 \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# POS shell (serves the legacy /order/<token> page the table QR still encodes)
cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173 --strictPort

# Branded storefront (SSR)
cd apps/storefront
VITE_DEV_API_TARGET=http://127.0.0.1:8001 INTERNAL_API_URL=http://127.0.0.1:8001/api/v1 \
  npm run dev -- --host 127.0.0.1 --port 3000 --strictPort
```

**Why the rate limit is disabled:** the public surface is limited per IP (10
writes/min). Driving several orders from one address would otherwise return 429
part-way through the run. The limiter has its own API tests.

`VITE_STOREFRONT_URL` stays blank, which is the production-safe default: the
legacy `/order/<token>` page is served inline rather than redirecting.

## 3. Fixture (created through the API, not the UI)

A scripted seed keeps the test repeatable. Steps:

1. `POST /auth/register` → `POST /auth/verify-email` → `POST /auth/login`.
2. `POST /workspaces/setup` with `plan_code: "pro"` (table management is a paid
   feature), then `POST /mock/chamabapay/{external_id}/complete` to activate it.
3. `POST /modifier-groups` — a **required** group "Milk" (min 1, max 1) with
   `Oat +0.50` and `Whole 0.00`.
4. `POST /products` — "Flat White" $3.00, `opening_stock` 20,
   `modifier_group_id` = the group above.
5. `POST /dining/tables` — `T1` (seats 2) and `T2` (seats 2); each gets a
   `qr_token`.
6. `PATCH /stores/{id}/public-order` `{enabled: true}`.
7. Read `company.slug` / `store.slug` from `/workspaces/current`.

Derived URLs:
- storefront store page … `http://127.0.0.1:3000/<company>/<store>`
- product page … `…/<company>/<store>/product/<productId>`
- dine-in route … `…/<company>/<store>/t/<T1.qr_token>`
- **printed** table QR target … `http://127.0.0.1:5173/order/<T1.qr_token>`

## 4. Scenarios

Each scenario states the browser steps and the API assertion that proves it.

### S1 — a guest chooses a required add-on
1. Open the product page.
2. **Expect** the group "Milk" with an add button **disabled** and the hint
   "Choose the required options above."
3. Click "Oat".
4. **Expect** the price to read **$3.50** and the add button to become enabled.
5. Add, open the cart, place the order.
6. **Expect** "Order placed".
7. **Assert** the newest ticket line: `modifiers[0].name == "Oat"`,
   `price_delta == "0.50"`, `unit_price == "3.50"`, ticket `subtotal == "3.50"`,
   `order_type == "takeaway"`, `source == "online"`, `table_id == null`.

### S2 — a table QR lands in dine-in mode
1. Open the dine-in route `…/t/<T1.qr_token>`.
2. **Expect** the store name, the **"Table T1 · Dine-in"** badge, and the items.
3. Add the Flat White, place the order.
4. **Assert** the ticket: `source == "qr"`, `order_type == "dine_in"`,
   `table_id == T1.id`, `label == "T1"`.
5. **Assert** `dining/tables` now reports `T1` as `occupied`.

### S3 — dine-in auto-fire (P2)
1. After S2, **assert** every line on that ticket has a non-null `fired_at`.
2. **Assert** an online (S1) ticket's lines have `fired_at == null`.

### S4 — the printed QR keeps working (P1)
1. Open `http://127.0.0.1:5173/order/<T1.qr_token>` (the exact URL a table tent
   encodes).
2. **Expect** the menu with the table name shown (dev serves it inline).
3. Place an order and **assert** it is `dine_in` on `T1` (same as S2) — proving
   the printed artefact still works.

### S5 — add-ons are priced server-side (P4a)
1. `POST /public/store/{c}/{s}/orders` with
   `modifiers: [{name: "Oat", price_delta: "-100.00"}]`.
2. **Assert** 201 and `unit_price == "3.50"` (the request's delta is ignored).
3. `POST` with `modifiers: [{name: "Sprinkles"}]` → **assert** 400.

### S6 — a retail store's POS hides online tickets (P3)
1. On a store **without** the `tables` capability, create an online order.
2. **Assert** it appears in `Order`s but the POS held drawer does **not** list it
   (unit-covered by `heldOrdersForRegister`); a `tables` store lists every
   ticket.

### S7 — rotation retires the old code (P5)
1. `POST /dining/tables/{T1}/rotate-qr`.
2. **Assert** the returned `qr_token` differs and `GET /public/order/{old}` is
   404 while `GET /public/order/{new}` is 200.
3. In the browser, open the **old** dine-in route → **expect** "This table link
   is no longer active…".

### S8 — table pages are not indexable (P1)
1. Open the dine-in route.
2. **Assert** `<meta name="robots" content="noindex">` is present.

## 5. Evidence

- A screenshot per browser step (product page with an add-on chosen, storefront
  store page, dine-in page, expired-code page). **Caveat:** the browser tool's
  `screenshot` needs a visible desktop window; when it is not visible, fall back
  to DOM reads (`browser.evaluate`) plus the API assertions, which is what the
  verified run did.
- The JSON of the tickets created, copied from the API assertions.

## 6. Automation map

| Scenario | Automated where |
|---|---|
| S1, S2 | `apps/web/e2e/storefront-modifiers.spec.js`, `storefront-dine-in.spec.js` |
| S3 | `chmabapos_api/tests/test_online_ordering.py` |
| S4 | `test_online_ordering.py` (legacy token path) |
| S5 | `test_online_ordering.py::test_public_menu_exposes_modifiers_and_reprices` |
| S6 | `apps/web/src/lib/heldOrders.test.js` |
| S7, S8 | `test_dining.py::test_rotating_a_table_qr_retires_the_old_code`, `storefront-dine-in.spec.js` |

The manual run below exists to confirm the **integrated** behaviour in a real
browser, which no single automated spec covers end to end.

## 7. Verified run (2026-10-19, local dev)

Fixture: a fresh `pro` restaurant ("Manual E2E Co" / "Table Counter"), a required
"Milk" group (Oat +0.50), a "Flat White" at $3.00 carrying that group, and tables
T1/T2. Driven with a real browser (OpenCode browser tools) for the UI steps and
direct API calls for the assertions. **20/20 API assertions passed.**

| Step | Observed |
|---|---|
| Product page, before choosing | add button `disabled`, hint "Choose the required options above.", group `MILK · REQUIRED · CHOOSE 1` |
| Product page, after choosing Oat | price `$3.00 → $3.50`, add enabled, `aria-pressed=true`, hint gone |
| Store page card | the add-on product shows **Choose**; the other three keep add buttons; cart bar "1 item · $3.50" |
| Placing the order | **"Order placed"** |
| Ticket (online) | `source=online`, `order_type=takeaway`, `table_id=null`, line `Oat/0.50`, `unit_price=3.50`, `subtotal=3.50`, lines **not** fired |
| Dine-in route `…/t/<T1 token>` | `Table T1` badge, `Dine-in`, `meta robots = noindex` |
| Dine-in order | **"Your order is with the kitchen · T1."**; ticket `source=qr`, `order_type=dine_in`, `table_id=T1`, `label=T1`, every line **fired**; `T1` → `occupied` |
| Printed QR (`:5173/order/<token>`) | menu shows the store name and **"T1"** |
| Tampered add-on price | request `price_delta=-100.00` → 201 but `unit_price=3.50` (catalogue wins) |
| Unknown add-on | `Sprinkles` → **400** |
| Rotation (T2) | new code issued, old code **404**, new code 200 |
| Retired code in the browser | "This table link is no longer active - please ask a member of staff." |

### Notes from the run

- **Screenshots were not captured:** `browser.screenshot` requires a visible
  desktop window and reported *"Screenshot needs a visible tab… keep its desktop
  window visible."* Evidence here is DOM reads plus API assertions.
- **Bring the stack up on a spare port.** A long-running API on `:8000` served a
  **stale build** (its `/openapi.json` had 2 paths and none of the current
  routes), so the run used `:8001` from the working tree.
- The fixture company and its user were **deleted afterwards**, so a manual run
  leaves the dev database as it found it.


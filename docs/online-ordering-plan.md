# Online ordering & QR-at-table

Status: Implemented (Phases 1–2) — public tokenised menu + order submit, settings toggle with per-table QR, the public customer page and staff Online/QR badges shipped (#419/#423/#426/#429/#430). Phase 2 (online KHQR before confirmation) shipped: a store can require online payment, the public page shows a KHQR and confirms once paid, funded by the merchant's ChmabaPay link.
Owners: Engineering
Scope: design only — no code changes in this document's PR.

Related: `docs/restaurant-mode.md` (§9 lists online ordering as out of scope
today), `docs/capabilities-and-gaps.md` (G11), `chmabapos_api/app/models.py`
(`HeldOrder`, `DiningTable`, `Order`), `docs/trade-in-plan.md` (capability-gated
sub-features).

## 1. Goal

Let a customer place an order **without the cashier**: scan a QR at the table, or
open a public link, browse the menu, build a cart and submit it. The order lands
in the existing Kitchen/POS flow as an open ticket, so staff keep working the same
board.

## 2. Current state

- Open tickets are `HeldOrder` rows (table, order type, JSON lines); the Kitchen
  and Floor already read them, and the POS can resume/settle them.
- `DiningTable` has a `name`; there is no per-table code.
- Stores can already be enabled with feature packs/capabilities, and the API has
  public, unauthenticated endpoints (health, public stats) as a pattern.
- There is **no** customer-facing ordering surface and no unauthenticated way to
  read a store's menu.

## 3. Design principles

1. **One order engine.** A customer order is an open ticket (or a paid order),
   not a parallel order system. It appears on the same Kitchen board and is
   settled through the same checkout.
2. **Public surface is read-menu + submit-order only.** No catalog writes, no
   inventory reads beyond availability, no customer PII beyond what the customer
   types.
3. **Tokenised, revocable access.** A store opts in and gets a public slug/token;
   per-table QR codes carry the table. Tokens can be rotated or disabled.
4. **Pay-at-counter first.** MVP submits an unpaid ticket; online KHQR payment is
   a later phase.
5. **Additive migrations**, capability/plan gated.

## 4. Data model

- **`Store`**: `public_order_enabled` (bool), `public_order_token` (opaque, unique).
- **`DiningTable`**: `qr_token` (opaque, unique per store) — encodes the table.
- **`HeldOrder`**: `source` (`pos | qr | online`, default `pos`) and
  `customer_note` (Text, nullable). Reuses the existing status/table/order-type.

No new order table in v1. A dedicated `PublicOrder` staged table is only worth it
if submissions need moderation before becoming tickets (see §10).

## 5. Public API (unauthenticated, token-scoped)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/public/order/{token}` | menu + store branding for the token (table name when a table token) |
| `POST` | `/public/order/{token}` | submit a cart → creates a `HeldOrder` (`source=qr/online`) |

Both are rate-limited per token and return only active products with a computed
**available** flag (in stock), never costs or supplier data. A submitted order is
validated server-side (active products, stock, modifiers) and priced with the
same rules as the POS.

## 6. Staff surface

- **Kitchen/Floor**: tickets show an **Online** / **QR** badge and the customer's
  note; the drawer and settle flow are unchanged.
- **Settings → Online ordering** (`apps/web`): enable, copy the public link, and
  print/download per-table QR codes (a simple QR image linking to the table URL).
- Nothing new on the POS itself; settling an online ticket is the normal flow.

## 7. Customer surface

A small **public web page** (`apps/web` route or a lightweight separate bundle):

1. Menu grouped by category (reuses the catalog images/names/prices).
2. Cart with modifiers and quantities.
3. Submit → shows a confirmation with the table label and the order total; pay at
   the counter (v1).

No login, no customer account. Phone number is optional and only if the store
enables "call me when ready".

## 8. Payment

Phase 1: pay-at-counter (the ticket is created unpaid; staff settle as usual).
Phase 2: online KHQR (shipped) — the customer pays via the existing ChmabaPay/KHQR
machinery before the ticket is confirmed. Payment state lives on the held ticket
(`held_orders.payment_*`), the public page polls
`GET /public/order/{token}/payment/{held_id}`, and settlement marks the ticket paid.

## 9. Migration

One additive revision: `stores.public_order_enabled`, `stores.public_order_token`,
`dining_tables.qr_token`, `held_orders.source`, `held_orders.customer_note`.
Chained to the current single head.

## 10. Rollout

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/online-ordering-plan` | this document |
| 1 | `feat/online-ordering-core` | public token + menu/submit endpoints, `HeldOrder.source`, staff badges, settings toggle + QR |
| 2 | `feat/online-ordering-ui` | customer menu/cart/checkout page |
| 3 | `feat/online-ordering-payment` | online KHQR before confirmation — ✅ shipped |

## 11. Open decisions

1. **Direct-to-`HeldOrder` vs a staged `PublicOrder`.** Recommendation: v1 creates
   the ticket directly (staff already triage the board); introduce a staged table
   only if stores want to moderate submissions.
2. **Token model.** Recommendation: one store token for the public link **plus** a
   per-table token for QR, both revocable.
3. **Availability source.** Recommendation: show a simple in-stock/out-of-stock
   flag, not live counts (avoid leaking inventory levels and racing the POS).

## 12. Out of scope

- Delivery dispatch and driver tracking (G12).
- Customer accounts, loyalty accrual from public orders, saved cards.
- Multi-language menus and per-item scheduling (happy hour).
- Table reservations/waitlists (G10).

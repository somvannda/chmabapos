# Orders page improvement

Status: Planned — this document plans the work; it makes no code changes.

Owners: Engineering

Scope: the store-facing **Orders** view at `/orders` in `apps/web`
(`LiveOrdersWithReceipt` in `apps/web/src/features/sales.jsx`) and the backing
`GET /orders` API in `chmabapos_api/app/api/v1.py`.

Related: `docs/offline-mode-plan.md` (held orders/refresh),
`docs/online-ordering-plan.md` (open tickets),
`apps/web/src/features/reports.jsx` (period presets + summary UI),
`apps/web/src/lib/dashboard.js` (open/unpaid-order nudges), `docs/printing.md`
(receipt reprint), `docs/roles-permissions-audit.md` (who may cancel/void/refund).

## 1. Goal

Make the Orders page the place staff go to **find a specific order fast,
understand the store's current sales position, and act on an order without
leaving the page**. Today the page is a flat, client-filtered list that stops
working once an order scrolls off the first page: no search, no date range, no
server-side status filters, no summary of the day, and an action row that grows
to seven icon buttons.

Concretely we want:

1. **Findability** — search by order number or customer, and filter by real
   server-side criteria (date range, status, order type, cashier, delivery
   state) instead of the current client-side status tabs over the latest 50.
2. **Context** — day/period summary tiles (gross sales, order count, open
   balance, pending payments) that stay correct as orders accumulate.
3. **Actionable rows** — one clean overflow menu per row, with the high-frequency
   actions (view, reprint, email receipt) visible and everything else one click
   away, gated by role and plan features exactly as today.
4. **Consistent UX** — loading, empty, and error states plus dark-mode parity
   that match the rest of the workspace.

## 2. Current state

- `GET /orders` returns the latest `limit` (≤100) orders for the store, ordered
  newest first, with `status`, `limit`, `offset` query params. There is **no
  search, no date-range, no order-type/cashier filter, and no aggregate counts**.
- `OrderRead` (schemas.py `:1775`) already carries everything the page renders:
  `order_number`, `status`, `customer_name` + `customer`, `order_type`,
  `table_id`, `total`/`subtotal`/`discount`/`tax`/`tip`, `deposit`,
  `amount_paid`, `balance_due`, `refunded_amount`, `pickup_at`, `delivery_*`,
  `created_at`/`paid_at`, `items`, `payments`, `tenders`.
- The view (`apps/web/src/features/sales.jsx` `LiveOrdersWithReceipt`) renders:
  header (store name + **Refresh orders**), three `SmallStat` tiles (*Orders
  loaded*, *Paid*, *Pending*), client-side filter tabs (all/paid/pending/pickup/
  cancelled), a table (Order / Customer / Items / Payment / Status / Total /
  Actions), a client-side **Load more** button, and a cancel/void `ConfirmDialog`.
- Row actions today: view receipt, print receipt, edit pickup, print deposit,
  collect balance, refund, cancel/void — up to **seven** `IconButton`s on a
  purchase-order row, with no overflow. Payment-failed orders show an inline
  "retry" hint. Status tabs and the stats tiles filter/count only the **loaded**
  page, so they drift from reality once there are more than 50 orders.

## 3. Design principles

1. **Server-side filtering is source of truth.** Tabs, search and date range map
   to query params; the client never recounts the full store. Aggregates come
   from the API, not from `orders.length`.
2. **Same order engine.** The page only *reads*/acts on the existing
   `Order`/`Payment`/`Refund`/`HeldOrder` model. No new order system.
3. **Reuse existing actions.** Collect, deposit print, refund, cancel/void,
   email-receipt and print already exist as APIs and modals; this plan changes
   how they are surfaced, not how they behave.
4. **Permission and plan gating unchanged.** `canManage` (owner/manager/
   inventory_manager) and `refunds` plan feature keep deciding row actions; the
   `memberRole` and `workspace.plan_features` plumbing already exists.
5. **Additive API only.** New query params and one small aggregates endpoint;
   existing consumers (`dashboard`, `deliveries`, refunds) are untouched.

## 4. API changes

### 4.1 Extend `GET /orders`

Add query params to `list_orders` (v1.py `:5379`):

| Param | Type | Meaning |
|---|---|---|
| `search` | `str?` | case-insensitive match on `order_number` **or** customer name/phone via the existing `Order.customer` relation. |
| `from_date` / `to_date` | `date?` | filter `Order.created_at` (inclusive). |
| `order_type` | `str?` | `takeaway`/`dine_in`/`delivery` / `pickup` as stored. |
| `cashier_id` | `UUID?` | filter on the order's recorded cashier/creator. |
| `delivery_status` | `str?` | when `order_type=delivery` (reuse logic from `list_deliveries`). |
| `has_balance` | `bool?` | `balance_due > 0` (find open/pending payment fast). |

Status, `limit`, `offset` already exist and are reused. Keep `limit ≤ 100`;
pagination stays offset-based. Search should use an indexable prefix/ilike and
be capped (`max_length=80`) like the admin search params.

### 4.2 Aggregates — `GET /orders/summary`

New lightweight endpoint, same `StoreContext` guard, returns for a period
(default: today, in store timezone):

- `orders_count`, `paid_count`, `pending_count` (status counts),
  `open_balance` (`sum(balance_due)` across open orders),
  `gross_total` / `net_total` for `paid` orders in the period,
  `refunded_total`.
- `refunds` plan feature not required to read it (counts are read-only).

This keeps the summary tiles truthful without loading every order. Keep the
period parameters (`from_date`/`to_date`) shared with 4.1.

## 5. UI plan (`apps/web`)

Keep `LiveOrdersWithReceipt` as the component but restructure its render into
small presentational pieces (inline in `sales.jsx` to stay consistent with the
file's style, or extracted to `features/widgets.jsx` if they grow).

### 5.1 Filter bar (server round-trip)

Replace the client-only tab strip with a toolbar that drives `GET /orders`:

- **Search input** (debounced ~300ms) — order number or customer name/phone.
- **Date range preset dropdown** — Today / Last 7 days / Last 30 days / This
  month / Custom, matching the presets in `features/reports.jsx`.
- **Status pills** — All / Paid / Pending / Pickup / Cancelled (now server-side).
- **Order type + delivery state** (collapsible "More filters") for stores on
  `table_management`.
- URL-ish state: keep filters in local state; no requirement to deep-link.

The "Refresh orders" button is retained; it now re-runs the current query.

### 5.2 Summary tiles

Allow the API summary to replace the drift-prone tiles:

- Today's **gross sales**, **orders count**, **open balance** (money customers
  still owe on pickup/reservation orders), and **pending payments**.
- When a status pill is active, the tiles annotate that filter (e.g. "Paid in
  this period") rather than pretending to be whole-store totals.

### 5.3 Row actions → one overflow menu

Group actions so a row never shows more than 3 icon buttons:

- **Always visible**: View (opens receipt), Print receipt.
- **Overflow (⋯) menu**: Email receipt, Edit pickup, Print deposit receipt,
  Collect balance, Refund order, Cancel/Void — each still role/plan gated and
  each opening the exact modal used today. Payment-failed rows keep the inline
  "retry" hint and a prominent **Collect balance** affordance.
- Add an **Email receipt** action using the existing
  `POST /orders/{id}/email-receipt` (currently only surfaced from the receipt
  view) when the store has `email_receipts`.

### 5.4 Table polish

- Show the **order type** badge under Order (already available via
  `ORDER_TYPE_LABELS`); optionally expose `created_by` as a cashier name on
  `OrderRead` (cheap additive field) if a cashier column earns its place.
- Keep the **Payment method** chip (from `payments[0].provider`/`tenders`) as now.
- Right-align money, keep `formatCurrencyAmount`; show *Due X* and *Partially
  refunded* states as today.
- Mobile: keep `mobile-table` responsive rules; the overflow menu is the escape
  hatch for the icon-heavy rows.
- States: skeleton load for first fetch, the existing empty-state copy, and a
  retry on error (reuse current error banner + refresh).

### 5.5 Dark mode parity

The page already carries most theme tokens; audit the new toolbar/search/overflow
menu against `styles.css` dark tokens and `index.css`/`#17181c` shell like the
rest of the workspace (see `lib/darkMode.test.js`).

## 6. Out of scope / explicitly not doing

- A full **order detail drawer** — review/refund/print already open as modals;
  do not build a parallel screen. Add only if a later spike shows a need for
  line-level "everything about this order" without the receipt.
- Bulk actions, CSV export, and order editing — no API support and out of
  scope for a read/act page.
- Cross-store/consolidated Orders — that is the Reports/Admin domain.
- Changing the order engine, payment flows, or refund logic.
- Public/customer-facing order tracking.

## 7. Phased plan

| Phase | Work | Files (primary) | Exit criteria |
|---|---|---|---|
| **P1 — API filters** | Search, date range, order type, cashier, `has_balance` on `list_orders` | `chmabapos_api/app/api/v1.py`, `apps/web/src/api.js` | `GET /orders?search=&from_date=&to_date=` returns filtered rows; API tests cover each param. |
| **P2 — Summary endpoint** | `GET /orders/summary` + `OrderSummaryRead` schema | `v1.py`, `chmabapos_api/app/schemas.py`, `api.js` | Summary returns period-true aggregates; tests for empty store, refunds, open balance. |
| **P3 — Filter bar + truthful tiles** | Toolbar drives server queries; tiles read summary; refresh re-queries | `apps/web/src/features/sales.jsx` | Debounced search/range change re-fetches; tiles match API; no recount of `orders.length`. |
| **P4 — Row overflow + email receipt** | Group row actions, add Email receipt | `sales.jsx` | ≤3 visible icons per row; every action opens the same modal as today; role/plan gating preserved. |
| **P5 — States & dark mode audit** | Loading/empty/error polish, `mobile-table`, dark tokens | `sales.jsx`, `styles.css` | Manual pass in light+dark on desktop+mobile; existing `darkMode.test.js` still green. |

## 8. Tests

- **API** (pytest): `list_orders` search (order number, customer name, customer
  phone), date-range inclusivity, `has_balance`, `order_type`, cashier filter,
  param validation/limits; `orders/summary` counts and sums incl. refunds and
  empty store.
- **Web** (vitest, following `src/lib/*.test.js` style): a pure helper for
  building the query params from filter state; status/delivery label mapping.
- **E2E/manual**: search → single result; deep pagination; pickup order with
  open balance shows Due + Collect in overflow; refund gating by role.

## 9. Rollout

- Additive API + new query params mean no breaking change; old clients keep
  working with the 50-row default.
- Ship UI behind nothing special (it is a pure client change); coordinate the
  summary endpoint deploy with P3.
- Follow `AGENTS.md` per PR: `feat/` or `chore/` branches, regenerate anything
  versioned, green CI on API + Web, merge via PR.

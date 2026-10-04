# Trade-in & buyback

Status: Implemented — device intake at an assessed value, applied to a sale as a credit, with reporting (#401/#402/#404).
Owners: Engineering
Scope: design only — no code changes in this document's PR.

Related: `docs/capabilities-and-gaps.md` (G7), `docs/serial-condition-report.md`
(condition grading), `chmabapos_api/app/models.py` (`ProductSerial`, `Order`,
`OrderTender`), `docs/product-model.md`.

## 1. Goal

An electronics shop should be able to **take a customer's device in** — grade it,
agree a value, and apply that value against a purchase (trade-in) or pay it out
(buyback) — and put the device into stock for resale, all in the normal POS flow.

## 2. Current state

- Serials track individual units end to end: `ProductSerial` has `imei`,
  `condition_grade`, `battery_health`, dual warranty and a `service ticket` log.
- `ProductSerial.order_item_id` links a sold unit to the line that sold it.
- Checkout takes tenders of kind `payment` (cash/KHQR) and one `change` tender;
  refunds reverse a sale.
- A device received from a supplier is stocked via `StockMovement` +
  `ProductSerial` at a cost basis.
- There is **no** flow for a device received **from a customer**.

## 3. Design principles

1. **A trade-in is stock intake plus a credit, not a new order system.** The
   taken device becomes a normal graded serial on the shelf; the value is applied
   to the sale as a credit. Resale then uses the existing serial flow.
2. **Value is a tender, not a discount.** A trade-in credit reduces the amount due
   through the tender machinery, so discounts/margin and approval thresholds keep
   their meaning.
3. **Snapshot the assessment.** Condition, IMEI and agreed value freeze on the
   trade-in record; the serial it creates carries the same grade.
4. **Additive migrations**, backward compatible.
5. **Capability-gated**, like the rest of electronics.

## 4. Data model

### 4.1 `TradeIn`

New company/store-scoped table:

- `id`, `company_id`, `store_id`
- `customer_id` (nullable FK) — who traded it in
- `product_id` — the catalog product the device is stocked as (e.g. "iPhone 13
  128GB (used)")
- `serial_number`, `imei` (nullable) — identity of the accepted unit
- `condition_grade`, `battery_health`, `condition_report` (JSON) — the assessment
- `assessed_value` (`Numeric(12,2)`) — the agreed credit
- `kind` — `trade_in` (credit against a sale) | `buyback` (paid out)
- `status` — `accepted` | `void`
- `order_id` (nullable FK) — the sale the credit was applied to
- `serial_id` (nullable FK) — the `ProductSerial` created for resale
- `notes`, `created_by`, `created_at`

### 4.2 Stock intake

Accepting a trade-in creates:

- a `ProductSerial` (status `in_stock`, `store_id`, `condition_grade`,
  `battery_health`, `imei`, `cost_price = assessed_value`), and
- a `StockMovement` (`movement_type="opening_balance"`, `reason="trade_in"`,
  `unit_cost=assessed_value`).

Stock lands at the **assessed value**, so margin on resale is real, and the
existing grade report (`serial-condition-report.md`) picks it up.

### 4.3 Applying the credit

- **Trade-in:** the order gains a tender of `kind="payment"` / `method="trade_in"`
  for the agreed value; the customer pays the remainder. The `TradeIn.order_id`
  links back for reporting.
- **Buyback:** no order; the shop pays the customer (cash) — recorded as a
  trade-in with `kind="buyback"` and a negative-cash tender on a zero-value order,
  or simply as a stand-alone cash-out record. Recommendation: a stand-alone
  record first; a paying-out order later.

## 5. Control & approvals

- A trade-in above a configurable threshold can require manager approval, reusing
  the existing approval policy machinery (like discounts/refunds).
- The IMEI must be unique among in-stock serials (`uq_serial_company_number` gives
  that already). A blacklist/IMEI-registry lookup is out of scope.

## 6. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/trade-ins` | assess + accept a device (creates the serial + movement) |
| `GET` | `/trade-ins` | list, filter by date/kind/status |
| `POST` | `/trade-ins/{id}/void` | reverse an accepted trade-in before it is sold |
| `GET` | `/trade-ins/{id}` | one record |

Order create accepts the credit through the existing `tenders` list (a
`trade_in` method with the `trade_in_id`), so pricing/tax/change logic is reused.
Regenerate `openapi.json`.

## 7. Web UI (`apps/web`)

- **POS**: a **Trade-in** action beside the cart opens the assessment form
  (product, serial/IMEI, condition grade, battery, value) and adds a credit
  line/tender; checkout nets it against the total.
- **Orders**: a trade-in badge/amount on the sale.
- **Catalog**: the created serial shows under the product's serials with its grade
  and trade-in cost.
- Behind the `serials` capability (electronics).

## 8. Migration

One additive revision creating `trade_ins`, chained to the current single head.
No changes to `orders` (the credit rides on `order_tenders`).

## 9. Rollout

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/trade-in-plan` | this document |
| 1 | `feat/trade-in-core` | `TradeIn`, stock intake, credit tender, tests |
| 2 | `feat/trade-in-pos` | POS assessment form + credit line |
| 3 | `feat/trade-in-reports` | trade-in value in reports (COGS/intake) |

## 10. Open decisions

1. **Credit as a tender (recommended) vs a discount.** Tender keeps discount
   semantics and approval thresholds clean; also supports buyback payouts.
2. **Stock cost basis = assessed value (recommended)** vs catalog cost — the
   former makes resale margin truthful.
3. **Buyback payout timing.** Recommendation: record the intake first; add a
   cash-out order/expense in a later phase.

## 11. Out of scope

- Automated price guides / market valuation APIs.
- IMEI blacklist / stolen-device registry lookups.
- Cross-store trade-in (the device is stocked at the accepting store).
- Supplier credit notes for traded devices.

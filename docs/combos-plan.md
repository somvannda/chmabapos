# Combos & meal deals

Status: Implemented — fixed bundles (#376/#380), choose-from-a-set groups (#386/#387) and combo reporting (#389) shipped; see `docs/combos-choice-plan.md` for the choice groups.
Owners: Engineering
Scope: design only — no code changes in this document's PR.

Related: `docs/product-model.md` (product/variant/modifier model),
`docs/capabilities-and-gaps.md` (G4), `chmabapos_api/app/models.py`.

## 1. Goal

Let a merchant sell a **combo / meal deal**: a named bundle of products for a
single price (e.g. "Burger + Fries + Drink — $6.50"), usable at the POS like any
product. Common for café, restaurant and mart.

## 2. Current state

- A product is a single sellable row with optional variants, modifiers and (for
  food) recipe-based ingredient depletion (`Modifier.ingredient_product_id`).
- `OrderItem` snapshots name/sku/price/variant/modifiers and deducts stock for
  the product (and, for recipe modifiers, the ingredient).
- There is **no** notion of a bundle: today the only way to sell "burger + fries"
  together is to ring them up as separate lines.

## 3. Design principles

1. **A combo is a product-shaped sellable, not a new order system.** It appears
   in the POS catalog, price is a number the merchant sets, and it snapshots
   onto the order like any line.
2. **No combo inventory.** A combo is logical: its components carry the stock.
   Selling a combo deducts each component's stock (like a recipe), never a
   "combo balance".
3. **Snapshot on sale** (per `product-model.md` §3): the combo name, price and
   component list freeze onto the order line.
4. **Additive migrations**, backward compatible.
5. **Phased**: fixed combos first; customer-choice combos later.

## 4. Data model

### 4.1 Combo (Phase 1)

- `Combo(id, company_id, name, sku?, image?, price, is_active, position, created_at, updated_at)`
- `(company_id, sku)` unique when a SKU is set (optional; a combo can be
  barcode-less).
- `price` is the **sale price** of the whole bundle. The merchant decides how it
  relates to the component sum (the UI can show "components $7.20 → combo
  $6.50").

### 4.2 Combo components (Phase 1)

- `ComboItem(id, combo_id, product_id, variant_id?, quantity, position)`
- Components are the products (and optional variant) the combo includes.
- A combo with no items is invalid.

### 4.3 Customer choice (Phase 2)

Some deals are "choose any 1 main + 1 drink":

- `ComboGroup(id, combo_id, name, min_select, max_select, position)`
- `ComboGroupOption(id, group_id, product_id, variant_id?, price_delta)`

Phase 1 keeps a flat `ComboItem` list; Phase 2 adds groups for choice.

## 5. Order snapshot

`OrderItem` gains (all nullable, additive):

| Field | Type | Notes |
|---|---|---|
| `combo_id` | `UUID?` | FK to `Combo` (SET NULL) |
| `combo_name` | `String(180)?` | snapshot |
| `combo_components` | `JSON?` | `[{product_id, variant_id, name, sku, quantity, unit_price?}]` snapshot |

One `OrderItem` represents the combo (its `product_id` points at the combo's
**lead** component or a synthetic rule; see §10). The component list is used for
receipts and, crucially, for **stock depletion and refunds**.

## 6. Pricing, tax and stock

- **Price:** the combo's `price` is a single line total (`unit_price * quantity`).
  Component `unit_price`s are kept only for reporting/COGS, not summed into the
  bill.
- **Tax:** the combos tax at the order/store rate (Phase 1). Per-component tax is
  out of scope (the store already has one `service_tax_rate`; per-product tax
  exists but distributing it across a combo is a Phase 3 question — see §10).
- **Stock:** selling a combo deducts each component via `StockMovement`
  (`movement_type="sale", reason="combo"`), exactly like recipe depletion today.
  FEFO applies to batch-tracked components.
- **Serials:** a combo containing a serial-tracked component is out of scope in
  v1 (a bundle with a tracked phone is unusual); reject or defer.

## 7. POS UX

- Combos appear in the catalog grid alongside products (a distinct badge) and in
  search.
- Tapping a combo adds **one** cart line ("Burger + Fries + Drink") at the combo
  price; the cart shows the components as sub-text.
- Combos are not hold/ticket-specific; they flow through held tickets like any
  line (once Phase 1 lands, `HeldOrder` lines already carry name/price).

## 8. API

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/combos` | list / create |
| `PATCH/DELETE` | `/combos/{id}` | edit / remove |
| `GET` | `/combos/{id}` | one combo + components |

Combos are catalog data (company-scoped, `catalog_roles`). The order create
payload gains optional `combo_id` on a line; the server expands components,
prices and depletes stock. Regenerate `openapi.json`.

## 9. Rollout order

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/combos-plan` | this document |
| 1 | `feat/combos-core` | `Combo`/`ComboItem`, CRUD, order-line snapshot + component stock depletion, POS add + receipt |
| 2 | `feat/combos-choice` | `ComboGroup`/`ComboGroupOption` (choose-from-a-set) |
| 3 | `feat/combos-reports` | combo sales + margin reporting |

## 10. Open decisions

1. **Lead component:** an `OrderItem.product_id` is required today. Options:
   (a) point it at a designated "lead" component; (b) make a hidden combo
   product row; (c) relax `product_id` to nullable for combo lines.
   Recommendation: **(a)** for Phase 1 (no schema change to `product_id`), move
   to (c) if it gets awkward.
2. **Price display vs accounting:** one bill line (simple) vs distributing the
   combo price across components for per-item tax/margin. Recommendation: one
   line in v1; revisit if per-component tax is needed.
3. **Refunds:** refunding a combo must restore each component's stock. Confirm
   the refund flow expands `combo_components` the same way.
4. **Combos with choices** (Phase 2) and **modifiers inside a combo** (Phase 3?):
   keep out of v1.

## 11. Out of scope

- Nested combos (a combo containing a combo).
- Combos containing serial/lot-tracked components (v1).
- Time-limited / happy-hour combo pricing.
- Cross-store combo availability overrides.

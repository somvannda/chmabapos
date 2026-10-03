# Combos with choice (Phase 2)

Status: Draft for review
Owners: Engineering
Scope: design only — no code changes in this document's PR.

Related: `docs/combos-plan.md` (Phase 1: fixed combos), `docs/capabilities-and-gaps.md`
(G4), `chmabapos_api/app/models.py`.

## 1. Goal

Some deals let the customer pick: "choose any 1 main + 1 drink — $6.50". Phase 1
sells a **fixed** bundle; Phase 2 adds **choice groups** so one combo can offer a
set of alternatives, each optionally at a price delta.

## 2. Current state (Phase 1)

- `Combo` / `ComboItem` describe a fixed bundle; `Combo.price` is the bundle price.
- An order line may carry `combo_id`; the server expands `combo.items`, snapshots
  them into `OrderItem.combo_components`, prices the line at `Combo.price`, and
  depletes each component's stock (FEFO for batches).
- Refunds/reversals restore from the same `combo_components` snapshot.

## 3. Design principles

1. **Additive.** Phase 1 combos keep working unchanged; a combo with no groups is
   exactly a Phase 1 combo.
2. **Flat on the order line.** The order still stores **one** `OrderItem` per combo;
   the chosen options are folded into the existing `combo_components` snapshot.
   No new order-item structure.
3. **The bundle price stays authoritative.** Option `price_delta` is added per
   unit; component `unit_price`s remain reporting-only, as in Phase 1.
4. **Stock lives on the concrete products.** Deduct fixed components and the
   **chosen** options; never a "combo balance".

## 4. Data model

### 4.1 New tables

- `ComboGroup(id, combo_id, name, min_select, max_select, is_required, position)`
  - `min_select`/`max_select` bound how many options the cashier picks.
  - `is_required` is derived sugar (`min_select >= 1`) kept explicit for the UI.
- `ComboGroupOption(id, group_id, product_id, variant_id?, price_delta, position)`

A combo may have **both** fixed `ComboItem`s and `ComboGroup`s. `combo.items`
(fixed) and `combo.groups` (choice) are independent lists.

### 4.2 Example

"Combo A — $6.50": fixed `Fries ×1`; group "Main" (min 1, max 1): Burger,
Chicken; group "Drink" (min 1, max 2): Cola, Water.

## 5. Selection payload

`OrderItemRequest` gains an optional list:

```
combo_selections: [{ group_id, option_id, quantity }]
```

- One entry per chosen option (repeat `option_id` with a larger `quantity`, or a
  single entry with `quantity`, for multi-select groups).
- The server validates: the combo has that group; the option belongs to the
  group; `min_select <= Σ quantity <= max_select`; and required groups are
  satisfied. Unknown/extra groups are rejected.
- A combo whose groups are all optional can be sold with no selections.

## 6. Order snapshot

`OrderItem.combo_components` keeps its Phase 1 shape for fixed items and gains
the chosen options, each tagged with the group it satisfied:

| field | notes |
|---|---|
| `product_id`, `variant_id`, `name`, `variant_name`, `sku` | as Phase 1 |
| `quantity` | component quantity (fixed `ComboItem.quantity`, or the picked option quantity) |
| `unit_price` | catalog price at sale time (reporting only) |
| `group_id`, `group_name` | present only for choices; absent for fixed items |

Receipts show choices under the combo line ("Main: Chicken · Drink: Cola").
Refunds/reversals already iterate `combo_components`, so they restore choices
too **with no extra code** — this is the main reason to keep the flat snapshot.

## 7. Pricing, tax and stock

- **Price:** `line_total = (combo.price + Σ option.price_delta × quantity) × qty`.
- **Tax:** unchanged from Phase 1 (one bill line at the store rate).
- **Stock:** deduct fixed components and every chosen option, each via a
  `StockMovement` (`reason="combo_sale"`), with FEFO for batch-tracked items.
- **Serials:** still out of scope for combos.

## 8. API

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/combos` | now includes/accepts `groups` alongside `items` |
| `PATCH/DELETE` | `/combos/{id}` | edit / remove |

`ComboRead` gains `groups: [{ id, name, min_select, max_select, is_required, options: [{ product_id, variant_id, name, sku, price_delta }] }]`.
Order create accepts `combo_selections` as in §5. Regenerate `openapi.json`.

## 9. POS UX

- A combo **with groups** opens a picker (one section per group, honouring
  min/max) before it is added; a combo **without groups** adds in one tap, as today.
- The cart line shows the chosen options as sub-text.
- The manager's Combos modal gains group editing (add group, add options, set
  min/max) next to the fixed items.

## 10. Migration

One additive revision creating `combo_groups` and `combo_group_options`, chained
to the current single Alembic head. No changes to existing tables.

## 11. Rollout

| # | Branch | Scope |
|---|---|---|
| 1 | `feat/combos-choice-core` | models, CRUD, selection validation, order expansion + choice stock depletion, tests |
| 2 | `feat/combos-choice-ui` | POS group picker, cart sub-text, group editing in the Combos modal |

## 12. Open decisions

1. **Price delta location:** on the option (per-option) vs on the group (per
   selection). Recommendation: **on the option** — simplest and matches modifiers.
2. **Multi-select quantity semantics:** allow picking the same option more than
   once (quantity) vs distinct options only. Recommendation: allow quantity, cap
   the summed quantity by `max_select`.
3. **Required groups:** enforce `min_select` server-side (yes) and mirror it in
   the UI; keep `is_required` as display sugar only.

## 13. Out of scope

- Nested combos and combos-within-choices.
- Per-choice tax or margin distribution (stays one bill line).
- Time-limited choice sets.
- Combining choice groups with per-line modifiers.

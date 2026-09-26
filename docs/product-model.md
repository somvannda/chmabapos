# Product model

This document is the single source of truth for how Chmaba represents products,
their variations, add-ons and tracked units. Code (models, schemas, API and UI)
must match it.

Status: Draft for review
Owners: Engineering
Scope: Product management data model and the vertical field packs (electronics,
coffee, mart, shop). No code is changed by this document.

## 1. Goal

Today a product is a single flat row that only fits a simple shop. A workspace
can be an **electronics store**, a **coffee shop**, a **mart** or a **general
shop**, and each vertical needs different product information:

| Need | Electronics | Coffee | Mart | Shop |
|---|---|---|---|---|
| Barcode / UPC scan | ✓ | – | ✓ | ✓ |
| Brand / model | ✓ | – | ✓ | – |
| Serial / IMEI + warranty | ✓ | – | – | – |
| Variants (storage/color/size/pack) | ✓ | ✓ | ✓ | ✓ |
| Modifiers / add-ons (milk, shots, ice) | – | ✓ | – | – |
| Unit of measure / weight | – | – | ✓ | – |
| Batch / expiry | – | – | ✓ | – |

The goal is **one layered model** that serves all four verticals, with the
**electronics** pack enabled first, and the coffee, mart and shop packs added
later without a second product system.

## 2. Current state

`Product` (`chmabapos_api/app/models.py`):

- `id`, `company_id`, `category_id`, `name`, `sku`, `description`, `image`
  (base64 `Text`), `price`, `cost_price`, `is_active`, `created_at`,
  `updated_at`.
- Uniqueness: `(company_id, sku)`.
- `InventoryBalance(store_id, product_id, on_hand, reorder_point)`.
- `OrderItem` snapshots `product_name`, `sku`, `unit_price`, `quantity`,
  `line_total`.
- `Category` is company-scoped and self-referential (parent/child).
- `Store` already has a free-form `preferences` JSON column and
  `service_tax_rate`.
- `Company` has no notion of industry/vertical.

Limitations:

1. No barcode, brand, unit of measure, tax class or tracked-unit support.
2. No variants — "iPhone 15 128GB" vs "256GB" can only be two unrelated
   products, with no shared identity.
3. No modifiers — coffee add-ons cannot be represented without inventing SKUs.
4. No serials/IMEI, so electronics cannot track individual units or warranty.
5. `OrderItem` cannot record a variant, modifier or serial, so sales history
   cannot reconstruct what was actually sold once those exist.
6. Images are base64 blobs in the database; multiple images/spec sheets are not
   supported.

## 3. Design principles

1. **One model, layered.** Universal fields are strongly typed columns; the
   long tail of vertical-specific fields lives in a validated JSON `attributes`
   column. A field is promoted to a real column only when it must be indexed or
   queried (e.g. `barcode`, `serial_number`, `expiry_date`).
2. **Vertical is configuration, not a fork.** `Company.vertical` (with an
   optional per-store override in `Store.preferences`) selects which field pack
   the UI shows. The schema does not change per vertical.
3. **Snapshot on sale.** Anything that can change over time (name, sku, price,
   variant, modifiers, serial) is snapshotted onto the order line at sale time,
   following the existing `OrderItem.product_name`/`sku` precedent.
4. **Additive migrations.** Every step is a backward-compatible Alembic revision
   so existing workspaces keep working.
5. **Keep the read shape flat.** Product/variant records stay flat and
   JSON-serializable so list/search/reporting views stay cheap to query.

## 4. Layers

### 4.1 Classification

- `Company.vertical` — `electronics | coffee | mart | shop | general`
  (default `general`).
- Optional `Store.preferences.vertical` override for mixed businesses.

Drives which field pack the UI renders and which attribute schema is suggested
for a category. It does **not** enable/disable API fields — everything is
accept-reject at the schema level, not the vertical level.

### 4.2 Core product (all verticals)

Additions to `Product` (all nullable/defaulted so existing rows migrate):

| Field | Type | Notes |
|---|---|---|
| `barcode` | `String(80)` | indexed per company; scanned at POS/receive |
| `brand` | `String(120)` | electronics, mart |
| `unit` | `String(20)` | `each` (default), `kg`, `g`, `l`, `ml`, `pack` |
| `track_inventory` | `Boolean` | default `true`; services = `false` |
| `track_serials` | `Boolean` | default `false`; electronics = `true` |
| `attributes` | `JSON` | vertical-specific fields, validated per category |

`description` and `cost_price` already exist but are not surfaced in the UI;
the core work surfaces them.

### 4.3 Attributes (JSON)

`Product.attributes` and `ProductVariant.attributes` hold vertical-specific
descriptive data, e.g.:

```json
// electronics
{ "model": "iPhone 15", "storage": "128GB", "color": "Blue",
  "condition": "new", "warranty_months": 12 }
// mart
{ "origin": "Thailand", "pack_size": "24 x 330ml" }
```

Validation uses a small **attribute schema registry** keyed by vertical and,
optionally, category. Unknown keys are allowed but warned; known keys are typed
and length-bounded. Fields that must be queried (barcode, serial, expiry) are
promoted to real columns, never left in `attributes`.

### 4.4 Variants

A product can define **options** (e.g. `Storage`, `Color`, `Size`), each with
**values**, and an optional set of **variants** — concrete combinations that can
carry their own SKU, barcode, price and cost.

- `ProductOption(id, product_id, name, position)`
- `ProductOptionValue(id, option_id, value, position)`
- `ProductVariant(id, product_id, sku, barcode, name, price, cost_price,
  is_active, attributes, position)`

Inventory is tracked per variant when variants exist, and per product when they
do not. Uniqueness of `sku` and `barcode` is enforced across products **and**
variants within a company.

This one layer serves:

- electronics: `Storage` (128/256GB) × `Color` (Black/Blue)
- coffee: `Size` (S/M/L)
- mart: `Pack` (single / 6-pack / carton)
- shop: `Size` × `Color`

### 4.5 Modifiers (coffee, food)

Add-ons that change price and/or deplete ingredients **without** creating a new
SKU.

- `ModifierGroup(id, company_id, name, min_select, max_select, is_required)`
- `Modifier(id, group_id, name, price_delta, ingredient_product_id, quantity,
  position, is_default)`

Groups attach to a product or category. At sale time the chosen modifiers are
snapshotted onto `OrderItem.modifiers` (JSON). `ingredient_product_id` enables
optional recipe-based stock depletion.

### 4.6 Serials / IMEI (electronics)

`ProductSerial(id, company_id, product_id, variant_id, store_id,
serial_number, imei, status, cost_price, warranty_months, warranty_until,
purchase_order_id, order_item_id, created_at, updated_at)`

- `status`: `in_stock | sold | returned | defective`.
- `(company_id, serial_number)` unique.
- Scanned on purchase/receive (into stock) and on sale (out of stock).
- The sale records the serial on the order line.

### 4.7 Batches / expiry (mart)

`ProductBatch(id, company_id, product_id, variant_id, store_id, batch_code,
expiry_date, quantity_on_hand, cost_price, created_at)`

- Stock is consumed **FEFO** (first-expiry-first-out).
- Unit-of-measure pricing (per kg/l) rides on `Product.unit` plus a
  `price`-is-per-unit flag where needed.

### 4.8 Order line snapshot

`OrderItem` gains, all nullable so existing rows are unaffected:

| Field | Type | Notes |
|---|---|---|
| `variant_id` | `UUID` | nullable FK to `ProductVariant` |
| `variant_name` | `String(180)` | snapshot |
| `modifiers` | `JSON` | list of `{name, price_delta}` snapshots |
| `serial_id` | `UUID` | nullable FK to `ProductSerial` |

`product_name`, `sku` and `unit_price` remain and stay the authoritative
snapshot for reporting even if the product later changes or is deleted.

## 5. Vertical field packs

The pack is the set of fields/tables a vertical actually uses. All packs share
the core; packs only decide what the UI asks for.

| Capability | Electronics | Coffee | Mart | Shop | Enabled by |
|---|---|---|---|---|---|
| Barcode | ✓ | – | ✓ | ✓ | core |
| Brand | ✓ | – | ✓ | – | core |
| Unit of measure | – | – | ✓ | – | core |
| Variants | ✓ | ✓ | ✓ | ✓ | variants |
| Modifiers | – | ✓ | – | – | modifiers |
| Serials / IMEI / warranty | ✓ | – | – | – | serials |
| Batch / expiry | – | – | ✓ | – | batches |

So "shop" needs **nothing beyond core + variants**; it is primarily a
validation pass, not a build.

## 6. Inventory semantics

- Inventory key is `(store_id, product_id)` when a product has no variants, and
  `(store_id, variant_id)` when it does. `Product.on_hand` in API responses is
  the sum across variants for convenience.
- `StockMovement` gains an optional `variant_id` and `batch_id` so history can
  attribute movements precisely.
- Serial and batch tracking are layered on top of quantity balances; the
  balance stays the fast path, serials/batches are the detailed ledger.

## 7. Rollout order (one branch / PR each)

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/product-model` | this document |
| 1 | `feat/product-core-fields` | vertical flag, core columns, `attributes`, barcode/unit/brand, surface description/cost, attributes UI, details drawer, CSV round-trip |
| 2 | `feat/product-variants` | options/values/variants, variant inventory, POS variant picker, `OrderItem` variant snapshot |
| 3 | `feat/product-serials` | serials/IMEI, warranty, receive/sale scanning |
| 4 | `feat/product-modifiers` | modifier groups/modifiers, POS modifier popup, `OrderItem.modifiers` snapshot, optional recipe depletion |
| 5 | `feat/product-uom-batches` | unit-of-measure pricing, batches/expiry, FEFO |
| – | shop | folded into item 1 acceptance (no standalone branch) |

Items 4 and 5 are independent of 2–3 and may run in parallel after item 1.

Every API change regenerates `chmabapos_api/openapi.json` in the same PR (CI
fails on drift).

## 8. Out of scope

- Offline / local-store / desktop-sync product caching.
- Multi-warehouse replenishment planning.
- Product bundles/composites beyond recipe-based ingredient depletion.
- Moving images out of the database to object storage (tracked separately; the
  `image` column stays base64 for now).
- Per-product tax class (store-level `service_tax_rate` remains the only lever).

## 9. Open decisions

1. Variant inventory storage: separate `(store_id, variant_id)` rows vs a
   single balance table with a nullable `variant_id` (recommended: nullable
   `variant_id`, one table).
2. Whether attribute schemas are seeded per vertical/category or only
   client-side validated.
3. Whether serial-level cost overrides product cost for COGS.

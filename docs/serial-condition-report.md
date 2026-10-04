# Serial condition reports

Per-unit condition data for **serialized products** (the electronics pack): used,
refurbished and graded stock where every unit differs even when the spec is the
same.

Status: Implemented except the computed `landed_cost` field (§4.4/§5.1), which is not built.
Owners: Engineering
Scope: the data model, API and UI for capturing and reporting the condition of an
individual serialized unit. No code is changed by this document.

This document extends `docs/product-model.md` (section 4.6, serials / IMEI). It is
additive and follows the same principles; it does not replace the product/variant
model.

## 1. Goal

Today a serialized unit records *identity* (serial number, IMEI), *location*
(store, status), *money* (cost) and *time* (warranty). It records nothing about
the physical **condition** of the unit.

For new goods that is fine. For used and refurbished electronics it is the whole
business. A store selling "MacBook Pro 14\" 2021, 16 GB / 512 GB, Space Gray"
receives units that are identical on paper but differ in:

- cosmetic wear (scratches, dents, discolouration, worn coating),
- battery health and cycle count,
- screen defects (dead pixels, bright spots, scratches, replacements),
- repaired or aftermarket parts,
- accessories included,
- supplier and landed cost.

Because condition has no home in the model, stores are forced to either create a
variant per price tier and hide the real condition in a variant name/attribute,
or sell everything at one price and lose the grade spread entirely. Neither
supports a warranty claim, an accurate condition report, or a re-grade.

The goal is **one per-unit condition record** that:

1. is the source of truth for what a specific unit actually is,
2. keeps the sellable catalog shape (product → variant) unchanged,
3. supports re-grading over the life of a unit, and
4. is snapshotted onto the sale so history and receipts are immutable.

## 2. Industry model we align to

Across the refurbished electronics market the sellable condition model is
consistent (Back Market, Assurant CPO, refurbed, Cykero, Everphone and others):

- **Cosmetic grade drives price and appearance.** It is published as a small,
  ordered ladder with *measurable* thresholds, e.g. Back Market's
  `Premium / Excellent / Good / Fair`.
- **Functionality is a separate guarantee.** Every grade is 100% functional and
  warrantied; the grade is appearance and price only.
- **Battery health is a first-class, per-unit number** with a floor per grade
  (commonly ≥ 90% for the top tier, ≥ 80% for the rest).
- **Each unit is serialized** and carries its own cost, source lot, photos and
  test report.

The de-facto grade ladder, with the thresholds that make it usable:

| Grade | Also called | Appearance | Battery floor |
|---|---|---|---|
| `premium` | Pristine, A+ | Flawless; genuine parts | ≥ 90% |
| `excellent` | Grade A, As-new | Almost no wear; micro-scratches invisible at 20 cm | ≥ 80% |
| `good` | Grade B, Very Good | Light wear; no screen scratches | ≥ 80% |
| `fair` | Grade C, Acceptable | Visible scratches/dents; screen fine when on | ≥ 80% |

### 2.1 Five dimensions that must not collapse

The common modelling mistake is to treat everything that differs as one axis.
The industry keeps them apart:

| Dimension | Example | Lives on |
|---|---|---|
| Spec | 14\", 16 GB, 512 GB, Space Gray | `Product` (shared) |
| Cosmetic grade | excellent / good / fair | Sellable grade → price tier |
| Functional condition | battery 91%, screen replaced, tests pass | **Unit** (a guarantee) |
| Unit identity | serial / IMEI, photos, landed cost | **Unit** (`ProductSerial`) |
| Source / lot | supplier, purchase order | **Unit's** receiving lot |

Supplier is not a grade and not a variant: two identical `excellent` units from
different suppliers sell for the same price and only differ in cost. It belongs
on the unit's intake.

## 3. Design principles

1. **Additive and nullable.** Every new field is nullable or defaulted so
   existing workspaces, serials and orders keep working.
2. **Queryable fields are columns; the long tail is JSON.** Following
   `product-model.md`, a field is promoted to a real column only when it must be
   indexed or filtered (grade, battery health). The detailed scorecard is JSON.
3. **The unit is the source of truth; the variant stays the listing.** Grade is
   an assessment *of a unit*; the grade variant is a grouping of units currently
   assessed at that grade. We do not make condition a second, competing catalog.
4. **Re-assessable.** A unit can be re-graded (e.g. battery replaced) without
   losing its history.
5. **Snapshot on sale.** The grade and the condition report are copied onto the
   order line at sale time, like every other mutable field.
6. **Electronics pack.** The fields are only surfaced when the store's vertical
   pack includes serials; the schema itself does not fork.

## 4. Data model

### 4.1 `ProductSerial` additions

Current definition (origin/main) for reference:

```
ProductSerial(id, company_id, product_id, variant_id, store_id,
              serial_number, imei, status, cost_price,
              warranty_months, warranty_until,
              order_item_id, created_at, updated_at)
```

Proposed additions, all nullable:

| Field | Type | Index | Notes |
|---|---|---|---|
| `condition_grade` | `String(20)` | yes | one of the grade ladder; `NULL` = unassessed |
| `battery_health` | `Integer` | yes | percent, `0..100`; `NULL` = unknown |
| `battery_cycle_count` | `Integer` | no | optional |
| `condition_report` | `JSON` | no | the detailed scorecard (below) |
| `supplier_id` | `UUID` FK `suppliers.id` | yes | source lot, `ON DELETE SET NULL` |
| `purchase_order_id` | `UUID` FK `purchase_orders.id` | no | receiving lot, `ON DELETE SET NULL` |
| `graded_at` | `DateTime(tz)` | no | when the current grade was assigned |
| `graded_by` | `UUID` FK `users.id` | no | who assigned it, `ON DELETE SET NULL` |

`condition_report` (JSON) carries the long tail that does not need indexing:

```json
{
  "screen":  { "grade": "good", "notes": "Light hairline scratch, invisible on" },
  "body":    { "grade": "excellent", "notes": "Micro-scuff on lid corner" },
  "functional": { "status": "pass", "tests": ["keyboard", "ports", "camera"],
                  "failures": [] },
  "parts_replaced": ["battery"],
  "accessories": ["charger", "box"],
  "notes": "Battery replaced 2026-08; cycles reset."
}
```

Rationale: `condition_grade` and `battery_health` are filtered and reported on
("show me every `good` MacBook with battery ≥ 85%"), so they are columns. Screen,
body, functional detail and notes are read as a block and shown on a card, so
they stay in JSON. This mirrors how `Product.attributes` and
`ProductVariant.attributes` already work.

### 4.2 `SerialConditionHistory` (append-only)

Re-grading is a real workflow, so each assessment is recorded rather than
overwritten:

```
SerialConditionHistory(id, company_id, serial_id FK, condition_grade,
                       battery_health, battery_cycle_count, condition_report,
                       graded_by FK users, graded_at, created_at)
```

- Index on `(serial_id, graded_at)`.
- The serial's columns are the *current* assessment (denormalised for read
  speed); the history table is the audit trail.
- The newest history row must match the serial's columns; both are written in the
  same transaction. A service ticket that changes condition (battery swap) is the
  natural trigger to append a row.
- Alternative considered: reuse `SerialServiceTicket` for grading events. Kept
  separate because service tickets are a different concept (repair/warranty work)
  and grading happens without a ticket. See open decision 2.

### 4.3 Supplier and lot

- `supplier_id` links the unit to the existing `Supplier` record, replacing the
  current free-text `supplier` string that is written onto `StockMovement`.
- `purchase_order_id` links the unit to a `PurchaseOrder` so a whole received lot
  can be traced, and so supplier performance (return/defect rate by supplier) can
  be reported.
- The free-text `supplier` on `InventoryRestockRequest` and `StockMovement`
  stays for backward compatibility; when `supplier_id` is present it wins.

### 4.4 Landed cost

Refurbished margin is not `price - cost_price`; it is `price - landed_cost` where
landed cost includes parts and labour. There is already a per-unit repair cost
(`SerialServiceTicket.cost`).

- Define **landed cost** = `ProductSerial.cost_price` + `SUM(SerialServiceTicket.cost)`
  for the unit (repairs/refurb), computable from existing data.
- Expose it as a computed field `landed_cost` on serial reads.
- Do **not** add a stored column for now; if it becomes a hot path, denormalise
  later. See open decision 4.

### 4.5 Sale snapshot

`OrderItem` already snapshots `attributes` and `variant_name`. Add:

| Field | Type | Notes |
|---|---|---|
| `condition_grade` | `String(20)` | nullable; the unit's grade at sale |

and include the full condition report inside the existing `OrderItem.attributes`
snapshot. This keeps receipts, reprints and margin-by-grade reporting stable even
if the unit is later re-graded or the serial edited.

Serials remain linked via `order_item_id` (unchanged); the grade column is a
denormalisation purely for reporting.

### 4.6 Grade taxonomy

- Fixed set, ordered low-to-high visibility: `premium`, `excellent`, `good`,
  `fair`, plus the sentinel `parts`/`defective` if we want to sell
  refurbishment-grade units. All are plain strings validated at the schema level;
  no enum type is added to the database (consistent with `ProductSerial.status`).
- `NULL` means **unassessed** and must be allowed, because existing serials and
  non-electronics verticals will never have it.
- Whether the set is company-configurable is deferred (open decision 3); the
  default follows the market ladder so out-of-the-box behaviour is familiar.

## 5. API

Schemas in `chmabapos_api/app/schemas.py`.

### 5.1 Serial schemas

- `ProductSerialInput` += `condition_grade`, `battery_health`,
  `battery_cycle_count`, `condition_report`, `supplier_id`.
- `ProductSerialRead` += the same, plus `graded_at`, `supplier_name`,
  `landed_cost` (computed, not stored).
- `ProductSerialUpdateRequest` += `condition_grade`, `battery_health`,
  `battery_cycle_count`, `condition_report`, `supplier_id`, and **`variant_id`**.
  - `variant_id` on update is the **re-grade / re-file** path: it moves a unit to
    the grade variant it now matches. Today a serial's variant cannot be changed
    except implicitly at sale; re-grading needs this.
- `SerialLookupRead` += `condition_grade`, `battery_health`,
  `battery_cycle_count`, `supplier_name`.

### 5.2 Receive-stock payload

`POST /inventory/{product_id}/restock` (`InventoryRestockRequest`) currently
takes a flat `serial_numbers: list[str]` with a single `unit_cost` for the whole
batch. Per-unit condition needs a richer shape.

Add an optional `serials` list that, when present, takes precedence over
`serial_numbers`:

```json
{
  "quantity": 2,
  "variant_id": "...",
  "serials": [
    { "serial_number": "C02X...A1", "condition_grade": "excellent",
      "battery_health": 94, "supplier_id": "...", "unit_cost": 690,
      "supplier_warranty_months": 6 },
    { "serial_number": "C02X...A2", "condition_grade": "good",
      "battery_health": 88, "supplier_id": "...", "unit_cost": 605 }
  ]
}
```

- Still enforce **one serial per unit** (`len(serials) == quantity`).
- Per-unit `unit_cost` overrides the batch `unit_cost`, closing the "one cost per
  receive batch" limitation noted in the current model. A per-unit cost is
  written to `StockMovement.unit_cost` for the corresponding unit where a
  movement is recorded.
- Backward compatibility: callers that send `serial_numbers` keep the current
  behaviour and get a single grade/cost for the batch.

### 5.3 Validation rules

- `condition_grade` must be in the allowed set; `battery_health` must be
  `0..100`.
- Grade vs variant consistency: if the target variant declares a grade (in its
  `attributes`), a unit whose `condition_grade` differs is accepted but the
  response carries a **warning** (soft), never a hard block. Hard-blocking would
  fight the "re-grade before re-file" workflow.
- Unassessed serials stay sellable (no hard requirement to grade), unless a store
  opts in to stricter rules (open decision 5).

### 5.4 Endpoints

No new resource is required: condition is part of create/update/read on existing
serials. Optional convenience endpoint:

- `POST /serials/{id}/conditions` — append a history row and update the current
  columns. Useful for the "Regrade" action so the UI does not have to send a full
  update.

## 6. UI (`apps/web`)

- **Receive stock** (`LiveInventoryView`, `saveRestock` in
  `features/catalog.jsx`): when receiving a serial-tracked product, capture a
  default grade + battery for the batch and allow per-serial overrides. Add a
  supplier picker fed by `GET /suppliers` (replacing the free-text field for
  choice, keeping it as fallback).
- **Serials modal** (`SerialsModal`): show grade and battery as a badge next to
  each serial; add a **condition** editor (grade, battery, cycle count, screen /
  body / functional, notes, accessories). Add a **Regrade** action that writes a
  history row and optionally re-files the unit to the matching grade variant.
- **Serial lookup** (`SerialLookupModal`): render the condition report card
  alongside the sale, warranty and service history.
- **Product form**: keep the existing note that condition is per unit; do not add
  condition fields at product/variant level beyond the grade variant itself.

## 7. Migration and backfill

- New Alembic revision. **Chain `down_revision` to the then-current single head**
  (`alembic heads` must show exactly one revision). At the time of writing the
  head on `main` is `d2a5b8c1e4f7`; note that an in-flight migration
  `f3b7c1d9e2a4` (split supplier/customer warranty) also chains to that head and
  should land first, in which case this revision chains to `f3b7c1d9e2a4`.
- All new columns nullable; create `serial_condition_history`.
- Best-effort backfill: for serials whose variant name or attributes encode a
  grade (e.g. a variant named "Grade A · Excellent"), set `condition_grade` from
  it; otherwise leave `NULL` (unassessed). Backfill runs in the migration but
  must never fail the upgrade on unparseable data.
- Regenerate `chmabapos_api/openapi.json` in the same PR (CI fails on drift).

## 8. Reporting

Once grade and battery exist per unit, these become possible:

- **Margin by grade** — `report_margin` grouped by `OrderItem.condition_grade`,
  using the frozen per-unit cost and landed cost.
- **Inventory aging by grade** — days-on-hand per grade variant to drive
  re-pricing, which is how refurbishers defend margin.
- **Battery distribution** — histogram of `battery_health` to spot units that
  need a battery before they sell.
- **Supplier performance** — defect/return rate by `supplier_id` using
  `SerialServiceTicket` and `status = returned | defective`.

## 9. Vertical gating

- Fields are only rendered for the electronics pack (`Company.vertical ==
  "electronics"`, or a store override), consistent with `product-model.md`.
- The API does not reject the fields for other verticals; gating is a UI concern,
  as documented there.

## 10. Out of scope

- Per-unit photos. The media library (`MediaAsset`, `/media/assets`) is the right
  home; wiring multiple serial images is a follow-up, not part of this change.
- Automated/AI cosmetic grading.
- Stolen/blacklist database integration and automated data-wipe attestation.
- Marketplace listing sync (Back Market, eBay, Swappa).
- Company-configurable grade taxonomies.

## 11. Rollout order (one branch / PR each)

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/serial-condition-report` | this document |
| 1 | `feat/serial-condition-model` | `ProductSerial` columns, `SerialConditionHistory`, schemas, migration, `variant_id` re-file |
| 2 | `feat/serial-condition-receive` | per-unit capture in receive stock, per-unit cost, supplier picker |
| 3 | `feat/serial-condition-ui` | serials modal editor, regrade action, lookup card |
| 4 | `feat/serial-condition-sale` | `OrderItem.condition_grade` + report snapshot, receipt/invoice line |
| 5 | `feat/serial-condition-reports` | margin by grade, aging by grade, battery distribution, supplier performance |

Items 2–3 and 4–5 are independent and may run in parallel after item 1.

## 12. Open decisions

1. `condition_grade` + `battery_health` as columns vs a single JSON condition
   blob. Recommendation: columns for the two queryable fields, JSON for the rest.
2. Separate `SerialConditionHistory` table vs reusing `SerialServiceTicket`.
   Recommendation: separate table; grading is not repair.
3. Fixed grade ladder vs company-configurable grades. Recommendation: ship the
   fixed market ladder first; make it configurable only if asked.
4. Landed cost computed on read vs denormalised column. Recommendation: compute
   on read; denormalise only if reporting gets slow.
5. Whether an ungraded unit may be sold. Recommendation: yes by default, with a
   store-level warning; do not hard-block.
6. Do we keep the free-text `supplier` string once `supplier_id` exists?
   Recommendation: keep for backward compatibility, prefer the FK when present.

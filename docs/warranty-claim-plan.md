# Warranty-claim lifecycle

Status: Draft for review
Owners: Engineering
Scope: design only — no code changes in this document's PR.

Related: `docs/capabilities-and-gaps.md` (G8), `docs/serial-condition-report.md`,
`chmabapos_api/app/models.py` (`ProductSerial`, `SerialServiceTicket`,
`SerialConditionHistory`), `docs/trade-in-plan.md` (stock intake precedent).

## 1. Goal

When a customer returns a device under warranty, the shop should be able to file
a **claim**, decide it, and resolve it (repair, replace, or refund) with a clean
audit trail — linked to the serial, the original sale and the customer.

## 2. Current state

- `ProductSerial` carries **dual warranty** clocks: `supplier_warranty_until`
  (starts at receipt) and `customer_warranty_until` (starts at `sold_at`), plus
  `order_item_id` linking the unit to the sale line.
- `SerialServiceTicket` logs **repairs** (`ticket_type="repair"`, `status`,
  `summary`, `cost`, `resolved_at`).
- `SerialConditionHistory` is the append-only condition/grading audit trail.
- Refunds reverse a sale line and (for serials) return the unit to stock.
- There is **no** formal claim: no eligibility check, no approval, no
  repair-vs-replace decision, no supplier recovery link.

## 3. Design principles

1. **The serial is the spine.** A claim always hangs off one sold
   `ProductSerial`; the original `Order`/`OrderItem` and `customer_id` are read
   from it, never re-entered.
2. **A claim is a workflow, not just a note.** Explicit states + a status
   history, so a warranty desk can see where each claim is.
3. **Repair is the default; replacement and refund are decided outcomes.**
   Replacement intakes a new serial (like a trade-in) and re-links warranty.
4. **Reuse the existing primitives**: `SerialServiceTicket` for repair work,
   the refund flow for refunds, the approval policy for high-cost decisions,
   and `StockMovement` for replacement intake.
5. **Additive migrations**, backward compatible.

## 4. Data model

### 4.1 `WarrantyClaim`

New company/store-scoped table:

- `id`, `company_id`, `store_id`
- `claim_number` (per store, via the existing document-number helper)
- `serial_id` (FK `product_serials`) — the unit under claim
- `customer_id` (nullable FK) — snapshotted from the serial's sale
- `order_id` / `order_item_id` (nullable FKs) — the original sale
- `status` — `open | approved | denied | in_repair | replaced | refunded | closed`
- `resolution` — `repair | replace | refund | deny` (set at decision time)
- `issue` (short summary), `description` (Text)
- `claimed_at`, `decided_at`, `resolved_at` (nullable)
- `cost` (`Numeric(12,2)`, nullable) — repair/replacement cost borne by the shop
- `replacement_serial_id` (nullable FK `product_serials`)
- `refund_id` (nullable FK `refunds`)
- `service_ticket_id` (nullable FK `serial_service_tickets`)
- `decided_by`, `created_by` (FK `users`), timestamps

### 4.2 Status history

`WarrantyClaimEvent(id, claim_id, from_status, to_status, note, actor_id, created_at)`
— append-only, mirrors the condition-history pattern.

## 5. Workflow

1. **File** — at the serial (Serial drawer → "File warranty claim"): checks the
   unit is `sold` and within `customer_warranty_until` (a warning, not a hard
   block, when expired). Creates the claim `open`.
2. **Decide** — approve or deny. Approval may require a manager per the
   existing approval policy when `cost`/value crosses a threshold.
3. **Resolve** — one of:
   - **Repair**: create/attach a `SerialServiceTicket`; unit leaves and returns;
     set `in_repair` → `closed`.
   - **Replace**: intake a new serial for the same product/variant (stock
     movement, like a trade-in); set the replacement's `customer_warranty_until`
     to the remainder of the claim's warranty or a fresh term (decision §10);
     set `replaced`.
   - **Refund**: run the existing refund flow for the order line; set `refunded`.
   - **Deny**: close with a reason.
4. **Close** — the terminal state; events capture the full transition trail.

## 6. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/warranty-claims` | file a claim for a sold serial |
| `GET` | `/warranty-claims` | list, filter by status/serial/customer |
| `GET` | `/warranty-claims/{id}` | one claim + events |
| `POST` | `/warranty-claims/{id}/decide` | approve / deny (with resolution intent) |
| `POST` | `/warranty-claims/{id}/resolve` | repair / replace / refund |

`GET /serials/{id}` (or the serial drawer's payload) includes the claims for the
unit. Regenerate `openapi.json`.

## 7. Web UI (`apps/web`)

- **Serial drawer** (`catalog.jsx` serials modal): a **Warranty** tab showing the
  warranty clock and the unit's claims, with **File claim**.
- **Warranty claims** view (new nav item, behind the `serials` capability): list
  by status with age; open one to decide/resolve.
- A claimed/replacement unit shows on the product's serial list like any graded
  unit.

## 8. Migration

One additive revision creating `warranty_claims` and `warranty_claim_events`,
chained to the current single head. No changes to `product_serials`.

## 9. Rollout

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/warranty-claim-plan` | this document |
| 1 | `feat/warranty-claim-core` | models, file/decide/resolve, eligibility, events, tests |
| 2 | `feat/warranty-claim-ui` | serial-drawer Warranty tab + claims list/detail |
| 3 | `feat/warranty-claim-reports` | claim cost/rate reporting, supplier recovery view |

## 10. Open decisions

1. **New `WarrantyClaim` table vs extend `SerialServiceTicket`.** Recommendation:
   a **new claim table** that can *link* a service ticket — the ticket is a
   repair artifact, not the claim lifecycle; keeping them separate keeps the
   existing repair log intact.
2. **Replacement warranty term.** Recommendation: carry over the **remaining**
   customer warranty (no warranty extension abuse), with a configurable reset.
3. **Supplier recovery.** Out of scope for v1 beyond storing cost; a supplier RMA
   link is a later phase.

## 11. Out of scope

- Supplier RMA automation and cost recovery.
- Recall/product-safety campaigns.
- Third-party repair-centre integrations.
- Automatic eligibility from external serial/IMEI registries.

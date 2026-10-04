# Seat & course routing

Status: Implemented — per-line seat/course + fire-by-course (#392), Kitchen grouping/fire + drawer controls (#393) and POS seat chips (#394).
Owners: Engineering
Scope: design only — no code changes in this document's PR.

Related: `docs/restaurant-mode.md` (§4.4, §10.1), `docs/capabilities-and-gaps.md`
(G2), `chmabapos_api/app/models.py`, `apps/web/src/features/ticketDrawer.jsx`.

## 1. Goal

A dine-in ticket should support **seats** (who ordered a line) and **courses**
(when it should fire). Staff can set a line's seat, group the ticket by course in
the kitchen, and fire a course to the pass without firing the whole ticket.

Everything stays inside the existing `HeldOrder`-based tickets; no new order system.

## 2. Current state

- An open ticket is a `HeldOrder`; its lines live in a JSON list `HeldOrder.items`.
  Each line already carries `product_id`, `variant_id`, `quantity`, `modifiers`,
  and a `line_key` from `held_line_key(product_id, variant_id, modifiers)`.
- `held_line_key` is the identity used by uniqueness, merge, split and transfer, so
  the same product with different options is a distinct line.
- On settle, a real `OrderItem` is written and prices/names snapshot.
- The Kitchen board and the shared ticket drawer render those lines.

There is **no** seat or course on a line, and no way to fire part of a ticket.

## 3. Design principles

1. **Lines, not a new table.** Seat and course are attributes of a ticket line; the
   `HeldOrder` JSON stays the store. A dedicated `TableTicket` table is only worth it
   if per-line kitchen state grows beyond a couple of fields (see §10).
2. **Seat is part of a line's identity; course is not.** Two identical drinks for
   two seats must be two lines; a line's course can change (starter → main) without
   forking it.
3. **Additive and backward compatible.** Existing seatless/courseless tickets keep
   working and keep their identity.
4. **Fire is a kitchen signal, not a stock event.** Firing changes only ticket state;
   stock, tax and payments still happen at settle.
5. **Snapshot on sale.** `seat`/`course` freeze onto the settled `OrderItem` for
   reporting, like the other line fields.

## 4. Data model

### 4.1 Ticket line (JSON, additive)

Add two optional fields to each `HeldOrder.items` entry:

| field | type | notes |
|---|---|---|
| `seat` | int? | 1-based seat number; `null` = shared/unassigned |
| `course` | str? | one of the configured courses; `null` = unassigned |
| `fired_at` | ISO str? | set when the line is fired to the kitchen |

No schema migration is needed for the JSON; the columns already exist.

### 4.2 Identity

`held_line_key(product_id, variant_id, modifiers, seat=None)` appends the seat only
when set:

```
<product>:<variant>:<sorted modifiers>          # seatless (unchanged)
<product>:<variant>:<sorted modifiers>:s<seat>  # seated
```

This keeps existing keys stable while letting per-seat lines coexist. `course` is
**not** in the key, so a line can be re-coursed in place.

### 4.3 Settled order (`OrderItem`)

Add two nullable columns so reporting/receipts can show seat/course:

- `OrderItem.seat` — `Integer?`
- `OrderItem.course` — `String(40)?`

One additive Alembic revision; no data backfill.

## 5. Firing

- A line's `fired_at` marks it sent to the kitchen.
- `POST /held-orders/{id}/fire` with an optional `course` fires every unfired line in
  that course (or all unfired lines when omitted), stamping `fired_at`.
- Firing does not block settle; a ticket can be settled with unfired lines (staff
  choice), but the Kitchen board flags them.

## 6. API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/held-orders/{id}/items/{line}/seat` *(or reuse ticket update)* | set seat/course on a line |
| `POST` | `/held-orders/{id}/fire` | fire a course (or all) |
| `GET` | `/held-orders` | lines now include `seat`, `course`, `fired_at` |

`HeldItemRequest`/`HeldItemRead` gain `seat`, `course`, `fired_at`. The settle path
snapshots `seat`/`course` onto `OrderItem`. Regenerate `openapi.json`.

## 7. Web UI

- **Ticket drawer** (shared Floor/Kitchen): per-line seat and course selects, and a
  **Fire** action per course with an "unfired" indicator.
- **Kitchen board**: group a ticket's lines by course; show unfired courses first;
  a **Fire course** button.
- **POS**: optional seat chips (1..N) when the ticket is dine-in; the active seat is
  attached to lines added from then on. Seat defaults to unassigned so cashiers can
  ignore it.
- All behind the existing `tables` capability + `table_management` plan gate.

## 8. Migration

One additive revision adding `order_items.seat` and `order_items.course`, chained to
the current single Alembic head. No changes to `held_orders` (JSON).

## 9. Rollout

| # | Branch | Scope |
|---|---|---|
| 0 | `docs/seat-course-plan` | this document |
| 1 | `feat/seat-course-core` | line seat/course + identity, fire endpoint, `OrderItem` snapshot, migration, tests |
| 2 | `feat/seat-course-kitchen` | Kitchen grouping/fire + ticket-drawer controls |
| 3 | `feat/seat-course-pos` | POS seat chips |

## 10. Open decisions

1. **`HeldOrder` JSON vs a `TableTicket` table.** Recommendation: stay on the JSON
   for seats/courses/fired (two small fields); revisit a dedicated table only if
   per-line kitchen state grows (voids, fire rounds, timers). `restaurant-mode.md`
   §10.1 anticipated this.
2. **Seat in the identity key.** Recommendation: yes (so per-seat duplicates are
   distinct); course stays out of the key.
3. **Course set.** Recommendation: a small fixed set (`starters`, `mains`, `dessert`,
   `drinks`) plus the ability to leave a line uncoursed; a free-text custom course is
   a later option.

## 11. Out of scope

- Per-seat **billing** / splitting a bill by seat (split by line already ships).
- Course timers, hold-and-fire scheduling.
- Reservations, online/QR ordering, delivery dispatch.
- Per-line voids with manager approval (separate feature).

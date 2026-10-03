# Restaurant mode — deploy notes

Short ops runbook for the restaurant / table-management changes. Nothing here
destroys data.

## Migrations are additive

Every migration added for this work either creates a new table or adds a
nullable / defaulted column — no drops, no rewrites:

| Migration | Change |
|---|---|
| `add_order_type` | `orders.order_type`, `held_orders.order_type` (default `takeaway`) |
| `add_dining_tables` | creates `dining_areas`, `dining_tables` |
| `add_held_order_table` | `held_orders.table_id`, `held_orders.status` |
| `add_order_table` | `orders.table_id` |

## Deploy steps

1. **Back up the database.**
2. **Apply migrations** (additive, safe):
   ```
   alembic -c chmabapos_api/alembic.ini upgrade head
   ```
3. **Re-seed plans** so the plan capability maps match the code:
   ```
   python chmabapos_api/scripts/seed.py
   ```
   Idempotent; also refreshes currencies and plan limits. (The `starter` row is
   additionally patched by migration `c7a1b2c3d4e5` so existing databases pick
   up the `table_management` change even without a re-seed.)

## Table management is on Starter and Pro

`table_management` (table & restaurant mode) ships on **Starter and Pro**; only
**Free** gets a `403` from the dining endpoints. To toggle it for a plan without
a code change, use the override script (`--off` reverts):

```
python chmabapos_api/scripts/set_plan_capability.py --plan starter --capability table_management
python chmabapos_api/scripts/set_plan_capability.py --plan starter --capability table_management --off
```

## Verify

- `alembic current` equals `alembic heads`.
- A Starter or Pro workspace returns `200` from `GET /api/v1/dining/areas`; a
  Free workspace returns `403`.

## Local dev note

One shared local database across many branches causes Alembic drift (a stamp
behind the schema, or ahead). Give each worktree/branch its own database, or
recreate the dev DB before migration work. CI never hits this because it always
starts from an empty database.

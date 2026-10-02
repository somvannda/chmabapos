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
   This is what applies the Pro-only `table_management` change (Starter loses
   it, Pro keeps it). It is idempotent and also refreshes currencies and plan
   limits.

## Table management is Pro-only

`table_management` ships on **Pro** only; Free and Starter get a `403` from the
dining endpoints. If a deployment should keep it on Starter, turn it back on for
that plan (and `--off` to revert):

```
python chmabapos_api/scripts/set_plan_capability.py --plan starter --capability table_management
python chmabapos_api/scripts/set_plan_capability.py --plan starter --capability table_management --off
```

## Verify

- `alembic current` equals `alembic heads`.
- A Pro workspace returns `200` from `GET /api/v1/dining/areas`; Free/Starter
  return `403`.

## Local dev note

One shared local database across many branches causes Alembic drift (a stamp
behind the schema, or ahead). Give each worktree/branch its own database, or
recreate the dev DB before migration work. CI never hits this because it always
starts from an empty database.

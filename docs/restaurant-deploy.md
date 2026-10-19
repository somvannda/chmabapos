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
behind the schema, or ahead). CI never hits this because it always starts from an
empty database.

**Give each worktree its own database.** `scripts/create_database.py` already
honours `CHMABA_DATABASE`, so a branch name is enough:

```powershell
$name = "chmaba_" + ((git branch --show-current) -replace '[^a-zA-Z0-9]', '_')
$env:CHMABA_DATABASE = $name
python chmabapos_api/scripts/create_database.py
$env:DATABASE_URL      = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/$name"
$env:SYNC_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/$name"
python -m alembic -c chmabapos_api/alembic.ini upgrade head
```

Two symptoms mean you are on a drifted database, not looking at a code bug:
`alembic upgrade head` fails with *"Can't locate revision identified by …"*, or a
migration fails with *"column … already exists"* because the schema is ahead of
the stamp. Recover in that order:

```powershell
python chmabapos_api/scripts/check_schema_drift.py   # is the schema actually complete?
python -m alembic -c chmabapos_api/alembic.ini heads # what is the one true head?
python -m alembic -c chmabapos_api/alembic.ini stamp --purge <that head>
```

`stamp` alone is not enough when the recorded revision is unknown: it reads the
old revision first, so `--purge` is what clears the stale row.

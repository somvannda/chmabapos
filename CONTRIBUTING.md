# Contributing

`main` is protected: every change goes through a pull request that must pass CI
(`API`, `Web`, `Admin` jobs). No direct pushes to `main`, and no human approval
step — merging is allowed as soon as CI is green.

## Workflow

1. Branch from `main`: `git switch -c fix/description` (or `feat/`, `refactor/`).
2. Make changes and commit with a clear message:

   ```
   type(scope): short summary
   ```

   Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`. Scope examples:
   `api`, `web`, `admin`, `deploy`, `ci`.

3. Run the relevant checks locally before pushing:

   - API: `pytest -q` (in `chmabapos_api`) and keep `openapi.json` up to date
     via `python chmabapos_api/scripts/export_openapi.py`.
   - Web/Admin: `npm run build` in `apps/web` and `apps/admin`.
4. Open a PR to `main`. CI runs tests/builds automatically; merge as soon as it
   is green.

## Structure conventions

- Backend code lives under `chmabapos_api/app` (routers in `app/api`, logic in
  `app/services`, schema changes as alembic migrations).
- Front-end views live under `apps/*/src/features/<domain>.jsx`; shared UI
  primitives under `apps/web/src/components/ui.jsx`. Keep `App.jsx` as a thin
  router only.
- No secrets, logs, build output, or `.env` files in the repo (see `.gitignore`
  and `.dockerignore`).

## Running the API spec regeneration

```bash
python chmabapos_api/scripts/export_openapi.py
```

Commit the resulting `openapi.json` change with your PR, otherwise CI fails.

## Local databases

Use **one database per worktree/branch**. Sharing a single local database across
branches causes Alembic drift: the recorded migration version and the actual
schema stop agreeing, so `alembic upgrade head` starts failing with
`relation "..." already exists` or `Can't locate revision identified by "..."`.
CI never hits this because it always starts from an empty database.

Pick a database name per branch and point the API at it (the API reads
`DATABASE_URL` and `SYNC_DATABASE_URL`; set them in your shell or a local,
git-ignored `.env`). `create_database.py` reads `CHMABA_DATABASE`:

```bash
export CHMABA_DATABASE=chmaba_mybranch
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/$CHMABA_DATABASE"
export SYNC_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/$CHMABA_DATABASE"
python chmabapos_api/scripts/create_database.py
alembic -c chmabapos_api/alembic.ini upgrade head
python chmabapos_api/scripts/seed.py
```

If a database has already drifted, recreate it the same way CI does — drop it
(terminate its connections first) and run the steps above. `current` and `heads`
must match when you are done: `alembic -c chmabapos_api/alembic.ini current`.

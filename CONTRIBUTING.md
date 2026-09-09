# Contributing

`main` is protected: every change goes through a pull request, needs one
approving review, and must pass CI (`API`, `Web`, `Admin` jobs). No direct
pushes to `main`.

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
4. Open a PR to `main`. CI runs tests/builds automatically.

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

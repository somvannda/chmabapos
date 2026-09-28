# Working Agreement

## Git workflow (mandatory)

The default branch is `main`. Never commit to `main` directly — all work lands on
`main` through a pull request. There is no required human approval step: green CI
is the gate. This keeps history clean and versioning predictable.

### Start of every unit of work

Before starting **any** feature, fix, chore, new topic, or new session:

1. `git fetch origin`
2. Create a new branch off the latest `origin/main`:
   - `git switch -c <type>/<short-description> origin/main`
   - `<type>` is one of: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `release`
   - Example: `feat/billing-invoices`, `fix/khqr-scan-bug`, `docs/api-readme`
3. Do the work on that branch only. If a session spans several unrelated topics,
   use a separate branch for each.

### While working

- Keep commits small, focused, and logically grouped per file/concern.
- Use Conventional Commits: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`.
  Add a short body when the change needs context.
- Never commit generated/binary noise or secrets. Regenerate committed artifacts
  (e.g. `chmabapos_api/openapi.json`) and commit them together with the change.
- Rebase or merge `origin/main` into your branch frequently to stay current and
  to surface conflicts early.
- When adding a new Alembic migration, always chain `down_revision` to the current
  single head (`alembic heads` must show exactly one revision).

### Finishing

1. Push the branch: `git push -u origin <branch>`
2. Open a PR against `main` (`gh pr create`).
3. Wait for CI: API (chmabapos_api), Web (apps/web), Admin (apps/admin) — all must pass.
4. Merge the PR as soon as checks are green (no approving review is required).
5. Delete the branch after merge (`gh pr merge --delete-branch` or equivalent).
6. Sync local `main`: `git switch main && git pull --ff-only`.

This rule applies to every assistant and human working in this repository,
including changes that introduce or update these rules.

## Repository layout

- `apps/web` — the customer-facing POS (`chmaba-cloud-pos`). This is the store
  cashier surface: products, cart, checkout, serials, refunds, shifts, receipts.
  Selling behaviour belongs here.
- `apps/admin` — the platform admin control panel (`chmaba-admin`). It manages
  platform-level data only (overview, users, companies, stores, subscriptions,
  plans, audit, payments) and does **not** mount a store POS. The POS-shaped
  components in `apps/admin/src/App.jsx` (`POSView`, `LivePOSView`, `NAV_ITEMS`
  and the workspace shell) are currently unused.
- `chmabapos_api` — the FastAPI backend and the source of truth for stock,
  serials, orders and reservations.

When a task is about selling, checkout, serials or store inventory, target
`apps/web` and `chmabapos_api`. Confirm `apps/admin` actually renders a surface
before changing POS-style components there.

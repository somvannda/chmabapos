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
3. Wait for CI. `ci.yml` runs nine jobs and **all of them must pass**: `api`
   (`chmabapos_api`), `web` (`apps/web`), `storefront` (`apps/storefront`), `admin`
   (`apps/admin`), `e2e` (Playwright against `apps/web`), `api-client` (generated-type
   drift), `ops-config` (nginx + compose), `front-image` (Docker build) and `android`
   (`apps/android`). A green subset is not the gate — do not merge while any job is red.
   Check with `gh pr checks <pr>`.
4. Merge the PR as soon as checks are green (no approving review is required).
5. Delete the branch after merge (`gh pr merge --delete-branch` or equivalent).
6. Sync local `main`: `git switch main && git pull --ff-only`.

This rule applies to every assistant and human working in this repository,
including changes that introduce or update these rules.

## Repository layout

- `apps/web` — the customer-facing POS (`chmaba-cloud-pos`). This is the store
  cashier surface: products, cart, checkout, serials, refunds, shifts, receipts.
  Selling behaviour belongs here.
- `apps/android` — the native Android POS (`com.chmaba.pos`, Kotlin + Jetpack
  Compose). A second implementation of the same selling surface, plus stock,
  purchasing and reports. It follows `apps/web` visually — see
  `apps/android/DESIGN_GUIDE.md` — and is built and tested by the `android` CI job.
- `apps/storefront` — the public storefront for online ordering: a dedicated SSR
  app on the shop host (`shops.chmaba.com`), with the long `chmaba.com/order/<token>`
  link kept as a permanent redirect because printed table QR codes encode it.
- `apps/ios` — the native iOS POS (`com.chmaba.pos`, Swift/SwiftUI). A third
  implementation of the same selling surface. It is built by **xtool** from WSL with
  no Xcode and no Mac — see `apps/ios/README.md` for the toolchain and the USB relay —
  and is the one app here whose CI job does **not** compile it. The `iOS (apps/ios)`
  job verifies the Lucide icon parser and asserts every destination screen offers a
  way back; neither renders a screen, so anything visual still has to be checked on a
  device.
- `apps/admin` — the platform admin control panel (`chmaba-admin`). It manages
  platform-level data only (overview, users, companies, stores, subscriptions,
  plans, audit, payments) and does **not** mount a store POS; its shell uses
  `ADMIN_NAV_ITEMS` and has no POS or store-workspace views.
- `chmabapos_api` — the FastAPI backend and the source of truth for stock,
  serials, orders and reservations.
- `packages/` — `ui` (`@chmaba/ui`, shared React components) and `api-client`
  (`@chmaba/api-client`, types generated from the API's OpenAPI spec and checked
  for drift by the `api-client` CI job).

When a task is about selling, checkout, serials or store inventory, target
`chmabapos_api`, and expect to touch **all three** POS clients: `apps/web` (store
cashier), `apps/android` (mobile) and `apps/ios` (iOS). Confirm `apps/admin` actually
renders a surface before changing POS-style components there.

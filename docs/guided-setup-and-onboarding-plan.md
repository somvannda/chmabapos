# Guided Setup & Onboarding — Implementation Plan

Status: Implemented — all five phases (plus the coach spotlight anchors) are merged to `main`; see §10 for the PRs.
Owners: Engineering
Scope: Make business type an editable, first-class setting; collect a few goal
questions at signup and use them to recommend a plan; seed feature packs from
the business type plus those answers; and add a branched, real-time guided setup
that walks a new merchant to a completed sale. This document plans the work; it
makes no code changes.

Related: `docs/capabilities-and-gaps.md` (business types + packs),
`docs/product-model.md` (product/variant model), `docs/ai-support-plan.md`
(ADR-103 vertical content, AI help), `docs/billing-model.md`,
`chmabapos_api/app/verticals.py`, `chmabapos_api/app/features.py`,
`apps/web/src/features/onboarding.jsx`,
`apps/web/src/features/settings.jsx`,
`apps/web/src/lib/capabilityPacks.js`, `apps/web/src/lib/nudges.js`.

## 1. Goal

A new merchant should land in a workspace that already looks like *their* store,
be shown the right plan for their size, and be guided step by step to their first
completed sale — without turning features on by hand or reading a manual.

Concretely:

1. **Business type is editable** after signup (today it is set once at signup and
   hidden).
2. **Onboarding asks a few goal questions** (stores, team, sell model) and
   **recommends the plan** whose limits fit.
3. **Feature packs seed themselves** from business type + answers, and stay
   easy to adjust.
4. **A guided setup journey** adapts to the business type and answers, follows
   the merchant across screens, auto-advances as real actions complete, and ends
   at a finished sale.

## 2. Non-goals (this phase)

- No hard "modes". Business type stays **advisory** — the API keeps accepting
  every field for every vertical (`capabilities-and-gaps.md` §1).
- No change to plan **enforcement** (`require_plan_feature`); this only changes
  what we *recommend* and *pre-fill*.
- No new pricing model, no new plan tiers.
- No database migration is required for v1 (answers ride in existing JSON
  columns); a migration is called out where it would help.
- Not a rework of the AI assistant; the journey may feed it context later.

## 3. Current state (what already works)

| Piece | Where | Behaviour today |
|---|---|---|
| Business type captured | `WorkspaceSetupRequest.vertical` (`schemas.py:304`), stored on `Company.vertical` (`v1.py:1092`), chosen in `onboarding.jsx:144` | Set once at signup, defaults to `general` |
| Capability packs derived | `capabilities_for(vertical, preferences)` (`verticals.py:122`) | Vertical defaults, or an **absolute** per-store override |
| Packs exposed to UI | `WorkspaceRead.capabilities` (`schemas.py:338`) via `/workspaces/current` | `null` = unknown (show all), `[]` = known empty |
| Packs toggled | Settings → Feature packs `FeaturePacksCard` (`settings.jsx:103`) | Owner-only save via `PATCH /stores/{id}` `preferences.capabilities` |
| Packs consumed | `catalog.jsx`, `sales.jsx`, `dining.jsx`, `kitchen.jsx`, sidebar (`workspace.jsx`) | Fields/views surface per pack |
| Plan picker | `onboarding.jsx:45` | Always marks **Free** as "Recommended" |
| Plan limits | `PlanRead` (`schemas.py:164`) | Exposes `max_stores`, `max_members`, `transaction_limit`, `monthly_price` |
| Setup checklist | `GET /setup/checklist` (`v1.py:1195`) | Data-driven from real rows; first step title adapts by vertical |
| Checklist surfaces | Dashboard "Finish setting up" (`team.jsx`), KB nudges (`lib/nudges.js`, `help.jsx`) | Passive, single-screen |
| Business type in Settings | `SettingsEditor` (`settings.jsx:33`) | **Missing** — no way to change it in the UI |

Two independent layers exist and must stay distinct:

- **Plan entitlements** — `app/features.py::FEATURE_CATALOG` (15 keys), stored on
  `Plan.capabilities`; enforced server-side.
- **Business-type packs** — `app/verticals.py::CAPABILITY_LABELS` (8 keys);
  purely about which UI fields surface first.

## 4. Design principles

1. **Advisory, never blocking.** A missing capability or feature hides a step or
   a field; it never blocks the API.
2. **Reuse, don't rebuild.** Extend `verticals.py`, `/setup/checklist`, and the
   existing Settings plumbing.
3. **Backend is the source of truth.** Recommendations and defaults are computed
   server-side from real plan rows, not hardcoded copy.
4. **Every question is skippable.** Sensible defaults when answers are absent
   (fall back to `general` + Free, as today).
5. **One PR per item**, branched off `origin/main`, green CI as the gate
   (`AGENTS.md`).

## 5. Workstream A — Editable business type + delta overrides

### A.1 Business type selector in Settings

- Backend already accepts `vertical` on `CompanyUpdateRequest` (`schemas.py:348`)
  and `PATCH /company`. **No API change needed.**
- Frontend: add a "Business type" dropdown to the **Company profile** pane
  (`SettingsEditor`, `settings.jsx:33`, `company` branch), sourced from the same
  list as onboarding (`BUSINESS_TYPES` in `onboarding.jsx`; consider moving it to
  `lib/capabilityPacks.js` so both import one catalog).
- Wire it into `saveCompany()` → `onUpdateCompany({ vertical })`.

### A.2 Delta overrides instead of an absolute list

Today `Store.preferences.capabilities` **replaces** the vertical defaults, so the
store stops tracking `Company.vertical` the moment a pack is saved. Change to a
delta model:

```
Store.preferences.capability_overrides = { "added": [...], "removed": [...] }
```

`capabilities_for(vertical, preferences)` becomes:

```
base     = VERTICAL_CAPABILITIES.get(vertical, ())
added    = overrides.added   (validated against CAPABILITY_KEYS)
removed  = overrides.removed (validated against CAPABILITY_KEYS)
effective = (base | added) - removed
```

**Backward compatibility:** if `preferences.capabilities` (legacy absolute list)
is present, keep honouring it exactly as today; only compute deltas when the new
key is present. A one-time lazy migration on read is acceptable (no Alembic
migration needed for JSON).

### A.3 Feature packs UI

- `FeaturePacksCard` (`settings.jsx:103`):
  - Seed checkboxes from the **effective** set (as today) but save **deltas**.
  - Show the source per row ("On by default for Café" vs "Added by you").
  - Add **"Reset to my business type's defaults"** (clears
    `capability_overrides`).
  - Add an empty-state line for `general` so an all-unchecked list is explained
    ("Your business type uses the core POS; tick any packs you need.").

## 6. Workstream B — Onboarding goal questions + plan recommendation

### B.1 Questions

Insert one compact step ("A few quick questions") before **Choose your plan**.
Keep it to ≤ 4 taps; all optional.

| # | Question | Answers | Drives |
|---|---|---|---|
| 1 | How many stores will you run? | Just one / 2–5 / 6–50 / 50+ | `max_stores` → plan |
| 2 | Who sells with you? | Just me / 2–10 / 11–99 / 100+ | `max_members` → plan |
| 3 | Do you sell by weight or volume? | yes/no | `unit_of_measure` pack |
| 4 | Do you track IMEI / serials / warranty? | yes/no | `serials` pack |
| 5 | Do your items have expiry dates? | yes/no | `batches` pack |
| 6 | Do you serve dine-in tables? | yes/no | `tables` pack |

Questions 3–6 default from the chosen business type (pre-ticked) and the merchant
can uncheck. This is the "sell model" input; it is intentionally small.

### B.2 Plan recommendation

`PlanRead` already exposes the limits (`max_stores`, `max_members`,
`transaction_limit`, `monthly_price`), so the recommendation can be computed from
the existing public `GET /plans` response. For a single source of truth, compute
it server-side and expose the result.

Algorithm (`app/billing.py` or a new small helper):

```
band_upper = {"1": 1, "2-5": 5, "6-50": 50, "50+": 10**6}
need_stores  = band_upper[stores]
need_members = band_upper[team]
eligible = [p for p in plans if p.max_stores >= need_stores
                              and p.max_members >= need_members]
recommended = min(eligible, key=lambda p: (p.monthly_price, p.max_stores))
          or max(plans, key=lambda p: (p.max_stores, p.max_members))
```

- Onboarding flags this plan **"Recommended for you"** and sorts it first; Free
  keeps its "Recommended" badge only when it is genuinely the fit.
- The plan cards already render from real limits
  (`derive_plan_marketing_features`), so no marketing copy changes.
- Do **not** auto-charge; the merchant still confirms. Paid selection continues
  into the existing billing flow.

### B.3 Capability seeding from answers

At `POST /workspaces/setup`:

```
seeded_added = capability_answers - vertical_defaults
Store.preferences.capability_overrides = { "added": seeded_added, "removed": [] }
```

so the packs shown equal `vertical defaults ∪ answers`. Because it is stored as a
delta (Workstream A), later changing business type still updates the defaults.

### B.4 Onboarding request/schema

Extend `WorkspaceSetupRequest` (`schemas.py:299`):

```
store_count_band: Literal["1","2-5","6-50","50+"] = "1"
team_size_band:   Literal["1","2-10","11-99","100+"] = "1"
capability_answers: list[str] = []          # validated against CAPABILITY_KEYS
```

Persist the raw answers for analytics/branching in
`Store.preferences.onboarding_profile`. Regenerate `openapi.json`.

## 7. Workstream C — Guided setup journey

### C.1 Step model

Turn the checklist into an ordered, adaptive journey. Each step:

```json
{
  "id": "first-sale",
  "title": "Ring up your first sale",
  "description": "Try the register with a sample item.",
  "view": "pos",
  "anchor": "pos-new-sale",
  "article_id": "getting-started.first-sale",
  "requires": { "capability": null, "plan_feature": null },
  "done": false
}
```

`done` is computed from real rows (reuse the existing counts in
`setup_checklist`). No step ever blocks the API.

### C.2 Branching matrix

Base journey per business type, then add/remove by answers and packs:

| Signal | Steps added / removed |
|---|---|
| `general` | add product → open shift (if required) → first sale |
| café / restaurant | "Add your menu items"; + "Set up tables" when `tables` |
| mart | "Add products with barcodes"; + "Set reorder points" |
| electronics | "Add products with serial numbers" |
| stores > 1 | + "Add your second store", "Transfer stock between stores" |
| team > 1 | + "Invite a team member", "Set roles & permissions" |
| `batches` | + "Track a product's expiry" |
| `serials` | + "Add a product with an IMEI" |
| solo + 1 store | never show team/store steps |

### C.3 API shape

Prefer **extending** `GET /setup/checklist` (backward-compatible additions) over
a new endpoint:

- add `goal: "first_sale"`, `next_step_id`, and the richer step fields above;
- keep `completed` / `total`.

Dismissal is **per user**, not per store, so a cashier can hide their own coach:
persist to `User.preferences.setup_journey_dismissed` via the existing
`PATCH /auth/me/preferences` (`v1.py:6121`) — no new endpoint.

### C.4 Frontend coach

- New `components/SetupJourney.jsx`, mounted in the workspace shell
  (`workspace.jsx`) so it persists across views:
  compact card — "Step 2 of 4 · Add a product · **[Show me]** · Dismiss".
- **Auto-advance:** refetch the journey wherever the app already refreshes data.
  `handleOrderCompleted → refreshOperationalData()` is the natural hook for the
  first-sale step; add the same after product create and shift open.
- **Deep link + spotlight:** each step carries `view` + `anchor`; "Show me"
  navigates there and draws a CSS ring on the element tagged
  `data-coach="<anchor>"`. No new dependency.
- **Celebrate** the completed first sale, then stop nagging.
- Respect RBAC (`canViewRole`) and the two gating layers before showing a step.

### C.5 Persistence summary

| Data | Storage | Notes |
|---|---|---|
| Answers | `Store.preferences.onboarding_profile` | JSON, no migration |
| Capability overrides | `Store.preferences.capability_overrides` | delta model |
| Journey dismissal | `User.preferences.setup_journey_dismissed` | per user |
| Progress | derived from rows | never stored |

## 8. Data model changes

- **v1: none.** All state rides in existing JSON columns.
- Optional later: promote `Company.vertical`-adjacent onboarding answers to real
  columns if we want to index/report on them. One Alembic revision, `down_revision`
  chained to the single head (`alembic heads` must show one).

## 9. Interaction with plan features (keep the two layers distinct)

A journey step may depend on a **capability** (vertical/UI) and/or a **plan
feature** (billing). Show a step only when both are satisfied:

- `requires.capability` — from `capabilities_for` (e.g. `serials`).
- `requires.plan_feature` — from the active plan's `capabilities` (e.g.
  `table_management`; note `#395` now includes it on Starter).

This keeps "what the UI surfaces" separate from "what the merchant paid for".

## 10. Phased delivery (one branch / PR each)

| Phase | Deliverable | Branch | PR | Migration |
|---|---|---|---|---|
| 1 ✅ | Business type in Settings + delta overrides + reset + `general` empty-state | `feat/business-type-settings` | #400 | no |
| 2 ✅ | Onboarding goal questions + plan recommendation | `feat/onboarding-goal-questions` | #403 | no |
| 3 ✅ | Capability seeding from answers + onboarding profile | `feat/onboarding-capability-seeding` | #406 | no |
| 4 ✅ | Journey backend: adaptive `/setup/checklist` + branch matrix | `feat/setup-journey-api` | #407 | no |
| 5 ✅ | Journey frontend: persistent coach, auto-advance, spotlight, celebration | `feat/guided-setup-coach` | #409 | no |
| 6 ✅ | Coach spotlight anchors on POS/catalog/settings/team controls | `feat/setup-coach-anchors` | #412 | no |

All phases shipped one PR at a time, each green on CI before merge. Phase 1
unblocked manual testing of the whole packs story (before it, a `general` store
could not change type from the UI).

## 11. Testing & CI

- **API (pytest):**
  - `capabilities_for` with defaults, legacy absolute override, and delta
    overrides (add/remove, unknown keys dropped, `general` + added).
  - `recommend_plan` across band boundaries, ties, and "none eligible".
  - Journey builder: vertical base, answer branches, capability/feature gating,
    terminal first-sale, `next_step_id`.
- **Web (`node --test`):** pure helpers (recommendation display, journey
  next-step selection, capability seeding).
- **e2e (Playwright):** mocked onboarding questions → recommended badge; mocked
  journey auto-advance after a sale.
- Regenerate and commit `chmabapos_api/openapi.json` for any schema change
  (`python chmabapos_api/scripts/export_openapi.py`); CI fails on drift.
- `alembic heads` must stay a single head.

## 12. Risks & open questions

1. **Override migration** — legacy absolute `capabilities` must keep working;
   define precedence clearly and test it.
2. **Changing business type after customization** — delta model keeps defaults
   live; the "Reset" button gives an escape hatch. Confirm the UX wording.
3. **Recommendation vs real limits** — always derive from DB `Plan` rows, never
   hardcode; plans are editable in the admin panel.
4. **Intrusiveness** — team-size questions can feel nosy; make them optional and
   explain the benefit ("so we recommend the right plan").
5. **Not blocking** — enforce the advisory rule in review; a hidden step must
   never 4xx.
6. **RBAC** — a cashier must not see owner-only steps (billing, team).
7. **Language** — the corpus supports en/km; decide whether journey copy is
   localized in this phase.
8. **Measurement** — add activation analytics (signup → first sale rate) so the
   journey's impact is visible.

Open questions:

- Ask about transaction volume too, or keep to stores/team?
- Should the recommended paid plan be auto-selected (still requires explicit
  confirmation), or only flagged?
- Band boundaries (5 vs 10 stores; 10 vs 20 team) — align with real plan limits
  and revisit if plans change.

## 13. Follow-ups (post-implementation)

The plan shipped in full. Remaining nice-to-haves:

- Add the `settings-khqr` spotlight anchor inside the Bank & KHQR pane (the coach
  navigates there today but does not ring a specific control).
- Feed the guided journey into the AI assistant's context ("what do I do now?").
- Add activation analytics (signup → first sale) so the journey's impact is
  measurable.
- Localize the onboarding questions and coach copy (en/km).

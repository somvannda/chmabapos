# User Guides

The public, step-by-step setup library at `chmaba.com/guides`. It is separate
from the in-app help center: a guide is a long-form page for someone who may not
have a workspace yet, and it is managed like a blog through the platform admin.

## Public routes

| Route | Purpose |
|---|---|
| `/guides` | Library index: search, featured guides, categories and every guide in reading order. |
| `/guides/<category-slug>` | One business path, grouped by stage. |
| `/guides/<category-slug>/<guide-slug>` | The step player. |

The library ships five business paths: **Coffee shop** (12 guides), **Restaurant**
(8), **Mart / grocery** (5), **Electronics store** (4) and **General retail** (4,
covering the retail shop and the catch-all “Other / general” business type).

The reader is a step player rather than a long article:

- One section is one step, with a real product screenshot.
- A cross-guide timeline at the top shows every guide in the path, which guides
  are done, where the reader is, and what is up next.
- The category page shows a **Continue your path** card: the next incomplete
  guide, the step to resume at, the path percentage and a one-click resume.
- Progress, checked actions and the current step are saved in `localStorage`
  under `chmaba.guide.progress.v1`, keyed by guide slug.
- The final step shows takeaways, the next guide and a Start free CTA.

## Content model

- `guide_categories` - `slug`, `name`, `description`, `icon`, `accent`,
  `position`, `is_active`. A category is public only when active and it has at
  least one published guide.
- `guides` - belongs to a category; unique `(category_id, slug)`. Holds the
  title, summary, stage (`group_title`), level, reading time, intro, learning
  points, requirements, JSON `sections`, takeaways, SEO fields, status
  (`draft` / `published` / `archived`), featured flag, position, view count and
  publish timestamp.
- A section is `{ heading, body: [paragraph], steps: [string], tip }`.

Seeded content lives in `chmabapos_api/app/guide_content.py`; the tables are
created and seeded by `a8c9e1f3b5d7_add_user_guides.py`. Copy fixes that must
reach an existing database get their own data migration (see
`b9d0f2a4c6e8_refresh_guide_copy.py`).

## API

Public (rate-limited, no auth):

- `GET /api/v1/public/guides`
- `GET /api/v1/public/guides/{category_slug}`
- `GET /api/v1/public/guides/{category_slug}/{guide_slug}`

Platform admin:

- `GET|POST /api/v1/admin/guide-categories`
- `PATCH|DELETE /api/v1/admin/guide-categories/{id}`
- `GET|POST /api/v1/admin/guides`
- `PATCH|DELETE /api/v1/admin/guides/{id}`

Deleting a category that still has guides is refused. Deleting a guide is a
hard delete; archive it when the history matters.

## Admin CMS

`apps/admin` -> **User guides** (`/admin/guides`) provides:

- Guide list with search, status and category filters; publish, unpublish, view
  live page, edit and delete.
- Full editor: basics, category/stage/level, intro, repeatable section blocks,
  learning points, requirements, takeaways, SEO, featured flag, position and
  publish status.
- Category manager: create, edit, reorder, hide and delete categories.
- Public preview links (drafts stay private until published).

## Screenshots

Guide illustrations are real screenshots, not drawings. They are captured from
the running app by:

1. `python chmabapos_api/scripts/seed_guides_demo.py` - creates the local demo
   coffee workspace and representative menu/sales.
2. `node apps/web/scripts/capture-guide-screens.mjs` - signs in, walks the real
   screens and writes JPEGs to `apps/web/public/guide-screens/`.

When a screen changes, re-capture the affected file; do not edit the guide
component to imitate the UI.

## Tests

- `chmabapos_api/tests/test_guides.py` covers the seeded library, drafts staying
  private, publishing, archiving, slug validation, category deletion guard and
  the `series` payload.
- `apps/web/src/lib/routing.test.js` covers guide routes.
- `apps/web/src/lib/marketingNavWiring.test.js` covers the header/footer links.

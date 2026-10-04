# @chmaba/api-client

Generated TypeScript types for the Chmaba POS API, plus a thin typed fetch
client. This implements **ADR-005** (`docs/architecture.md`): the API contract is
the committed OpenAPI spec, and both front-ends adopt this package incrementally
instead of the hand-rolled `apps/*/src/api.js`.

## Generate

`src/schema.d.ts` is generated from `chmabapos_api/openapi.json` and **must not
be edited by hand**. Regenerate after any API change and commit the result
together with it (CI checks for drift):

```bash
cd packages/api-client
npm install
npm run generate
```

## Usage

```ts
import { createApiClient } from "@chmaba/api-client";

const api = createApiClient({
  baseUrl: import.meta.env.VITE_API_URL,
  getToken: () => window.localStorage.getItem("chmaba.access_token"),
  getStoreId: () => currentStoreId,
});

const workspace = await api.request("/workspaces/current");
```

The generated `paths` / `components` types can be composed into typed helpers as
adoption grows; the goal is a single source of truth for request and response
shapes.

## Status

Types are generated and committed; day-to-day adoption in `apps/web` and
`apps/admin` is tracked as a follow-up so it can land incrementally without a
flag day.

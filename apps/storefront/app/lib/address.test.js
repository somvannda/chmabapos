import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { canonicalRedirect, storeAddress } from "./address.js";

// The rename path that `previous_slugs` exists for: an old address must not 404,
// and it must not silently keep serving two URLs for the same store either. The
// API resolves a retired slug and reports the current one; this decides whether
// to render or to redirect, so a wrong answer here is a redirect loop or a dead
// printed link.

test("an address with both segments is usable, a partial one is not", () => {
  assert.deepEqual(storeAddress({ company_slug: "acme", store_slug: "downtown" }), {
    company: "acme",
    store: "downtown",
  });
  assert.equal(storeAddress({ company_slug: "acme" }), null);
  assert.equal(storeAddress({ store_slug: "downtown" }), null);
  assert.equal(storeAddress({}), null);
  assert.equal(storeAddress(null), null);
});

test("the canonical address renders instead of redirecting", () => {
  const store = { company_slug: "acme", store_slug: "downtown" };
  assert.equal(canonicalRedirect(store, { companySlug: "acme", storeSlug: "downtown" }), null);
});

test("a retired company segment or a retired store segment redirects", () => {
  const store = { company_slug: "acme", store_slug: "downtown" };
  assert.equal(canonicalRedirect(store, { companySlug: "old-acme", storeSlug: "downtown" }), "/acme/downtown");
  assert.equal(canonicalRedirect(store, { companySlug: "acme", storeSlug: "uptown" }), "/acme/downtown");
  assert.equal(canonicalRedirect(store, { companySlug: "old", storeSlug: "older" }), "/acme/downtown");
});

test("table and product context survive the redirect", () => {
  const store = { company_slug: "acme", store_slug: "downtown" };
  const params = { companySlug: "old-acme", storeSlug: "downtown" };
  assert.equal(canonicalRedirect(store, params, { tableCode: "T 12" }), "/acme/downtown/t/T%2012");
  assert.equal(
    canonicalRedirect(store, params, { productId: "a/b" }),
    "/acme/downtown/product/a%2Fb",
  );
});

test("a store without slugs never redirects, so a legacy row cannot loop", () => {
  assert.equal(canonicalRedirect({ company_slug: null, store_slug: "downtown" }, {}), null);
  assert.equal(canonicalRedirect({ company_slug: "acme", store_slug: "" }, {}), null);
});

test("both store-front loaders apply the rename redirect", () => {
  for (const file of ["../routes/store.jsx", "../routes/product.jsx"]) {
    const source = readFileSync(new URL(file, import.meta.url), "utf8");
    assert.match(source, /canonicalRedirect/, `${file} does not resolve the canonical address`);
    assert.match(source, /redirect\(canonical, 301\)/, `${file} does not send a 301 for a renamed slug`);
  }
});

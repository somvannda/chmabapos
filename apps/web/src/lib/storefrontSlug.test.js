import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import {
  RESERVED_COMPANY_SLUGS,
  RESERVED_STORE_SLUGS,
  SLUG_MAX_LENGTH,
  slugProblem,
  slugifyName,
} from "./storefrontSlug.js";

// The Settings address editor mirrors the API's rules so a merchant sees the
// answer before saving. These tests pin the two halves that would otherwise
// drift silently: the suggestion algorithm, and the reserved-word list.

const here = dirname(fileURLToPath(import.meta.url));
const apiSource = readFileSync(
  join(here, "..", "..", "..", "..", "chmabapos_api", "app", "slugs.py"),
  "utf8",
);

test("a Latin name suggests a usable address", () => {
  assert.equal(slugifyName("Acme Coffee"), "acme-coffee");
  assert.equal(slugifyName("Acme  Coffee   3"), "acme-coffee-3");
  assert.equal(slugifyName("  Riverside Store!  "), "riverside-store");
});

test("accents fold to ASCII the way the server folds them", () => {
  // `slugify()` encodes to ASCII with "ignore"; matching it here means the
  // suggestion is not rejected by the API when the merchant accepts it.
  assert.equal(slugifyName("Café Sralanh"), "cafe-sralanh");
});

test("a name with no Latin letters suggests nothing", () => {
  // A Khmer name transliterates to nothing. Offering the fallback "company"
  // here is what produced /company-3/store in the first place.
  assert.equal(slugifyName("ហាងកាហ្វេ"), "");
  assert.equal(slugifyName(""), "");
  assert.equal(slugifyName("AB"), "");
});

test("validation mirrors the API's messages", () => {
  assert.equal(slugProblem("acme-coffee"), "");
  assert.equal(slugProblem(""), "Enter a web address");
  assert.equal(slugProblem("ab"), "Use at least 3 characters");
  assert.equal(slugProblem("a".repeat(SLUG_MAX_LENGTH + 1)), "Use at most 50 characters");
  assert.equal(slugProblem("Bad Slug!"), "Use lowercase letters, numbers and single hyphens only");
  assert.equal(slugProblem("-leading"), "Use lowercase letters, numbers and single hyphens only");
  assert.equal(slugProblem("double--hyphen"), "Use lowercase letters, numbers and single hyphens only");
});

test("reserved words are refused, and the store list is narrower", () => {
  assert.match(slugProblem("stores", { company: true }), /reserved/);
  assert.equal(slugProblem("stores", { company: false }), "");
  assert.match(slugProblem("order"), /reserved/);
  assert.match(slugProblem("order", { company: true }), /reserved/);
});

test("the reserved-word lists match app/slugs.py", () => {
  const block = (name) => {
    const match = apiSource.match(new RegExp(`${name}\\s*=\\s*frozenset\\(\\s*\\{([^}]*)\\}`, "s"));
    assert.ok(match, `${name} is not declared as a frozenset literal in app/slugs.py`);
    return new Set([...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1]));
  };
  const apiCompany = block("RESERVED_COMPANY_SLUGS");
  const apiStore = block("RESERVED_STORE_SLUGS");
  for (const slug of apiCompany) {
    assert.ok(RESERVED_COMPANY_SLUGS.has(slug), `company slug ${slug} is reserved by the API but not the client`);
  }
  for (const slug of RESERVED_COMPANY_SLUGS) {
    assert.ok(apiCompany.has(slug), `client reserves company slug ${slug} that the API does not`);
  }
  for (const slug of apiStore) {
    assert.ok(RESERVED_STORE_SLUGS.has(slug), `store slug ${slug} is reserved by the API but not the client`);
  }
  for (const slug of RESERVED_STORE_SLUGS) {
    assert.ok(apiStore.has(slug), `client reserves store slug ${slug} that the API does not`);
  }
});

import test from "node:test";
import assert from "node:assert/strict";

import { COUNTRY_OPTIONS, countryOptions } from "./countries.js";

test("country options are uniquely valued and cover common markets", () => {
  const values = COUNTRY_OPTIONS.map((option) => option.value);
  assert.equal(new Set(values).size, values.length, "country values must be unique");
  for (const name of ["Cambodia", "Thailand", "Vietnam", "Singapore", "United States", "United Kingdom"]) {
    assert.ok(values.includes(name), `${name} should be in the list`);
  }
});

test("countryOptions keeps a stored value that is not in the list", () => {
  const options = countryOptions("Freedonia");
  assert.equal(options[0].value, "Freedonia");
  assert.equal(options.length, COUNTRY_OPTIONS.length + 1);
});

test("countryOptions returns the plain list for empty or known values", () => {
  assert.equal(countryOptions("").length, COUNTRY_OPTIONS.length);
  assert.equal(countryOptions("   ").length, COUNTRY_OPTIONS.length);
  assert.equal(countryOptions("Cambodia").length, COUNTRY_OPTIONS.length);
});

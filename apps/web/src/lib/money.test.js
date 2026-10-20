import test from "node:test";
import assert from "node:assert/strict";

import { currencyDecimals, moneyInput } from "./money.js";

test("the riel has no subunit", () => {
  assert.equal(currencyDecimals("KHR"), 0);
  assert.equal(moneyInput(3666, "KHR"), "3666");
  assert.equal(moneyInput("3666.30", "KHR"), "3666");
});

test("dollar amounts keep two decimals", () => {
  assert.equal(currencyDecimals("USD"), 2);
  assert.equal(moneyInput(10, "USD"), "10.00");
  assert.equal(moneyInput("10.5", "USD"), "10.50");
});

test("a missing or unknown currency falls back to two decimals", () => {
  assert.equal(moneyInput(10, undefined), "10.00");
  assert.equal(moneyInput(10, "THB"), "10.00");
});

test("an unparsable value yields a blank-ish amount per currency", () => {
  assert.equal(moneyInput("", "USD"), "0.00");
  assert.equal(moneyInput("", "KHR"), "0");
});

test("the currency code is case-insensitive", () => {
  assert.equal(moneyInput(3666, "khr"), "3666");
});

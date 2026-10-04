import test from "node:test";
import assert from "node:assert/strict";

import { SUPPORTED_LANGUAGES, getStoredLanguage, translate } from "./i18n.js";

test("supported languages are en and km", () => {
  assert.deepEqual(SUPPORTED_LANGUAGES, ["en", "km"]);
});

test("translate returns English by default", () => {
  assert.equal(translate("coach.showMe"), "Show me");
  assert.equal(translate("questions.back", "en"), "Back");
});

test("translate returns Khmer for km", () => {
  const km = translate("coach.showMe", "km");
  assert.notEqual(km, "Show me");
  assert.ok(km.length > 0);
});

test("translate falls back to the key for an unknown string", () => {
  assert.equal(translate("does.not.exist", "km"), "does.not.exist");
});

test("translate falls back to English for an unknown language", () => {
  assert.equal(translate("coach.showMe", "fr"), "Show me");
});

test("getStoredLanguage falls back when localStorage is unavailable", () => {
  // node has no localStorage; the helper must not throw and must use the fallback.
  assert.equal(getStoredLanguage("en"), "en");
  assert.equal(getStoredLanguage(), "en");
});

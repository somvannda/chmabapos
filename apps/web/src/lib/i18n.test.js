import test from "node:test";
import assert from "node:assert/strict";

import { SUPPORTED_LANGUAGES, getStoredLanguage, stepText, translate } from "./i18n.js";

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

test("stepText localizes a known step into Khmer", () => {
  const step = { id: "first-sale", title: "Ring up your first sale", description: "English desc" };
  const text = stepText(step, "km");
  assert.notEqual(text.title, step.title);
  assert.notEqual(text.description, step.description);
});

test("stepText uses a vertical-specific add-product title", () => {
  const step = { id: "add-product", title: "Add your first product", description: "d" };
  const coffee = stepText(step, "km", "coffee");
  const mart = stepText(step, "km", "mart");
  assert.notEqual(coffee.title, mart.title);
});

test("stepText falls back to the API text for English", () => {
  const step = { id: "first-sale", title: "Ring up your first sale", description: "English desc" };
  assert.deepEqual(stepText(step, "en"), { title: step.title, description: step.description });
});

test("stepText falls back for an unknown step id", () => {
  const step = { id: "future-step", title: "Future", description: "Future desc" };
  assert.deepEqual(stepText(step, "km"), { title: "Future", description: "Future desc" });
});

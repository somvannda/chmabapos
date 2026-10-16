import test from "node:test";
import assert from "node:assert/strict";

import {
  THEME_BOOTSTRAP,
  THEME_STORAGE_KEY,
  applyTheme,
  nextTheme,
  normalizeTheme,
  readStoredTheme,
  writeStoredTheme,
} from "./theme.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => { data[key] = String(value); },
    dump: () => ({ ...data }),
  };
}

test("normalizeTheme: only the two real themes are accepted", () => {
  assert.equal(normalizeTheme("dark"), "dark");
  assert.equal(normalizeTheme("light"), "light");
  assert.equal(normalizeTheme("Dark"), null);
  assert.equal(normalizeTheme(""), null);
  assert.equal(normalizeTheme(null), null);
  assert.equal(normalizeTheme(undefined), null);
});

test("the theme round-trips through storage", () => {
  const storage = fakeStorage();
  assert.equal(readStoredTheme(() => storage), null);
  writeStoredTheme("dark", () => storage);
  assert.equal(readStoredTheme(() => storage), "dark");
});

test("writeStoredTheme: a value that is not a theme is not stored", () => {
  const storage = fakeStorage();
  writeStoredTheme("chartreuse", () => storage);
  assert.deepEqual(storage.dump(), {});
});

test("storage being unavailable is survived rather than thrown", () => {
  // Private mode throws on access; the page still has to render.
  const hostile = () => { throw new Error("blocked"); };
  assert.equal(readStoredTheme(hostile), null);
  assert.doesNotThrow(() => writeStoredTheme("dark", hostile));
});

test("nextTheme: flips", () => {
  assert.equal(nextTheme("light"), "dark");
  assert.equal(nextTheme("dark"), "light");
});

test("applyTheme: toggles the class the tokens key off", () => {
  const classes = new Set();
  const root = {
    classList: {
      toggle: (name, on) => { if (on) classes.add(name); else classes.delete(name); },
    },
  };
  applyTheme("dark", root);
  assert.equal(classes.has("dark"), true);
  applyTheme("light", root);
  assert.equal(classes.has("dark"), false);
  applyTheme("nonsense", root);
  assert.equal(classes.has("dark"), false, "an unknown value means light, not dark");
});

test("the pre-paint bootstrap follows the system only when nothing is stored", () => {
  assert.match(THEME_BOOTSTRAP, new RegExp(THEME_STORAGE_KEY));
  assert.match(THEME_BOOTSTRAP, /prefers-color-scheme: dark/);
  // "stored dark, or nothing stored and the system is dark" - so a stored light on a
  // dark machine stays light, which is what makes the toggle look like it works.
  assert.match(THEME_BOOTSTRAP, /s==="dark"\|\|\(s===null&&/);
});

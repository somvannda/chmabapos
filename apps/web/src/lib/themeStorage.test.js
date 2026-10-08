import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ACCESS_TOKEN_KEY,
  THEME_STORAGE_KEY,
  normalizeTheme,
  readAccessToken,
  readStoredTheme,
  writeStoredTheme,
} from "./themeStorage.js";

// In-memory Storage stand-in so the helpers can be exercised without a browser.
function memoryStorage(initial = {}) {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    value: (key) => (data.has(key) ? data.get(key) : null),
  };
}

function brokenStorage() {
  return {
    getItem: () => {
      throw new Error("storage disabled");
    },
    setItem: () => {
      throw new Error("storage disabled");
    },
  };
}

test("theme: only dark and light are valid themes", () => {
  assert.equal(normalizeTheme("dark"), "dark");
  assert.equal(normalizeTheme("light"), "light");
  assert.equal(normalizeTheme("blue"), null);
  assert.equal(normalizeTheme(undefined), null);
});

test("theme: the persisted theme is read back, junk is ignored", () => {
  assert.equal(readStoredTheme(() => memoryStorage({ [THEME_STORAGE_KEY]: "dark" })), "dark");
  assert.equal(readStoredTheme(() => memoryStorage({ [THEME_STORAGE_KEY]: "sepia" })), null);
  assert.equal(readStoredTheme(() => memoryStorage()), null);
});

test("theme: writing persists the theme and ignores invalid values", () => {
  const storage = memoryStorage();
  writeStoredTheme("light", () => storage);
  assert.equal(storage.value(THEME_STORAGE_KEY), "light");

  writeStoredTheme("neon", () => storage);
  assert.equal(storage.value(THEME_STORAGE_KEY), "light", "invalid theme must not overwrite");
});

test("theme: the access token is read from localStorage or sessionStorage", () => {
  const local = memoryStorage({ [ACCESS_TOKEN_KEY]: "local-token" });
  const session = memoryStorage({ [ACCESS_TOKEN_KEY]: "session-token" });

  assert.equal(readAccessToken(() => local, () => session), "local-token", "localStorage wins");
  assert.equal(
    readAccessToken(() => memoryStorage(), () => session),
    "session-token",
    "session-only sign-ins must still be found",
  );
  assert.equal(readAccessToken(() => memoryStorage(), () => memoryStorage()), "");
});

test("theme: storage failures never throw", () => {
  assert.equal(readStoredTheme(brokenStorage), null);
  assert.doesNotThrow(() => writeStoredTheme("dark", brokenStorage));
  assert.equal(readAccessToken(brokenStorage, brokenStorage), "");
});

test("theme: the provider persists with a token from either storage", () => {
  // Static guard for the regression: the provider used to read the token from
  // localStorage only, so session-only sign-ins never synced the theme and the
  // server value flipped the UI back on refresh.
  const ui = readFileSync(new URL("../components/ui.jsx", import.meta.url), "utf8");
  assert.match(ui, /readAccessToken\(/, "the provider must use the shared token reader");
  assert.match(ui, /window\.localStorage/, "localStorage sessions must be read");
  assert.match(ui, /window\.sessionStorage/, "sessionStorage sessions must be read");
  assert.doesNotMatch(
    ui,
    /window\.localStorage\.getItem\("chmaba\.access_token"\)/,
    "must not read the access token from localStorage alone",
  );
});

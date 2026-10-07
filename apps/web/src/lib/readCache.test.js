import test from "node:test";
import assert from "node:assert/strict";

import { cacheKey, fetchWithCache, isNetworkError, loadCache, saveCache } from "./readCache.js";

function fakeStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
}

test("readCache: save and load round-trip", () => {
  const storage = fakeStorage();
  assert.equal(loadCache("store-1", "products", storage), null);
  saveCache("store-1", "products", [{ id: "p1" }], storage);
  const cached = loadCache("store-1", "products", storage);
  assert.deepEqual(cached.value, [{ id: "p1" }]);
  assert.equal(typeof cached.at, "number");
});

test("readCache: isolates stores and names", () => {
  const storage = fakeStorage();
  saveCache("store-1", "products", [{ id: "a" }], storage);
  saveCache("store-2", "products", [{ id: "b" }], storage);
  saveCache("store-1", "inventory", [{ id: "c" }], storage);
  assert.deepEqual(loadCache("store-1", "products", storage).value, [{ id: "a" }]);
  assert.deepEqual(loadCache("store-2", "products", storage).value, [{ id: "b" }]);
  assert.deepEqual(loadCache("store-1", "inventory", storage).value, [{ id: "c" }]);
  assert.notEqual(cacheKey("store-1", "products"), cacheKey("store-2", "products"));
});

test("readCache: tolerates corrupt storage", () => {
  const storage = fakeStorage();
  storage.setItem(cacheKey("store-1", "products"), "{not json");
  assert.equal(loadCache("store-1", "products", storage), null);
  storage.setItem(cacheKey("store-1", "products"), JSON.stringify({ missing: "value" }));
  assert.equal(loadCache("store-1", "products", storage), null);
});

test("readCache: fetchWithCache caches a successful read", async () => {
  const storage = fakeStorage();
  const result = await fetchWithCache("store-1", "products", async () => [{ id: "p1" }], storage);
  assert.equal(result.stale, false);
  assert.deepEqual(result.value, [{ id: "p1" }]);
  assert.deepEqual(loadCache("store-1", "products", storage).value, [{ id: "p1" }]);
});

test("readCache: fetchWithCache falls back to cache on a network error", async () => {
  const storage = fakeStorage();
  saveCache("store-1", "products", [{ id: "cached" }], storage);
  const result = await fetchWithCache("store-1", "products", async () => {
    throw new TypeError("failed to fetch");
  }, storage);
  assert.equal(result.stale, true);
  assert.deepEqual(result.value, [{ id: "cached" }]);
});

test("readCache: fetchWithCache rethrows an API error instead of using stale data", async () => {
  const storage = fakeStorage();
  saveCache("store-1", "products", [{ id: "cached" }], storage);
  await assert.rejects(
    fetchWithCache("store-1", "products", async () => {
      const error = new Error("forbidden");
      error.status = 403;
      throw error;
    }, storage),
    /forbidden/,
  );
});

test("readCache: fetchWithCache rethrows a network error with no cache", async () => {
  const storage = fakeStorage();
  await assert.rejects(
    fetchWithCache("store-1", "products", async () => {
      throw new TypeError("failed to fetch");
    }, storage),
    /failed to fetch/,
  );
});

test("readCache: classifies network vs API errors", () => {
  assert.equal(isNetworkError(new TypeError("failed to fetch")), true);
  assert.equal(isNetworkError({ status: undefined }), true);
  assert.equal(isNetworkError({ status: 500 }), false);
  assert.equal(isNetworkError({ status: 422 }), false);
});

// Read-through cache for POS catalogue data (G9 Phase 2 offline mode).
//
// Successful reads of the data the POS needs to sell (products, inventory,
// combos) are stored per store, so a cashier whose network drops — or whose
// API is briefly unreachable — still sees the last-known catalogue instead of
// an empty till. Only a *network* failure (no HTTP status) falls back to the
// cache; a real API error (4xx/5xx) still surfaces, so a permissions or
// validation problem is never masked by stale data.

const PREFIX = "chmaba.cache.";

export function cacheKey(storeId, name) {
  return `${PREFIX}${storeId}:${name}`;
}

export function saveCache(storeId, name, value, storage = globalThis.localStorage) {
  try {
    storage?.setItem(cacheKey(storeId, name), JSON.stringify({ at: Date.now(), value }));
  } catch {
    /* storage unavailable (private mode / quota) — caching is best effort */
  }
}

/** Returns `{ value, at }` for a stored entry, or null when missing/corrupt. */
export function loadCache(storeId, name, storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem(cacheKey(storeId, name));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !("value" in parsed)) return null;
    return { value: parsed.value, at: Number(parsed.at) || 0 };
  } catch {
    return null;
  }
}

/** A network failure has no HTTP status; an API error carries one. */
export function isNetworkError(error) {
  return error?.status == null;
}

/**
 * Read through: on success the result is cached; on a network failure the last
 * cached value is returned with `stale: true`. Any other error is rethrown.
 */
export async function fetchWithCache(storeId, name, loader, storage = globalThis.localStorage) {
  try {
    const value = await loader();
    saveCache(storeId, name, value, storage);
    return { value, stale: false, at: Date.now() };
  } catch (error) {
    if (isNetworkError(error)) {
      const cached = loadCache(storeId, name, storage);
      if (cached) return { value: cached.value, stale: true, at: cached.at };
    }
    throw error;
  }
}

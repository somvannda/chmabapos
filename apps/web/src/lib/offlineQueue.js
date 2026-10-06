// Offline sale queue (G9 Phase 1).
//
// A cash sale taken while the API is unreachable is stored locally with a
// stable `client_order_id` and replayed once connectivity returns; the backend
// dedupes on that id, so a replay never creates a duplicate. See
// docs/offline-mode-plan.md.

export const OFFLINE_ORDERS_KEY = "chmaba.offline.orders";

export function loadOfflineOrders(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem(OFFLINE_ORDERS_KEY);
    const rows = raw ? JSON.parse(raw) : [];
    return Array.isArray(rows) ? rows : [];
  } catch {
    return [];
  }
}

export function saveOfflineOrders(rows, storage = globalThis.localStorage) {
  try {
    storage?.setItem(OFFLINE_ORDERS_KEY, JSON.stringify(rows));
  } catch {
    /* storage unavailable (private mode / quota) — nothing we can do */
  }
  return rows;
}

export function enqueueOfflineOrder(storeId, body, storage = globalThis.localStorage) {
  const rows = loadOfflineOrders(storage);
  rows.push({ storeId, body, queuedAt: Date.now() });
  saveOfflineOrders(rows, storage);
  return rows.length;
}

/** A failure worth retrying: no HTTP status (network) or a transient server error. */
export function isRetryable(error) {
  const status = error?.status;
  if (status == null) return true; // fetch/network failure, or a non-API throw
  if (status === 401) return true; // the session may be refreshed on re-login
  return status >= 500;
}

/**
 * Replay queued sales. Successes are dropped; retryable failures are kept for
 * the next attempt; a validation failure (4xx) is dropped and counted so the
 * caller can surface it.
 */
export async function flushOfflineOrders({ token, createOrder, storage = globalThis.localStorage }) {
  const rows = loadOfflineOrders(storage);
  if (rows.length === 0) return { flushed: 0, failed: 0, remaining: 0 };
  const remaining = [];
  let flushed = 0;
  let failed = 0;
  for (const row of rows) {
    try {
      await createOrder(token, row.storeId, row.body);
      flushed += 1;
    } catch (error) {
      if (isRetryable(error)) remaining.push(row);
      else failed += 1;
    }
  }
  saveOfflineOrders(remaining, storage);
  return { flushed, failed, remaining: remaining.length };
}

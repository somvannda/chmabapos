// Offline sale queue (G9 Phase 1) plus a "needs attention" list (Phase 3).
//
// A cash sale taken while the API is unreachable is stored locally with a
// stable `client_order_id` and replayed once connectivity returns; the backend
// dedupes on that id, so a replay never creates a duplicate. A replay the
// server *rejects* (a validation error, e.g. stock changed) is not silently
// dropped: it moves to a failed list the cashier can review, retry or dismiss.
// See docs/offline-mode-plan.md.

export const OFFLINE_ORDERS_KEY = "chmaba.offline.orders";
export const OFFLINE_FAILED_KEY = "chmaba.offline.orders.failed";

function readRows(key, storage) {
  try {
    const raw = storage?.getItem(key);
    const rows = raw ? JSON.parse(raw) : [];
    return Array.isArray(rows) ? rows : [];
  } catch {
    return [];
  }
}

function writeRows(key, rows, storage) {
  try {
    storage?.setItem(key, JSON.stringify(rows));
  } catch {
    /* storage unavailable (private mode / quota) — nothing we can do */
  }
  return rows;
}

export function loadOfflineOrders(storage = globalThis.localStorage) {
  return readRows(OFFLINE_ORDERS_KEY, storage);
}

export function saveOfflineOrders(rows, storage = globalThis.localStorage) {
  return writeRows(OFFLINE_ORDERS_KEY, rows, storage);
}

export function loadFailedOrders(storage = globalThis.localStorage) {
  return readRows(OFFLINE_FAILED_KEY, storage);
}

export function saveFailedOrders(rows, storage = globalThis.localStorage) {
  return writeRows(OFFLINE_FAILED_KEY, rows, storage);
}

function newId() {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : String(Date.now()) + Math.random().toString(16).slice(2);
}

/** Stable identity for a queued/failed row (older rows predate `id`). */
export function rowKey(row) {
  return row?.id || String(row?.queuedAt ?? "");
}

export function enqueueOfflineOrder(storeId, body, storage = globalThis.localStorage) {
  const rows = loadOfflineOrders(storage);
  rows.push({ id: newId(), storeId, body, queuedAt: Date.now() });
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
 * Whether a sale may be queued offline. Offline mode is cash-first: cash and
 * trade-in credit need no connectivity, but a KHQR/card tender must be settled
 * online — queuing it would replay later as an order that was never paid.
 * An order with no tenders (fully covered by trade-in) is safe.
 */
export function isOfflineQueuable(tenders) {
  const list = Array.isArray(tenders) ? tenders : [];
  return list.every((tender) => tender?.method === "cash" || tender?.method === "trade_in");
}

/**
 * Replay queued sales. Successes are removed; retryable failures are kept for
 * the next attempt; a validation failure (4xx) is moved to the failed list with
 * its error message so the cashier can act on it.
 */
export async function flushOfflineOrders({ token, createOrder, storage = globalThis.localStorage }) {
  const rows = loadOfflineOrders(storage);
  if (rows.length === 0) return { flushed: 0, failed: 0, remaining: 0 };
  const remaining = [];
  const failedRows = loadFailedOrders(storage);
  let flushed = 0;
  let failed = 0;
  for (const row of rows) {
    try {
      await createOrder(token, row.storeId, row.body);
      flushed += 1;
    } catch (error) {
      if (isRetryable(error)) {
        remaining.push(row);
      } else {
        failed += 1;
        const entry = { ...row, error: error?.message || "Rejected by the server", failedAt: Date.now() };
        if (!failedRows.some((item) => rowKey(item) === rowKey(entry))) failedRows.push(entry);
      }
    }
  }
  saveOfflineOrders(remaining, storage);
  if (failed > 0) saveFailedOrders(failedRows, storage);
  return { flushed, failed, remaining: remaining.length };
}

/** Drop one failed sale, or all of them, from the needs-attention list. */
export function dismissFailedOrder(key, storage = globalThis.localStorage) {
  const left = loadFailedOrders(storage).filter((row) => rowKey(row) !== key);
  saveFailedOrders(left, storage);
  return left;
}

/** Move a failed sale back onto the queue so it is retried on the next flush. */
export function retryFailedOrder(key, storage = globalThis.localStorage) {
  const failedRows = loadFailedOrders(storage);
  const row = failedRows.find((item) => rowKey(item) === key);
  if (!row) return { queued: loadOfflineOrders(storage).length, failed: failedRows.length };
  const { error, failedAt, ...original } = row;
  const queued = loadOfflineOrders(storage);
  queued.push(original);
  saveOfflineOrders(queued, storage);
  const left = failedRows.filter((item) => rowKey(item) !== key);
  saveFailedOrders(left, storage);
  return { queued: queued.length, failed: left.length };
}

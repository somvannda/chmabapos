// Offline reconciliation helpers (G9 Phase 3).
//
// A rejected offline sale can be brought back to the till: rebuild its still-
// sellable lines from the loaded catalogue so the cashier re-checks out through
// the normal flow (which prices and taxes the sale correctly). Combos and lines
// whose product is gone or out of stock are reported as skipped, never silently
// dropped. See docs/offline-mode-plan.md.

/**
 * Rebuild cart lines from a queued/failed order body using the POS's sellable
 * products (which already carry per-variant price/stock/lineKey).
 * Returns `{ lines, skipped }` where each skipped entry is `{ item, reason }`
 * with reason one of "combo" | "missing" | "stock".
 */
export function buildCartLinesFromFailed(body, sellableProducts) {
  const products = Array.isArray(sellableProducts) ? sellableProducts : [];
  const items = Array.isArray(body?.items) ? body.items : [];
  const lines = [];
  const skipped = [];
  for (const item of items) {
    if (item.combo_id) {
      skipped.push({ item, reason: "combo" });
      continue;
    }
    const local = products.find(
      (entry) => entry.id === item.product_id && (entry.variant_id || null) === (item.variant_id || null),
    );
    if (!local) {
      skipped.push({ item, reason: "missing" });
      continue;
    }
    const stock = Number(local.stock ?? 0);
    if (!(stock > 0)) {
      skipped.push({ item, reason: "stock" });
      continue;
    }
    const modifiers = Array.isArray(item.modifiers) ? item.modifiers : [];
    const signature = modifiers.map((entry) => entry.name + ":" + entry.price_delta).sort().join("|");
    const delta = modifiers.reduce((sum, entry) => sum + Number(entry.price_delta || 0), 0);
    const quantity = Math.min(Math.max(1, Number(item.quantity) || 1), stock);
    lines.push({
      ...local,
      variant_id: item.variant_id || null,
      price: Number(local.price) + delta,
      lineKey: (local.lineKey || local.id) + "#" + signature,
      modifiers,
      quantity,
      stock,
    });
  }
  return { lines, skipped };
}

/** Add restored lines to the cart, merging same-line keys and capping to stock. */
export function mergeCartLines(cart, lines) {  const result = Array.isArray(cart) ? [...cart] : [];
  for (const line of Array.isArray(lines) ? lines : []) {
    const key = line.lineKey || line.id;
    const index = result.findIndex((entry) => (entry.lineKey || entry.id) === key);
    if (index >= 0) {
      const cap = Number(line.stock ?? Infinity);
      result[index] = {
        ...result[index],
        quantity: Math.min(Number(result[index].quantity || 0) + Number(line.quantity || 0), cap),
      };
    } else {
      result.push(line);
    }
  }
  return result;
}

/** Human label for a failed/rejected line, for the review UI. */
export function failedItemLabel(item, sellableProducts) {
  const products = Array.isArray(sellableProducts) ? sellableProducts : [];
  if (item?.combo_id) {
    const combo = products.find((entry) => entry.combo_id === item.combo_id);
    return combo?.name || "Combo";
  }
  const product = products.find(
    (entry) => entry.id === item?.product_id && (entry.variant_id || null) === (item?.variant_id || null),
  );
  return product?.name || item?.name || "Item";
}

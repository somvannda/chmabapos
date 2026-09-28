// Pure POS helpers, kept free of React/JSX so they can be unit-tested with node:test.

/** Cart discount: `amount` mode is a flat value clamped to the subtotal, otherwise a percentage (max 100). */
export function computeDiscount(subtotal, mode, input) {
  const value = Math.max(0, Number(input) || 0);
  if (mode === "amount") return Number(Math.min(value, subtotal).toFixed(2));
  return Number((subtotal * Math.min(100, value) / 100).toFixed(2));
}

/** Keep serials that are sellable for this store/variant: unattributed (null store/variant) units are allowed. */
export function serialCandidatesFor(candidates, { storeId, variantId } = {}) {
  const list = Array.isArray(candidates) ? candidates : [];
  return list.filter((serial) => (!serial.store_id || serial.store_id === storeId) && (!serial.variant_id || (variantId && serial.variant_id === variantId)));
}

/** Currency objects the store has enabled, for the payment modal. */
export function enabledCompanyCurrencies(companyCurrencies) {
  return (Array.isArray(companyCurrencies) ? companyCurrencies : []).filter((row) => row && row.is_enabled && row.currency).map((row) => row.currency);
}

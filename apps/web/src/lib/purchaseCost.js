// Supplier cost for a purchase-order line.
//
// A variant is one sellable specification; what each supplier charges for it
// lives on `supplier_product_prices` (one row per supplier, per variant). A
// product without variants is priced with `variant_id: null`, so both shapes go
// through the same lookup here.

function targetOf(variantId) {
  return variantId ? String(variantId) : null;
}

function fieldValue(unitCost) {
  if (unitCost === null || unitCost === undefined) return "";
  const text = String(unitCost).trim();
  return text === "" ? "" : text;
}

/** The quote one supplier gave for one variant (or for a variant-less product). */
export function findSupplierQuote(prices, { variantId = null, supplierId = null } = {}) {
  if (!supplierId) return null;
  const target = targetOf(variantId);
  return (prices || []).find(
    (row) => String(row.supplier_id) === String(supplierId) && targetOf(row.variant_id) === target,
  ) || null;
}

/** The quote the merchant marked as their default source for this variant. */
export function preferredSupplierQuote(prices, variantId = null) {
  const target = targetOf(variantId);
  return (prices || []).find((row) => row.is_preferred && targetOf(row.variant_id) === target) || null;
}

/**
 * Cost to prefill on a purchase-order line.
 *
 * The line's own supplier wins; otherwise the preferred supplier's quote is a
 * starting point the operator can overwrite. `source` tells the form which
 * caption to show, and "none" means the catalogue has no price to offer — the
 * operator has to enter what they actually pay.
 */
export function suggestedUnitCost(prices, { variantId = null, supplierId = null } = {}) {
  const exact = findSupplierQuote(prices, { variantId, supplierId });
  if (exact) return { unitCost: fieldValue(exact.unit_cost), source: "supplier", quote: exact };
  const preferred = preferredSupplierQuote(prices, variantId);
  if (preferred) return { unitCost: fieldValue(preferred.unit_cost), source: "preferred", quote: preferred };
  return { unitCost: "", source: "none", quote: null };
}

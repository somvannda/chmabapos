// Pure builders for modifier groups. Kept dependency-free so they can be
// unit-tested with node:test (the web app has no React test harness).
//
// The shape matches chmabapos_api/app/schemas.py::ModifierGroupInput /
// ModifierInput. A modifier may optionally point at an ingredient product and
// a quantity; the backend deducts that many units from stock when the option is
// chosen on a sale (recipe-based depletion).

// A blank row used when adding a modifier to a group.
export function emptyModifierRow() {
  return { name: "", price_delta: "0.00", ingredient_product_id: "", quantity: "1" };
}

// Turn an API modifier back into the editable row shape. A modifier with no
// ingredient keeps an empty string so the "No ingredient" option is selected.
export function modifierRowFrom(modifier) {
  return {
    name: modifier?.name ?? "",
    price_delta: modifier?.price_delta != null ? String(modifier.price_delta) : "0.00",
    ingredient_product_id: modifier?.ingredient_product_id ? String(modifier.ingredient_product_id) : "",
    quantity: modifier?.quantity != null ? String(modifier.quantity) : "1",
  };
}

// Build the create/update request body. Blank-named rows are dropped, a row
// with no ingredient drops the recipe fields, and the quantity is coerced to a
// positive integer (the API requires >= 1).
export function buildModifierGroupPayload(form) {
  const modifiers = (Array.isArray(form?.modifiers) ? form.modifiers : [])
    .filter((row) => String(row?.name ?? "").trim())
    .map((row) => {
      const ingredientId = row?.ingredient_product_id ? String(row.ingredient_product_id) : null;
      const parsed = Number.parseInt(row?.quantity, 10);
      const quantity = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
      return {
        name: String(row.name).trim(),
        price_delta: Number(row?.price_delta) || 0,
        ingredient_product_id: ingredientId,
        quantity,
      };
    });
  return {
    name: String(form?.name ?? "").trim(),
    min_select: 0,
    max_select: 1,
    is_required: false,
    modifiers,
  };
}

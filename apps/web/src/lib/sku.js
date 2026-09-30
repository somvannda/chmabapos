// Pure SKU helpers, kept free of React/JSX so they can be unit-tested with node:test.

const SKU_MAX_LENGTH = 80;

/**
 * Turn a product name into a stable, uppercase, dash-separated base SKU.
 * Diacritics are folded (Caffè -> CAFFE) and every run of non-alphanumerics
 * becomes a single dash. Returns "" when the name has no usable characters.
 */
export function slugifySku(value, maxLength = SKU_MAX_LENGTH) {
  const limit = Number.isFinite(maxLength) && maxLength > 0 ? Math.floor(maxLength) : SKU_MAX_LENGTH;
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, limit);
}

/**
 * Suggest a variant SKU by combining a product's base SKU with a variant name.
 * e.g. ("MACBOOK-PRO14", "Space Gray 32GB/512GB")
 *   => "MACBOOK-PRO14-SPACE-GRAY-32GB-512GB".
 * Either side may be empty; the result is "" only when both are unusable.
 */
export function suggestVariantSku(base, variantName, maxLength = SKU_MAX_LENGTH) {
  const limit = Number.isFinite(maxLength) && maxLength > 0 ? Math.floor(maxLength) : SKU_MAX_LENGTH;
  return [slugifySku(base, limit), slugifySku(variantName, limit)]
    .filter(Boolean)
    .join("-")
    .slice(0, limit)
    .replace(/-+$/g, "");
}

/** True when a product should have its base SKU locked in the form. */
export function isParentSkuLocked(hasVariants) {
  return Boolean(hasVariants);
}

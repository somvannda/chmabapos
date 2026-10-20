// Store QR poster helpers.
//
// A store QR is a picture a merchant prints and puts on the counter, so the
// saved image carries the shop's own name and logo plus a Chmaba credit line.
// The drawing itself happens on a canvas in the modal; the small pure pieces
// live here so the filename and the wording can be checked without a browser.

export const STORE_QR_POWERED_BY = "Powered by chmaba.com";
export const STORE_QR_SCAN_LINE = "Scan to order online";

// "Acme Coffee" -> "acme-coffee-qr.png". Names with no Latin characters (many
// Khmer shop names) fall back to a neutral filename instead of an empty one.
export function storeQrFileName(storeName) {
  const slug = String(storeName || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60)
    .replace(/-+$/g, "");
  return `${slug || "store"}-qr.png`;
}

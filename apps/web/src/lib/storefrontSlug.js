// Client-side half of the public storefront address rules.
//
// The API (`chmabapos_api/app/slugs.py`) is the authority: it validates again on
// save and answers 400 for a bad value or 409 for a taken one. This module only
// lets Settings show the same answer *before* the merchant saves - a suggestion
// from the name, an inline reason a value will be refused, and a live preview of
// the address - so nobody has to submit to find out.
//
// The reserved words are duplicated deliberately: they change rarely, the server
// still enforces them, and `storefrontSlug.test.js` cross-checks this list against
// the Python source so the two cannot drift silently.

export const SLUG_MIN_LENGTH = 3;
export const SLUG_MAX_LENGTH = 50;

// Shown in the Settings preview when VITE_STOREFRONT_URL is not configured yet,
// so a merchant still sees the real shape of the address they are choosing.
export const DEFAULT_STOREFRONT_HOST = "shops.chmaba.com";

// Mirrors RESERVED_COMPANY_SLUGS in app/slugs.py.
export const RESERVED_COMPANY_SLUGS = new Set([
  "admin",
  "api",
  "app",
  "assets",
  "display",
  "favicon.ico",
  "healthz",
  "login",
  "logout",
  "media",
  "order",
  "orders",
  "robots.txt",
  "signup",
  "sitemap.xml",
  "stores",
  "track",
]);

// Mirrors RESERVED_STORE_SLUGS in app/slugs.py.
export const RESERVED_STORE_SLUGS = new Set(["api", "assets", "healthz", "media", "order", "track"]);

const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/**
 * Best-effort address for a display name, or "" when the name has no Latin
 * letters (a Khmer name transliterates to nothing, and the merchant types the
 * Latin brand they already use instead).
 */
export function slugifyName(value) {
  const text = String(value || "")
    .normalize("NFKD")
    // NFKD splits an accent into letter + combining mark; dropping the marks
    // matches the server, which encodes to ASCII with "ignore".
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, SLUG_MAX_LENGTH)
    .replace(/-+$/g, "");
  return text.length >= SLUG_MIN_LENGTH ? text : "";
}

/** A merchant-safe reason the value cannot be used, or "" when it is fine. */
export function slugProblem(value, { company = false } = {}) {
  const slug = String(value || "").trim().toLowerCase();
  if (!slug) return "Enter a web address";
  if (slug.length < SLUG_MIN_LENGTH) return `Use at least ${SLUG_MIN_LENGTH} characters`;
  if (slug.length > SLUG_MAX_LENGTH) return `Use at most ${SLUG_MAX_LENGTH} characters`;
  if (!SLUG_RE.test(slug)) return "Use lowercase letters, numbers and single hyphens only";
  if ((company ? RESERVED_COMPANY_SLUGS : RESERVED_STORE_SLUGS).has(slug)) {
    return "That address is reserved — please choose another";
  }
  return "";
}

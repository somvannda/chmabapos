// Theme preference for the storefront.
//
// The storage key is deliberately the same one the POS app uses, so someone who picks
// dark in one place gets dark in the other. The choice is applied by putting `dark` on
// <html>, which is what the shared tokens.css keys its dark values off.
//
// There is no server round trip: a shopper is not necessarily signed in anywhere, and
// the preference is purely cosmetic - the opposite of the app, which also stores it on
// the user so it follows them between devices.

export const THEME_STORAGE_KEY = "chmaba-theme";

/** Only "dark" and "light" are valid; anything else means "no choice recorded". */
export function normalizeTheme(value) {
  return value === "dark" || value === "light" ? value : null;
}

export function readStoredTheme(getStorage) {
  try {
    return normalizeTheme(getStorage()?.getItem(THEME_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function writeStoredTheme(value, getStorage) {
  const theme = normalizeTheme(value);
  if (!theme) return;
  try {
    getStorage()?.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage can be blocked (private mode); the choice still applies to this page.
  }
}

/** What the document is actually showing right now, which is the source of truth. */
export function currentThemeFromDocument() {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function nextTheme(current) {
  return current === "dark" ? "light" : "dark";
}

export function applyTheme(theme, root = typeof document === "undefined" ? null : document.documentElement) {
  if (!root) return;
  root.classList.toggle("dark", (normalizeTheme(theme) || "light") === "dark");
}

/**
 * Runs as the first thing in <head>, before anything paints, so a shopper who chose dark
 * never sees a white flash. Kept as a string because it has to execute before hydration.
 */
export const THEME_BOOTSTRAP = `try{if(localStorage.getItem("${THEME_STORAGE_KEY}")==="dark"){document.documentElement.classList.add("dark")}}catch(e){}`;

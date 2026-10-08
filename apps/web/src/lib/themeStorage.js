// Theme preference helpers, kept free of React/JSX so they can be unit-tested
// with node:test.
//
// The chosen theme is mirrored in two places:
//   * localStorage["chmaba-theme"] — instant first paint and offline persistence.
//   * User.preferences.theme on the API — follows the user across devices.
//
// The access token lives in localStorage for "remember me" sessions and in
// sessionStorage otherwise (see App.jsx `storeToken`). Reading only localStorage
// skipped the API write for session-only sign-ins, so the server kept returning
// the previous theme on refresh and the toggle looked like it reverted.

export const THEME_STORAGE_KEY = "chmaba-theme";
export const ACCESS_TOKEN_KEY = "chmaba.access_token";

/** Only "dark" and "light" are valid themes; anything else is ignored. */
export function normalizeTheme(value) {
  return value === "dark" || value === "light" ? value : null;
}

/** Read the persisted theme, tolerating storage being unavailable. */
export function readStoredTheme(getStorage) {
  try {
    return normalizeTheme(getStorage()?.getItem(THEME_STORAGE_KEY));
  } catch {
    return null;
  }
}

/** Persist the theme, tolerating private mode / storage being disabled. */
export function writeStoredTheme(value, getStorage) {
  const theme = normalizeTheme(value);
  if (!theme) return;
  try {
    getStorage()?.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // The in-memory theme still applies for this session.
  }
}

/**
 * The access token can live in either storage depending on "remember me", so
 * check both. Returns "" when neither has one or storage is unavailable.
 */
export function readAccessToken(getLocal, getSession) {
  try {
    return getLocal()?.getItem(ACCESS_TOKEN_KEY) || getSession()?.getItem(ACCESS_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

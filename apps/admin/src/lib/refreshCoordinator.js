// Coordinates access-token refreshes so the rotating refresh cookie is never
// used by two refreshes at once.
//
// The API rotates the refresh token on every refresh and treats the *previous*
// token as stolen if it is replayed: replaying it revokes the whole session.
// When the short-lived access token ages out, a burst of in-flight requests all
// answer 401 together. If each one kicked off its own POST /auth/refresh they
// would race on the same cookie, and whichever request reached the server after
// the first rotation would present the pre-rotation token and sign the user out
// even though the session is still valid.
//
// This coordinator runs at most one refresh per tab (single-flight) and, when
// the Web Locks API is available, serializes refreshes across every tab that
// shares the same cookie jar.
//
// Kept free of React/JSX so it can be unit-tested with node:test.

export const REFRESH_LOCK_NAME = "chmaba:auth-refresh";

export function createRefreshCoordinator(refresh, { locks } = {}) {
  const lockManager =
    locks !== undefined
      ? locks
      : typeof navigator !== "undefined" && navigator.locks
        ? navigator.locks
        : null;

  let inFlight = null;

  return function refreshOnce() {
    if (inFlight) return inFlight;
    const run = lockManager
      ? () => lockManager.request(REFRESH_LOCK_NAME, () => refresh())
      : () => refresh();
    inFlight = Promise.resolve()
      .then(run)
      .finally(() => {
        inFlight = null;
      });
    return inFlight;
  };
}

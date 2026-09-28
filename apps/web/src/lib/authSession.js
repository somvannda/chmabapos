// Session-expiry helpers, kept free of React/JSX so they can be unit-tested
// with node:test. The API answers 401 when a bearer token is missing, expired
// or otherwise invalid. A 401 only means the user's session ended when the
// request actually carried a token; a failed sign-in has no token yet and must
// stay on the form instead of bouncing to "session expired".

export const AUTH_EXPIRED_EVENT = "chmaba:auth-expired";

export function isSessionExpired(status, token) {
  return status === 401 && Boolean(token);
}

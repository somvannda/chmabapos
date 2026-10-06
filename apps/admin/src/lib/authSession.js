// Session-expiry helpers for the admin panel. A 401 only means the sign-in
// ended when the request actually carried a token; a failed sign-in has no
// token yet and must stay on the form instead of bouncing to "session expired".

export const AUTH_EXPIRED_EVENT = "chmaba:auth-expired";

export function isSessionExpired(status, token) {
  return status === 401 && Boolean(token);
}

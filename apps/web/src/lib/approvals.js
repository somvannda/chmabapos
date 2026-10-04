// Shared approval helpers. Kept pure so they can be unit-tested with
// node:test. When an action is held for approval the API answers with HTTP 202
// and a `{ status: "pending_approval", approval_request }` body instead of the
// executed result. Callers must not treat that body as the real entity.
export function isPendingApproval(result) {
  return Boolean(result && typeof result === "object" && result.status === "pending_approval");
}

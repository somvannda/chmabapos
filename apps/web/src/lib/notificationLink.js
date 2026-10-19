// Resolve a notification's destination into an in-app view plus query, and read
// the billing "renew" intent a deep link carries.
//
// The API stores a path relative to the workspace root, e.g.
// "billing?renew=pro&cycle=monthly&pay=1". It is relative because the account
// segment of the URL is only known on the client, and bare (no scheme, no leading
// slash) so a notification can never act as an open redirect. Anything that could
// leave the app is rejected here rather than navigated to.

const VIEW_PATTERN = /^[a-z][a-z0-9-]*$/;
const PAY_CYCLES = ["monthly", "semi_annual", "annual"];

export function parseNotificationLink(link) {
  if (typeof link !== "string") return null;
  const trimmed = link.trim();
  if (!trimmed || trimmed.startsWith("/") || trimmed.includes("://") || trimmed.includes("\\")) return null;
  const question = trimmed.indexOf("?");
  const view = (question === -1 ? trimmed : trimmed.slice(0, question)).trim();
  if (!VIEW_PATTERN.test(view)) return null;
  const query = question === -1 ? "" : trimmed.slice(question + 1);
  return { view, params: new URLSearchParams(query) };
}

export function renewIntentFromParams(params) {
  if (!params) return null;
  const plan = String(params.get("renew") || "").trim();
  if (!plan || !VIEW_PATTERN.test(plan)) return null;
  const cycle = String(params.get("cycle") || "").trim();
  return {
    plan,
    cycle: PAY_CYCLES.includes(cycle) ? cycle : "monthly",
    pay: params.get("pay") === "1",
  };
}

export function renewIntentFromSearch(search) {
  if (typeof search !== "string" || !search) return null;
  return renewIntentFromParams(new URLSearchParams(search));
}

export { PAY_CYCLES };

const USER_PAGE_TO_VIEW = {
  dashboard: "dashboard",
  pos: "pos",
  orders: "orders",
  customers: "customers",
  catalog: "products",
  categories: "categories",
  products: "products",
  inventory: "inventory",
  purchasing: "purchasing",
  suppliers: "suppliers",
  reports: "reports",
  team: "team",
  activity: "activity",
  billing: "billing",
  settings: "settings",
};

const VIEW_TO_USER_PAGE = {
  dashboard: "dashboard",
  pos: "pos",
  orders: "orders",
  customers: "customers",
  products: "catalog",
  categories: "categories",
  inventory: "inventory",
  purchasing: "purchasing",
  suppliers: "suppliers",
  reports: "reports",
  team: "team",
  activity: "activity",
  billing: "billing",
  settings: "settings",
};

const ADMIN_PAGES = new Set(["overview", "users", "companies", "stores", "subscriptions", "plans", "audit", "payments"]);

const SETUP_STEPS = ["company", "plan", "ready"];

const TOP_LEVEL_PAGES = new Set(["login", "signup", "reset-password", "privacy", "terms", "contact", "refund-policy"]);

export function usernameFor(user) {
  if (!user) return "user";
  const emailName = user.email?.split("@")[0];
  const source = emailName || user.full_name || "user";
  return source.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "user";
}

export function userPath(user, view = "dashboard") {
  return `/${usernameFor(user)}/${VIEW_TO_USER_PAGE[view] || "dashboard"}`;
}

export function adminPath(page = "overview") {
  return `/admin/${ADMIN_PAGES.has(page) ? page : "overview"}`;
}

export function parseRoute(pathname = window.location.pathname) {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] === "admin") {
    return { kind: "not-found" };
  }
  if (parts.length === 0) {
    return { kind: "public" };
  }
  if (parts[0] === "app") {
    return { kind: "legacy-user", view: "dashboard" };
  }
  if (parts.length >= 2 && parts[1] === "setup") {
    return { kind: "setup", username: parts[0], step: SETUP_STEPS.includes(parts[2]) ? parts[2] : "company" };
  }
  if (parts.length === 1) {
    if (["privacy", "terms", "contact", "refund-policy"].includes(parts[0])) {
      return { kind: parts[0] };
    }
    if (TOP_LEVEL_PAGES.has(parts[0])) {
      return { kind: parts[0] };
    }
    return { kind: "not-found" };
  }
  if (USER_PAGE_TO_VIEW[parts[1]]) {
    return { kind: "user", username: parts[0], view: USER_PAGE_TO_VIEW[parts[1]] };
  }
  return { kind: "not-found" };
}

export function viewFromPath(pathname = window.location.pathname) {
  const route = parseRoute(pathname);
  return route.kind === "user" || route.kind === "legacy-user" ? route.view : "dashboard";
}

export function setupPathForUser(user, step = 1) {
  const index = Math.min(Math.max(Number(step) || 1, 1), SETUP_STEPS.length) - 1;
  return `/${usernameFor(user)}/setup/${SETUP_STEPS[index]}`;
}

export function setupStepFromPath(pathname = window.location.pathname) {
  const route = parseRoute(pathname);
  if (route.kind !== "setup") return 1;
  const index = SETUP_STEPS.indexOf(route.step);
  return index === -1 ? 1 : index + 1;
}

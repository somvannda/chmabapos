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
    return { kind: "admin", page: ADMIN_PAGES.has(parts[1]) ? parts[1] : "overview" };
  }
  if (parts[0] === "app") {
    return { kind: "legacy-user", view: "dashboard" };
  }
  if (parts.length >= 2 && parts[1] === "setup") {
    return { kind: "setup", username: parts[0] };
  }
  if (parts.length === 1 && ["privacy", "terms", "contact"].includes(parts[0])) {
    return { kind: parts[0] };
  }
  if (parts.length === 1 && !["login", "signup"].includes(parts[0])) {
    return { kind: "user", username: parts[0], view: "dashboard" };
  }
  if (parts.length >= 2 && USER_PAGE_TO_VIEW[parts[1]]) {
    return { kind: "user", username: parts[0], view: USER_PAGE_TO_VIEW[parts[1]] };
  }
  if (parts[0] === "login") return { kind: "login" };
  if (parts[0] === "signup") return { kind: "signup" };
  if (parts[0] === "reset-password") return { kind: "reset-password" };
  return { kind: "public" };
}

export function viewFromPath(pathname = window.location.pathname) {
  const route = parseRoute(pathname);
  return route.kind === "user" || route.kind === "legacy-user" ? route.view : "dashboard";
}

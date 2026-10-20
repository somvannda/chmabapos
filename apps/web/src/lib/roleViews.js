// Single source of truth for which workspace view each tenant role may open.
// Kept dependency-free (no React, no API client) so it can be unit-tested and
// reused by both the sidebar filter and the view-level guard in workspace.jsx.
export const VIEW_ROLES = {
  dashboard: ["owner", "manager", "inventory_manager", "cashier"],
  pos: ["owner", "manager", "cashier"],
  floor: ["owner", "manager", "cashier"],
  kitchen: ["owner", "manager", "cashier"],
  orders: ["owner", "manager", "cashier", "inventory_manager"],
  deliveries: ["owner", "manager", "cashier"],
  approvals: ["owner", "manager", "inventory_manager"],
  customers: ["owner", "manager", "cashier"],
  products: ["owner", "manager", "inventory_manager"],
  categories: ["owner", "manager", "inventory_manager"],
  inventory: ["owner", "manager", "inventory_manager"],
  purchasing: ["owner", "manager", "inventory_manager"],
  suppliers: ["owner", "manager", "inventory_manager"],
  reports: ["owner", "manager", "inventory_manager"],
  team: ["owner"],
  billing: ["owner"],
  settings: ["owner", "manager"],
  activity: ["owner", "manager"],
  help: ["owner", "manager", "inventory_manager", "cashier"],
  support: ["owner", "manager", "inventory_manager", "cashier"],
  inbox: ["owner", "manager", "cashier"],
};

export const canViewRole = (role, view) => (VIEW_ROLES[view] || []).includes(role);

// The permission a view needs. Only company custom roles consult this map;
// built-in roles above keep the fixed matrix, so adding a key here never
// changes what an existing owner/manager/inventory manager/cashier sees.
export const VIEW_PERMISSIONS = {
  dashboard: null,
  pos: "sales.create",
  floor: "dining.operate",
  kitchen: "dining.operate",
  orders: "orders.view",
  deliveries: "deliveries.manage",
  approvals: "approvals.decide",
  customers: "customers.manage",
  products: "catalog.view",
  categories: "catalog.view",
  inventory: "inventory.view",
  purchasing: "purchasing.view",
  suppliers: "purchasing.view",
  reports: "reports.view",
  team: "team.manage",
  billing: "billing.manage",
  settings: "settings.manage",
  activity: "audit.view",
  help: "support.use",
  support: "support.use",
  inbox: "orders.view",
};

const SYSTEM_ROLES = new Set(["owner", "manager", "inventory_manager", "cashier"]);

// Who may open a view. A built-in role keeps its fixed matrix. Any other role
// key is a company custom role: it reaches exactly the views its permissions
// unlock. Before this, a custom role matched no VIEW_ROLES entry at all and its
// member saw an empty workspace.
export function canView(role, view, permissions) {
  if (!role || SYSTEM_ROLES.has(role)) return canViewRole(role, view);
  const required = VIEW_PERMISSIONS[view];
  if (required === null) return true;
  return Boolean(required) && (permissions || []).includes(required);
}

// Settings sections a non-owner may still use: read-only summaries, or surfaces
// whose backend guard permits managers (catalog media, dining tables) or that
// manage the member's own account.
export const MANAGER_SETTINGS_SECTIONS = ["Media library", "Tables", "About this workspace", "Security"];

export const canEditSettingsSection = (role, section) =>
  role === "owner" || (role === "manager" && MANAGER_SETTINGS_SECTIONS.includes(section));

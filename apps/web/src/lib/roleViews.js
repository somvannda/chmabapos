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
  approvals: ["owner", "manager"],
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
};

export const canViewRole = (role, view) => (VIEW_ROLES[view] || []).includes(role);

// Settings sections a non-owner may still use: read-only summaries, or surfaces
// whose backend guard permits managers (catalog media, dining tables) or that
// manage the member's own account.
export const MANAGER_SETTINGS_SECTIONS = ["Media library", "Tables", "About this workspace", "Security"];

export const canEditSettingsSection = (role, section) =>
  role === "owner" || (role === "manager" && MANAGER_SETTINGS_SECTIONS.includes(section));

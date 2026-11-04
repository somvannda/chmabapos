// Effective plan feature keys exposed on the workspace payload
// (`workspace.plan_features`), mirroring `chmabapos_api/app/features.py`.
//
// These are paid capabilities, unlike the vertical "capability packs" in
// capabilityPacks.js. Pack checks deliberately fail open (an unknown pack list
// shows the field), but plan checks are strict: while the plan is loading or
// unknown we hide the control rather than show one that will 403. This mirrors
// the table_management nav gate added in #508.
//
// The list is for display and test parity only; the admin plan editor reads the
// canonical catalog from `GET /plans/features`, and the API decides what is
// allowed. Add a key here when it is added to `FEATURE_CATALOG`.
export const PLAN_FEATURES = [
  "inventory_management",
  "held_orders",
  "refunds",
  "khqr_payments",
  "multi_currency",
  "shift_management",
  "email_receipts",
  "purchasing",
  "advanced_reports",
  "roles_permissions",
  "table_management",
  "loyalty",
  "online_ordering",
  "delivery_dispatch",
  "combos",
  "serials_warranty",
  "batches_expiry",
  "consolidated_reports",
  "custom_roles",
  "priority_support",
];

export const hasPlanFeature = (planFeatures, key) =>
  Array.isArray(planFeatures) && planFeatures.includes(key);

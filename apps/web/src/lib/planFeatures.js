// Effective plan feature keys exposed on the workspace payload
// (`workspace.plan_features`), mirroring `chmabapos_api/app/features.py`.
//
// These are paid capabilities, unlike the vertical "capability packs" in
// capabilityPacks.js. Pack checks deliberately fail open (an unknown pack list
// shows the field), but plan checks are strict: while the plan is loading or
// unknown we hide the control rather than show one that will 403. This mirrors
// the table_management nav gate added in #508.
export const PLAN_FEATURES = [
  "inventory_management",
  "purchasing",
  "khqr_payments",
  "multi_currency",
  "advanced_reports",
  "loyalty",
  "barcode_scanning",
  "shift_management",
  "email_receipts",
  "held_orders",
  "refunds",
  "receipt_customization",
  "roles_permissions",
  "table_management",
  "priority_support",
];

export const hasPlanFeature = (planFeatures, key) =>
  Array.isArray(planFeatures) && planFeatures.includes(key);

// Which held tickets belong on the register.
//
// A public order (online or QR) creates a held ticket beside its Order, because
// that ticket is the kitchen's work item. A store without a dining room has no
// board to work those on, so the register's held drawer must not list rows nobody
// can act on. The sale itself still lives in Orders, and a store with the tables
// capability sees every ticket.
export function heldOrdersForRegister(heldOrders, hasTables) {
  const rows = Array.isArray(heldOrders) ? heldOrders : [];
  if (hasTables) return rows;
  // A row with no source predates the field and is a register-held ticket.
  return rows.filter((held) => (held?.source || "pos") === "pos");
}

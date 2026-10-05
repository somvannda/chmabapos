// Pure, dependency-free helpers for the workspace Overview dashboard.
//
// Kept free of React, the API client and any other runtime import so the
// derivations can be unit-tested with `node --test` and reused by the view.
// The view owns fetching; these functions only shape numbers and rows.

const pad = (value) => String(value).padStart(2, "0");

// Local calendar date -> "YYYY-MM-DD" (matches the API's date query params).
export function toISODate(value) {
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function fromISODate(iso) {
  const [year, month, day] = String(iso).split("-").map(Number);
  return new Date(year || 1970, (month || 1) - 1, day || 1);
}

// Presets shown in the Overview period selector. "today" is the default.
export function dashboardPeriods(now = new Date()) {
  const today = toISODate(now);
  const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6);
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  return [
    { id: "today", label: "Today", from: today, to: today },
    { id: "week", label: "Last 7 days", from: toISODate(weekStart), to: today },
    { id: "month", label: "This month", from: toISODate(monthStart), to: today },
  ];
}

// Rolling window of `days` calendar days ending today (inclusive).
export function trailingWindow(days = 14, now = new Date()) {
  const span = Math.max(1, Math.round(Number(days) || 1));
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (span - 1));
  return { from: toISODate(start), to: toISODate(now) };
}

// The equally sized window immediately before [from, to], used for comparisons.
export function previousPeriod(from, to) {
  const fromDate = fromISODate(from);
  const toDate = fromISODate(to);
  const span = Math.max(1, Math.round((toDate - fromDate) / 86400000) + 1);
  const prevTo = new Date(fromDate);
  prevTo.setDate(prevTo.getDate() - 1);
  const prevFrom = new Date(prevTo);
  prevFrom.setDate(prevFrom.getDate() - (span - 1));
  return { from: toISODate(prevFrom), to: toISODate(prevTo) };
}

export function timeGreeting(now = new Date()) {
  const hour = now.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function formatCount(value) {
  return (Number(value) || 0).toLocaleString();
}

// Percentage change with a UI-friendly direction. `percent` is null when there
// is no baseline (previous is zero); callers should fall back to the label.
export function percentChange(current, previous) {
  const now = Number(current) || 0;
  const before = Number(previous) || 0;
  if (!before) {
    if (!now) return { percent: 0, direction: "flat", label: "No change", hasBaseline: false };
    return { percent: null, direction: "up", label: "New", hasBaseline: false };
  }
  const delta = ((now - before) / before) * 100;
  return {
    percent: Math.abs(delta),
    direction: delta > 0 ? "up" : delta < 0 ? "down" : "flat",
    label: `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`,
    hasBaseline: true,
  };
}

// Inventory is loaded once for the whole workspace. Derive the owner-facing
// numbers the Overview needs without another request. A null cost price means
// the row is counted (so it can be flagged) but excluded from valuation.
export function inventorySnapshot(inventory = []) {
  let value = 0;
  let low = 0;
  let out = 0;
  let missingCost = 0;
  for (const item of inventory) {
    if (item?.status === "low") low += 1;
    else if (item?.status === "out") out += 1;
    const onHand = Number(item?.on_hand) || 0;
    if (item?.cost_price === null || item?.cost_price === undefined) {
      if (onHand > 0) missingCost += 1;
      continue;
    }
    value += onHand * Number(item.cost_price);
  }
  return { value, low, out, attention: low + out, missingCost };
}

function asRows(value) {
  return Array.isArray(value) ? value : [];
}

// Real best sellers from the report (ranked server-side by amount).
export function topProducts(report, limit = 5) {
  return asRows(report?.top_products)
    .slice(0, Math.max(0, limit))
    .map((row) => ({
      name: row?.name || "Unnamed",
      quantity: Number(row?.quantity) || 0,
      amount: Number(row?.amount) || 0,
    }));
}

// Normalise a report breakdown (payment methods / categories / combos) into
// labelled rows with a percentage share of the returned total.
export function salesMix(rows = [], limit = 5) {
  const clean = asRows(rows)
    .map((row) => ({
      label: String(row?.method || row?.category || row?.name || "Other"),
      amount: Number(row?.amount) || 0,
    }))
    .filter((row) => row.amount > 0)
    .sort((a, b) => b.amount - a.amount);
  const total = clean.reduce((sum, row) => sum + row.amount, 0);
  return {
    total,
    rows: clean.slice(0, Math.max(0, limit)).map((row) => ({
      ...row,
      percent: total ? (row.amount / total) * 100 : 0,
    })),
  };
}

export function recentTransactions(report, limit = 6) {
  return asRows(report?.transactions_detail)
    .slice(0, Math.max(0, limit))
    .map((row) => ({
      id: row?.id,
      orderNumber: row?.order_number || "—",
      customer: row?.customer_name || "Walk-in",
      total: Number(row?.total) || 0,
      currency: row?.currency_code,
      paymentMethod: row?.payment_method || "—",
      units: Number(row?.units_count) || 0,
      createdAt: row?.created_at,
    }));
}

export function runRate(report) {
  return {
    averageDailyNet: Number(report?.average_daily_net) || 0,
    projected30: Number(report?.projected_next_30_days) || 0,
    days: Math.max(1, Number(report?.days_in_period) || 1),
  };
}

function perDay(total, days) {
  const value = (Number(total) || 0) / Math.max(1, days);
  return (Math.round(value * 10) / 10).toLocaleString();
}

// The four headline KPIs, each compared against the previous window.
export function headlineMetrics(report, previous) {
  const current = report || {};
  const prior = previous || {};
  const days = Math.max(1, Number(current.days_in_period) || 1);
  const net = Number(current.net_after_refunds ?? current.net_sales ?? 0);
  const priorNet = Number(prior.net_after_refunds ?? prior.net_sales ?? 0);
  const transactions = Number(current.transactions) || 0;
  return [
    {
      id: "net",
      label: "Net sales",
      value: net,
      format: "currency",
      tone: "violet",
      detail: "After discounts & refunds",
      change: percentChange(net, priorNet),
    },
    {
      id: "transactions",
      label: "Transactions",
      value: transactions,
      format: "count",
      tone: "lime",
      detail: `${perDay(transactions, days)} avg/day`,
      change: percentChange(transactions, prior.transactions),
    },
    {
      id: "average",
      label: "Average order",
      value: Number(current.average_order) || 0,
      format: "currency",
      tone: "peach",
      detail: "Net per paid order",
      change: percentChange(current.average_order, prior.average_order),
    },
    {
      id: "items",
      label: "Items sold",
      value: Number(current.items_sold) || 0,
      format: "count",
      tone: "yellow",
      detail: "Units across paid orders",
      change: percentChange(current.items_sold, prior.items_sold),
    },
  ];
}

const CLOSED_ORDER_STATUSES = ["paid", "cancelled", "canceled", "refunded", "voided"];

// Actionable queue summarised for the Overview. Zero-count rows are dropped so
// the panel only shows work that actually needs the user.
export function needsAttention({ inventory = [], orders = [], heldOrders = [], unreadNotifications = 0 } = {}) {
  const stock = inventorySnapshot(inventory);
  const openOrders = asRows(orders).filter(
    (order) => order?.status && !CLOSED_ORDER_STATUSES.includes(order.status),
  ).length;
  const tickets = asRows(heldOrders).length;
  return [
    { id: "out", label: "Out of stock", count: stock.out, target: "inventory", tone: "red" },
    { id: "low", label: "Low stock", count: stock.low, target: "inventory", tone: "yellow" },
    { id: "open-orders", label: "Open or unpaid orders", count: openOrders, target: "orders", tone: "violet" },
    { id: "tickets", label: "Held tickets", count: tickets, target: "pos", tone: "blue" },
    { id: "alerts", label: "Unread alerts", count: Number(unreadNotifications) || 0, target: "notifications", tone: "neutral" },
  ].filter((row) => row.count > 0);
}

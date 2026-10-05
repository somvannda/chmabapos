import test from "node:test";
import assert from "node:assert/strict";

import {
  toISODate,
  dashboardPeriods,
  trailingWindow,
  previousPeriod,
  timeGreeting,
  percentChange,
  inventorySnapshot,
  topProducts,
  salesMix,
  recentTransactions,
  runRate,
  headlineMetrics,
  needsAttention,
} from "./dashboard.js";

test("toISODate formats a local date as YYYY-MM-DD", () => {
  assert.equal(toISODate(new Date(2026, 0, 3)), "2026-01-03");
  assert.equal(toISODate(new Date(2026, 11, 31)), "2026-12-31");
});

test("dashboardPeriods returns today, week and month windows", () => {
  const now = new Date(2026, 9, 5); // Mon 5 Oct 2026
  const periods = dashboardPeriods(now);
  assert.deepEqual(periods.map((p) => p.id), ["today", "week", "month"]);
  const [today, week, month] = periods;
  assert.deepEqual(today, { id: "today", label: "Today", from: "2026-10-05", to: "2026-10-05" });
  assert.equal(week.from, "2026-09-29"); // 7 days inclusive
  assert.equal(month.from, "2026-10-01");
  assert.equal(week.to, "2026-10-05");
});

test("trailingWindow spans the requested number of days ending today", () => {
  assert.deepEqual(trailingWindow(14, new Date(2026, 9, 5)), { from: "2026-09-22", to: "2026-10-05" });
  assert.deepEqual(trailingWindow(1, new Date(2026, 9, 5)), { from: "2026-10-05", to: "2026-10-05" });
});

test("previousPeriod matches the length of the current window", () => {
  assert.deepEqual(previousPeriod("2026-10-01", "2026-10-07"), { from: "2026-09-24", to: "2026-09-30" });
  assert.deepEqual(previousPeriod("2026-10-05", "2026-10-05"), { from: "2026-10-04", to: "2026-10-04" });
});

test("timeGreeting switches on the hour", () => {
  assert.equal(timeGreeting(new Date(2026, 9, 5, 8)), "Good morning");
  assert.equal(timeGreeting(new Date(2026, 9, 5, 14)), "Good afternoon");
  assert.equal(timeGreeting(new Date(2026, 9, 5, 21)), "Good evening");
});

test("percentChange reports direction, label and missing baseline", () => {
  assert.deepEqual(percentChange(150, 100), { percent: 50, direction: "up", label: "+50.0%", hasBaseline: true });
  const down = percentChange(50, 100);
  assert.equal(down.direction, "down");
  assert.equal(down.label, "-50.0%");
  const fresh = percentChange(20, 0);
  assert.equal(fresh.direction, "up");
  assert.equal(fresh.label, "New");
  assert.equal(fresh.hasBaseline, false);
  assert.equal(percentChange(0, 0).direction, "flat");
});

test("inventorySnapshot values stock and counts low/out separately", () => {
  const snapshot = inventorySnapshot([
    { status: "healthy", on_hand: 10, cost_price: 2 },
    { status: "low", on_hand: 2, cost_price: 3 },
    { status: "out", on_hand: 0, cost_price: 5 },
    { status: "healthy", on_hand: 4, cost_price: null }, // counts but cannot value
  ]);
  assert.equal(snapshot.value, 20 + 6);
  assert.equal(snapshot.low, 1);
  assert.equal(snapshot.out, 1);
  assert.equal(snapshot.attention, 2);
  assert.equal(snapshot.missingCost, 1);
});

test("topProducts limits and normalises report rows", () => {
  const report = { top_products: [{ name: "Latte", quantity: "4", amount: "12.00" }, { name: "Tea", quantity: 2, amount: 6 }] };
  assert.deepEqual(topProducts(report, 1), [{ name: "Latte", quantity: 4, amount: 12 }]);
  assert.deepEqual(topProducts(null), []);
});

test("salesMix sorts by amount, drops zero rows and computes share", () => {
  const mix = salesMix([
    { method: "Cash", amount: "25" },
    { method: "KHQR", amount: 75 },
    { method: "Other", amount: 0 },
  ]);
  assert.equal(mix.total, 100);
  assert.equal(mix.rows.length, 2);
  assert.equal(mix.rows[0].label, "KHQR");
  assert.equal(mix.rows[0].percent, 75);
});

test("recentTransactions normalises rows and supplies defaults", () => {
  const rows = recentTransactions({ transactions_detail: [{ id: "abc", order_number: "#12", total: "9.50", units_count: 3, payment_method: "cash" }] });
  assert.equal(rows[0].orderNumber, "#12");
  assert.equal(rows[0].customer, "Walk-in");
  assert.equal(rows[0].total, 9.5);
  assert.equal(rows[0].paymentMethod, "cash");
});

test("headlineMetrics compares net sales and items against the previous window", () => {
  const report = { net_after_refunds: "120", transactions: 12, average_order: 10, items_sold: 30, days_in_period: 2 };
  const previous = { net_after_refunds: "100", transactions: 10, average_order: 10, items_sold: 40 };
  const metrics = headlineMetrics(report, previous);
  assert.deepEqual(metrics.map((m) => m.id), ["net", "transactions", "average", "items"]);
  const net = metrics.find((m) => m.id === "net");
  assert.equal(net.value, 120);
  assert.equal(net.change.direction, "up");
  assert.equal(net.detail, "After discounts & refunds");
  assert.equal(metrics.find((m) => m.id === "transactions").detail, "6 avg/day");
  assert.equal(metrics.find((m) => m.id === "items").change.direction, "down");
});

test("needsAttention only surfaces non-zero work queues", () => {
  const rows = needsAttention({
    inventory: [{ status: "low" }, { status: "healthy" }, { status: "out" }],
    orders: [{ status: "paid" }, { status: "payment_pending" }, { status: "cancelled" }],
    heldOrders: [{ id: 1 }, { id: 2 }],
    unreadNotifications: 0,
  });
  const ids = rows.map((row) => row.id);
  assert.ok(ids.includes("low"));
  assert.ok(ids.includes("out"));
  assert.ok(ids.includes("open-orders"));
  assert.ok(ids.includes("tickets"));
  assert.ok(!ids.includes("alerts")); // zero count dropped
  assert.equal(rows.find((row) => row.id === "open-orders").count, 1);
  assert.equal(rows.find((row) => row.id === "tickets").count, 2);
});

test("runRate exposes the estimate fields with safe defaults", () => {
  assert.deepEqual(runRate({ average_daily_net: "5", projected_next_30_days: "150", days_in_period: 3 }), {
    averageDailyNet: 5,
    projected30: 150,
    days: 3,
  });
  assert.deepEqual(runRate(null), { averageDailyNet: 0, projected30: 0, days: 1 });
});

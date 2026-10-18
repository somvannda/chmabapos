import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real class of bug: a dashboard row whose target goes nowhere.
//
// There are two legitimate destinations, and the first version of this test only knew about
// one of them. A target may be a **view id the shell renders**, or it may be **intercepted by
// the dashboard's own click handler** - "notifications" opens the alerts panel, because a
// quick peek is a better experience than leaving the overview. Reading only the view ids
// declared a working row broken and "fixed" it into a worse one.
//
// Nothing in this suite renders, so the check is static: read the rows, read both places a
// target can be resolved, and require every target to resolve somewhere.
const read = (relative) => readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const dashboard = read("./dashboard.js");
const workspace = read("../features/workspace.jsx");
const team = read("../features/team.jsx");
const sales = read("../features/sales.jsx");

function viewIds(source) {
  const ids = new Set();
  // Declared nav items: { id: "orders", label: "Orders", icon: Receipt }
  for (const match of source.matchAll(/\{\s*id:\s*"([a-z-]+)"/g)) ids.add(match[1]);
  // The render map: orders: <LiveOrdersWithReceipt ... />
  for (const match of source.matchAll(/([a-z-]+):\s*<[A-Z]/g)) ids.add(match[1]);
  return ids;
}

function interceptedTargets(source) {
  // item.target === "notifications" ? onOpenNotifications?.() : onNavigate(item.target)
  return new Set([...source.matchAll(/item\.target === "([a-z-]+)"/g)].map((match) => match[1]));
}

function attentionTargets(source) {
  return [...source.matchAll(/target:\s*"([a-z-]+)"/g)].map((match) => match[1]);
}

test("every dashboard attention row resolves to a view or an intercepted panel", () => {
  const views = viewIds(workspace);
  assert.ok(views.size > 10, `expected to read the shell's view ids, saw ${views.size}`);

  const intercepted = interceptedTargets(team);
  assert.ok(intercepted.size >= 1, `expected to read the click handler's special cases, saw ${intercepted.size}`);

  const targets = attentionTargets(dashboard);
  assert.ok(targets.length >= 4, `expected to read the attention rows, saw ${targets.length}`);

  for (const target of targets) {
    assert.ok(
      views.has(target) || intercepted.has(target),
      `"${target}" is neither a view the shell renders nor a target the click handler intercepts, so the row goes nowhere`,
    );
  }
});

test("the alerts row keeps opening the alerts panel rather than navigating away", () => {
  assert.match(dashboard, /\{ id: "alerts",[^}]*target: "notifications"/, "the alerts row is the intercepted one");
  assert.match(team, /item\.target === "notifications"/, "and the handler must actually intercept it");
});

test("a row that names a filter hands it to the view it opens", () => {
  // The count on the row and the list the row opens have to be the same set, or the number is
  // a small lie: "3 awaiting payment" landing on every order the shop has ever taken.
  assert.match(dashboard, /\{ id: "online-unpaid",[^}]*filter: "payment_pending"/, "the row names the status it counts");
  assert.match(dashboard, /order\?\.status === "payment_pending"/, "and counts exactly that status, not 'not closed'");
  assert.match(team, /onNavigate\(item\.target, \{ filter: item\.filter \}\)/, "the row passes its filter through");
  assert.match(workspace, /navigateUser = \(nextView, options\) =>/, "the shell accepts a filter with the view");
  assert.match(workspace, /setOrdersFilter\(options\?\.filter \|\| "all"\)/, "and resets it when a target names none");
  assert.match(workspace, /initialFilter=\{ordersFilter\}/, "the orders view is opened with it");
  assert.match(sales, /useState\(initialFilter\)/, "and seeds its own filter from the prop");
});

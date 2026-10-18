import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real class of bug: a dashboard row whose target is not a view the shell can show.
//
// "Unread alerts" pointed at "notifications", which is not a view id - the inbox is "inbox" -
// so the row navigated to an id with nothing behind it and the panel came up blank. The row
// looked like it worked, which is the worst way for a link to fail.
//
// Nothing in this suite renders, so the check is static: read the rows, read the shell's view
// ids, and compare the two.
const read = (relative) => readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const dashboard = read("./dashboard.js");
const workspace = read("../features/workspace.jsx");

function viewIds(source) {
  const ids = new Set();
  // Declared nav items: { id: "orders", label: "Orders", icon: Receipt }
  for (const match of source.matchAll(/\{\s*id:\s*"([a-z-]+)"/g)) ids.add(match[1]);
  // The render map: orders: <LiveOrdersWithReceipt ... />
  for (const match of source.matchAll(/([a-z-]+):\s*<[A-Z]/g)) ids.add(match[1]);
  return ids;
}

function attentionTargets(source) {
  return [...source.matchAll(/target:\s*"([a-z-]+)"/g)].map((match) => match[1]);
}

test("every dashboard attention row points at a view the shell can show", () => {
  const views = viewIds(workspace);
  assert.ok(views.size > 10, `expected to read the shell's view ids, saw ${views.size}`);

  const targets = attentionTargets(dashboard);
  assert.ok(targets.length >= 4, `expected to read the attention rows, saw ${targets.length}`);

  for (const target of targets) {
    assert.ok(views.has(target), `"${target}" is not a view id the shell renders, so the row navigates nowhere`);
  }
});

test("the alerts row points at the inbox, which is the view that shows alerts", () => {
  assert.match(dashboard, /\{ id: "alerts",[^}]*target: "inbox"/, "the inbox is what renders notifications");
  assert.ok(!/target:\s*"notifications"/.test(dashboard), "there is no view called notifications");
});

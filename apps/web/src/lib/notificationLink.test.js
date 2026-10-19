import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseNotificationLink, renewIntentFromParams, renewIntentFromSearch } from "./notificationLink.js";

// A notification link is the only server-supplied value the bell navigates to,
// so the two things worth guarding are: it stays inside the app (no open
// redirect), and it carries the renewal intent the Billing page needs.

test("parses a billing renewal link into a view and intent", () => {
  const target = parseNotificationLink("billing?renew=pro&cycle=annual&pay=1");
  assert.equal(target.view, "billing");
  assert.deepEqual(renewIntentFromParams(target.params), { plan: "pro", cycle: "annual", pay: true });
});

test("a bare view is actionable without params", () => {
  const target = parseNotificationLink("billing");
  assert.equal(target.view, "billing");
  assert.equal(renewIntentFromParams(target.params), null);
});

test("refuses anything that could leave the app", () => {
  for (const unsafe of ["/billing", "//evil.com/billing", "https://evil.com", "javascript:alert(1)", "billing\\..\\x", "", "   "]) {
    assert.equal(parseNotificationLink(unsafe), null, `${JSON.stringify(unsafe)} must not become a destination`);
  }
});

test("an unknown cycle falls back to monthly rather than a broken key", () => {
  const intent = renewIntentFromParams(new URLSearchParams("renew=starter&cycle=weekly"));
  assert.equal(intent.cycle, "monthly");
});

test("pay is only true for an explicit 1, and a plain visit does not auto-pay", () => {
  assert.equal(renewIntentFromSearch("?renew=pro").pay, false);
  assert.equal(renewIntentFromSearch("?renew=pro&pay=1").pay, true);
  assert.equal(renewIntentFromSearch("?renew=pro&pay=0").pay, false);
  assert.equal(renewIntentFromSearch(""), null);
});

test("the shell wires the link into the bell and the renewal intent into Billing", () => {
  const workspace = readFileSync(new URL("../features/workspace.jsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  assert.match(workspace, /parseNotificationLink\(/, "the bell resolves the link");
  assert.match(workspace, /onOpen=\{openNotification\}/, "the dropdown is handed the opener");
  assert.match(workspace, /renewIntent=\{renewIntent\}/, "Billing receives the renewal intent");
  assert.match(workspace, /function NotificationsDropdown\(\{[^}]*onOpen/, "the dropdown accepts the opener");
  const team = readFileSync(new URL("../features/team.jsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");
  assert.match(team, /renewIntent/, "Billing consumes the renewal intent");
});

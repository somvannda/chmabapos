import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards the inbox store switcher. A user who can reach more than one store may
// switch between them from inside the inbox; the list itself is already scoped
// to their access by the API, so the switcher only renders what it is given. The
// switch must keep the merchant in the inbox rather than bouncing them to the
// dashboard, since that would lose their place in the conversation. Rendering is
// not available in this suite, so this static check pins the wiring down.
const read = (relative) =>
  readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");
const inbox = read("../features/inbox.jsx");
const workspace = read("../features/workspace.jsx");

test("inbox store switcher: the view accepts the accessible stores and a switch handler", () => {
  assert.match(
    inbox,
    /LiveInboxView\(\{[^}]*stores\s*=\s*\[\][^}]*onSwitchStore[^}]*\}\)/,
    "LiveInboxView must accept stores and onSwitchStore",
  );
});

test("inbox store switcher: only offered when the user can reach more than one store", () => {
  assert.match(
    inbox,
    /storeSwitcherOptions\(stores, unreadByStore\)/,
    "the options must come from the accessible stores and their unread counts",
  );
  assert.match(
    inbox,
    /\{storeOptions\.length > 1 \?/,
    "the switcher must be hidden for a single-store user",
  );
});

test("inbox store switcher: workspace passes the accessible stores and keeps the inbox open", () => {
  assert.match(
    workspace,
    /<LiveInboxView[^>]*stores=\{stores\}[^>]*onSwitchStore=\{\(id\) => switchStore\(id, \{ keepView: true \}\)\}/,
    "workspace must pass stores and a switch that stays in the inbox",
  );
  assert.match(
    workspace,
    /switchStore = async \(nextStoreId, options = \{\}\)/,
    "switchStore must accept a keepView option",
  );
  assert.match(
    workspace,
    /if \(!options\.keepView\) setActiveView\("dashboard"\)/,
    "switchStore must not always navigate away to the dashboard",
  );
});

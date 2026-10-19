import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards the inbox thread panel. The details about the open conversation live in
// a right-hand column, derived from the thread and the messages already loaded.
// Rendering is not available in this suite, so this static check pins the wiring
// down: the panel must only appear for an open thread, default to visible, offer
// a toggle, and read its contacts and orders through the tested helpers.
const inbox = readFileSync(new URL("../features/inbox.jsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");

test("inbox thread panel: only renders for an open thread, and defaults to open", () => {
  assert.match(inbox, /\{active && detailsOpen \? \(/, "the panel must be gated on an open thread and the toggle");
  assert.match(inbox, /const \[detailsOpen, setDetailsOpen\] = useState\(true\)/, "the panel must default to open");
});

test("inbox thread panel: has a header toggle", () => {
  assert.match(inbox, /aria-label="Toggle thread details"/, "the panel needs a labelled toggle");
  assert.match(inbox, /setDetailsOpen\(\(value\) => !value\)/, "the toggle must flip the panel");
});

test("inbox thread panel: derives contacts and orders from the thread", () => {
  assert.match(inbox, /contactRows\(active\)/, "contacts must come from the open thread");
  assert.match(inbox, /const sharedOrders = active\?\.orders \|\| \[\]/, "orders must come from the thread's server-side list");
  assert.match(inbox, /Orders in this chat/, "the panel must show the shared orders");
});

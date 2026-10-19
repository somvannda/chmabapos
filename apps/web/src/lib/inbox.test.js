import test from "node:test";
import assert from "node:assert/strict";

import {
  contactRows,
  conversationLabel,
  formatBytes,
  formatDuration,
  highestSeq,
  kindForFile,
  linkify,
  mergeMessages,
  parseSseChunk,
  playChatChime,
  relativeTime,
  storeSwitcherOptions,
  unreadTotal,
} from "./inbox.js";

test("mergeMessages: dedupes by id and orders by seq", () => {
  const first = [{ id: "b", seq: 2 }, { id: "a", seq: 1 }];
  const merged = mergeMessages(first, [{ id: "a", seq: 1, body: "updated" }, { id: "c", seq: 3 }]);
  assert.deepEqual(merged.map((message) => message.id), ["a", "b", "c"]);
  assert.equal(merged[0].body, "updated");
});

test("highestSeq: an empty thread has no cursor", () => {
  assert.equal(highestSeq([]), 0);
  assert.equal(highestSeq(undefined), 0);
  assert.equal(highestSeq([{ seq: 4 }, { seq: 9 }, { seq: 7 }]), 9);
});

test("parseSseChunk: several frames in one chunk", () => {
  const { events, rest } = parseSseChunk("event: message\nid: 3\ndata: {\"x\":1}\n\nevent: heartbeat\ndata: {}\n\n");
  assert.equal(rest, "");
  assert.equal(events.length, 2);
  assert.equal(events[0].event, "message");
  assert.equal(events[0].id, "3");
  assert.deepEqual(JSON.parse(events[0].data), { x: 1 });
});

test("parseSseChunk: a partial frame survives to the next read", () => {
  const first = parseSseChunk("event: message\ndata: {\"x\":");
  assert.deepEqual(first.events, []);
  const second = parseSseChunk(first.rest + "1}\n\n");
  assert.equal(second.events.length, 1);
  assert.deepEqual(JSON.parse(second.events[0].data), { x: 1 });
});

test("conversationLabel: prefers the store's own label, then the name the customer gave, then the account", () => {
  assert.equal(conversationLabel({ seller_label: "Table 4", guest_name: "Dara" }), "Table 4");
  assert.equal(conversationLabel({ guest_name: "Dara" }), "Dara");
  assert.equal(conversationLabel({ guest_name: null, shopper_name: "me@example.com" }), "me@example.com");
  assert.equal(conversationLabel({}), "Guest");
  assert.equal(conversationLabel(null), "Customer");
});

test("unreadTotal: sums only what needs attention", () => {
  assert.equal(unreadTotal([{ unread_count: 2 }, { unread_count: 0 }, {}]), 2);
  assert.equal(unreadTotal([]), 0);
  assert.equal(unreadTotal(undefined), 0);
});

test("storeSwitcherOptions: names carry the unread count only when a store is waiting", () => {
  const stores = [{ id: "a", name: "Main" }, { id: "b", name: "Airport" }, { id: "c", name: "Depot" }];
  assert.deepEqual(storeSwitcherOptions(stores, { a: 3, b: 0 }), [
    { value: "a", label: "Main (3)" },
    { value: "b", label: "Airport" },
    { value: "c", label: "Depot" },
  ]);
});

test("storeSwitcherOptions: tolerates no stores, no counts, and a nameless store", () => {
  assert.deepEqual(storeSwitcherOptions(undefined, undefined), []);
  assert.deepEqual(storeSwitcherOptions([{ id: "a", name: "Main" }]), [{ value: "a", label: "Main" }]);
  assert.deepEqual(storeSwitcherOptions([{ id: "a" }], { a: "nonsense" }), [{ value: "a", label: "Store" }]);
});

test("contactRows: only lists the details the customer actually shared", () => {
  const rows = contactRows({ contact_email: "dara@example.com", contact_phone: "+855 12 345 678" });
  assert.deepEqual(rows, [
    { label: "Email", value: "dara@example.com", href: "mailto:dara@example.com" },
    { label: "Phone", value: "+855 12 345 678", href: "tel:+85512345678" },
  ]);
  assert.deepEqual(contactRows({ contact_email: null, contact_phone: null }), []);
  assert.deepEqual(contactRows(null), []);
});

test("formatDuration and formatBytes stay readable", () => {
  assert.equal(formatDuration(7000), "0:07");
  assert.equal(formatDuration(65000), "1:05");
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(2048), "2 KB");
});

test("kindForFile: images are images, everything else is a document", () => {
  assert.equal(kindForFile({ type: "image/png" }), "image");
  assert.equal(kindForFile({ type: "application/pdf" }), "file");
  assert.equal(kindForFile({}), "file");
});

test("relativeTime: short spans read in minutes and hours", () => {
  const now = Date.parse("2026-10-17T12:00:00Z");
  assert.equal(relativeTime("2026-10-17T11:59:30Z", now), "now");
  assert.equal(relativeTime("2026-10-17T11:30:00Z", now), "30m");
  assert.equal(relativeTime("2026-10-17T09:00:00Z", now), "3h");
  assert.equal(relativeTime("nonsense", now), "");
  assert.equal(relativeTime(null, now), "");
});

test("linkify: a URL becomes a link, surrounding words stay text", () => {
  assert.deepEqual(linkify("see https://maps.example.com/x?q=1 for the map"), [
    { type: "text", value: "see " },
    { type: "link", value: "https://maps.example.com/x?q=1", href: "https://maps.example.com/x?q=1" },
    { type: "text", value: " for the map" },
  ]);
});

test("linkify: a bare www host gets an https scheme and a phone number a tel link", () => {
  assert.deepEqual(linkify("www.chmaba.com"), [
    { type: "link", value: "www.chmaba.com", href: "https://www.chmaba.com" },
  ]);
  const call = linkify("call +855 12 345 678 now");
  assert.equal(call[0].value, "call ");
  assert.deepEqual(call[1], { type: "link", value: "+855 12 345 678", href: "tel:+85512345678" });
  assert.equal(call.at(-1).value, " now");
});

test("linkify: a sentence-ending dot is not part of the link; short numbers stay text", () => {
  assert.equal(linkify("go to https://x.example.com.").find((segment) => segment.type === "link").href, "https://x.example.com");
  assert.deepEqual(linkify("order 1234 ready"), [{ type: "text", value: "order 1234 ready" }]);
  assert.deepEqual(linkify(""), []);
});

test("playChatChime: without a browser it declines instead of throwing", () => {
  assert.equal(playChatChime(), false);
});

import test from "node:test";
import assert from "node:assert/strict";

import {
  conversationLabel,
  formatBytes,
  formatDuration,
  highestSeq,
  kindForFile,
  mergeMessages,
  parseSseChunk,
  relativeTime,
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

test("conversationLabel: prefers the name the customer gave, then the account", () => {
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

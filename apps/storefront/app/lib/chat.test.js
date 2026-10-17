import test from "node:test";
import assert from "node:assert/strict";

import {
  chatKey,
  chatClock,
  formatBytes,
  formatDuration,
  kindForFile,
  parseSseChunk,
  readChatRecord,
} from "./chat.js";

test("chatKey: scoped per store, so one shop never resumes another's thread", () => {
  assert.notEqual(chatKey("acme", "main"), chatKey("acme", "second"));
  assert.match(chatKey("acme", "main"), /acme\/main$/);
});

test("readChatRecord: with no browser there is simply no stored thread", () => {
  // Node has no window, which is exactly the server-render path.
  assert.equal(readChatRecord("acme", "main"), null);
});

test("parseSseChunk: one chunk can carry several frames", () => {
  const buffer = "event: message\nid: 4\ndata: {\"a\":1}\n\nevent: heartbeat\ndata: {\"seq\":4}\n\n";
  const { events, rest } = parseSseChunk(buffer);
  assert.equal(rest, "");
  assert.equal(events.length, 2);
  assert.equal(events[0].event, "message");
  assert.equal(events[0].id, "4");
  assert.deepEqual(JSON.parse(events[0].data), { a: 1 });
  assert.equal(events[1].event, "heartbeat");
});

test("parseSseChunk: a half frame is kept for the next read, not dropped", () => {
  const first = parseSseChunk("event: message\ndata: {\"a\":");
  assert.deepEqual(first.events, []);
  assert.equal(first.rest, "event: message\ndata: {\"a\":");

  const second = parseSseChunk(first.rest + "1}\n\n");
  assert.equal(second.events.length, 1);
  assert.deepEqual(JSON.parse(second.events[0].data), { a: 1 });
  assert.equal(second.rest, "");
});

test("parseSseChunk: comment-only and blank frames produce nothing", () => {
  assert.deepEqual(parseSseChunk(": connected\n\n").events, []);
  assert.deepEqual(parseSseChunk("\n\n").events, []);
});

test("formatDuration: seconds and minutes read as a player expects", () => {
  assert.equal(formatDuration(0), "0:00");
  assert.equal(formatDuration(7_000), "0:07");
  assert.equal(formatDuration(65_000), "1:05");
  assert.equal(formatDuration(undefined), "0:00");
});

test("formatBytes: scales past a kilobyte without lying about precision", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(2048), "2 KB");
  assert.equal(formatBytes(3 * 1024 * 1024), "3.0 MB");
});

test("kindForFile: images are images, everything else is a document", () => {
  assert.equal(kindForFile({ type: "image/png" }), "image");
  assert.equal(kindForFile({ type: "application/pdf" }), "file");
  assert.equal(kindForFile({}), "file");
});

test("chatClock: an invalid timestamp is blank rather than 'Invalid Date'", () => {
  assert.equal(chatClock("nonsense"), "");
  assert.equal(chatClock(null), "");
  assert.notEqual(chatClock("2026-10-17T10:00:00Z"), "");
});

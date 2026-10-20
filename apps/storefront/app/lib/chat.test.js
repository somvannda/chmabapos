import test from "node:test";
import assert from "node:assert/strict";

import {
  chatKey,
  chatClock,
  formatBytes,
  formatDuration,
  kindForFile,
  linkify,
  openStoreChat,
  parseSseChunk,
  readChatRecord,
  retryMediaUrl,
} from "./chat.js";

test("chatKey: scoped per store, so one shop never resumes another's thread", () => {
  assert.notEqual(chatKey("acme", "main"), chatKey("acme", "second"));
  assert.match(chatKey("acme", "main"), /acme\/main$/);
});

test("readChatRecord: with no browser there is simply no stored thread", () => {
  // Node has no window, which is exactly the server-render path.
  assert.equal(readChatRecord("acme", "main"), null);
});

test("openStoreChat: with no browser it is a no-op rather than a crash", () => {
  // The store page's inline button imports this; it must survive SSR.
  assert.equal(openStoreChat(), undefined);
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

test("kindForFile: images, video and documents are told apart", () => {
  assert.equal(kindForFile({ type: "image/png" }), "image");
  assert.equal(kindForFile({ type: "video/mp4" }), "video");
  assert.equal(kindForFile({ type: "application/pdf" }), "file");
  assert.equal(kindForFile({}), "file");
});

test("chatClock: an invalid timestamp is blank rather than 'Invalid Date'", () => {
  assert.equal(chatClock("nonsense"), "");
  assert.equal(chatClock(null), "");
  assert.notEqual(chatClock("2026-10-17T10:00:00Z"), "");
});

test("linkify: a URL becomes a link, the words around it stay text", () => {
  const segments = linkify("see https://maps.example.com/x?q=1 for the map");
  assert.deepEqual(segments, [
    { type: "text", value: "see " },
    { type: "link", value: "https://maps.example.com/x?q=1", href: "https://maps.example.com/x?q=1" },
    { type: "text", value: " for the map" },
  ]);
});

test("linkify: a bare www host gets an https scheme", () => {
  assert.deepEqual(linkify("www.chmaba.com"), [
    { type: "link", value: "www.chmaba.com", href: "https://www.chmaba.com" },
  ]);
});

test("linkify: a phone number becomes a tel link, punctuation excluded", () => {
  const segments = linkify("call +855 12 345 678.");
  assert.equal(segments[0].type, "text");
  assert.deepEqual(segments[1], { type: "link", value: "+855 12 345 678", href: "tel:+85512345678" });
  assert.deepEqual(segments[2], { type: "text", value: "." });
});

test("linkify: a sentence-ending dot is not part of the link", () => {
  const segments = linkify("go to https://x.example.com.");
  assert.equal(segments.at(-1).type, "text");
  assert.equal(segments.find((segment) => segment.type === "link").href, "https://x.example.com");
});

test("linkify: a short run of digits is not a phone number", () => {
  assert.deepEqual(linkify("order 1234 ready"), [{ type: "text", value: "order 1234 ready" }]);
  assert.deepEqual(linkify(""), []);
});

test("linkify: a bare domain becomes a link with an https scheme", () => {
  assert.deepEqual(linkify("visit chmaba.com today"), [
    { type: "text", value: "visit " },
    { type: "link", value: "chmaba.com", href: "https://chmaba.com" },
    { type: "text", value: " today" },
  ]);
  assert.deepEqual(linkify("chmaba.com/order/12"), [
    { type: "link", value: "chmaba.com/order/12", href: "https://chmaba.com/order/12" },
  ]);
});

test("linkify: a file name, a version number and an email are not links", () => {
  assert.deepEqual(linkify("report.pdf 1.2.3 me@chmaba.com"), [
    { type: "text", value: "report.pdf 1.2.3 me@chmaba.com" },
  ]);
});

test("retryMediaUrl: the first request is the stored URL, later ones are cache-busted", () => {
  assert.equal(retryMediaUrl("/media/a.png", 0), "/media/a.png");
  assert.equal(retryMediaUrl("/media/a.png", 2), "/media/a.png?retry=2");
});

test("retryMediaUrl: an existing query string is extended, not duplicated", () => {
  assert.equal(retryMediaUrl("/media/a.png?v=1", 1), "/media/a.png?v=1&retry=1");
});

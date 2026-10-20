import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Picking several files at once sends them one after another, each as its own
// message (the chat model carries one attachment per message). Rendering is not
// available in this suite, so this static check pins the wiring down: the picker
// accepts several files, the cap is 10, and the composer hands them to the
// multi-file sender.
const inbox = readFileSync(new URL("../features/inbox.jsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");

test("inbox: the file picker accepts several files, capped at 10", () => {
  assert.match(inbox, /const MAX_FILES_PER_SEND = 10;/, "the cap must be 10");
  assert.match(inbox, /type="file"[\s\S]*?multiple/, "the file input must allow multiple files");
  assert.match(inbox, /onSendFiles\?\.\(/, "picked files must go to the multi-file sender");
});

test("inbox: the size check allows a 25 MB video and 5 MB otherwise", () => {
  assert.match(inbox, /const MAX_VIDEO_BYTES = 25_000_000;/);
  assert.match(inbox, /kind === "video" \? MAX_VIDEO_BYTES : MAX_ATTACHMENT_BYTES/);
});

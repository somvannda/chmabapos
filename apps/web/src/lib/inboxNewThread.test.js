import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// A brand-new thread reaches the inbox only over the live stream (nothing lists it
// yet). The handler must notice a conversation it does not hold and reload the
// list, or the first message of a new chat stays invisible until the next poll -
// which read to the user as "you have to refresh". Rendering is not available in
// this suite, so this static check pins the wiring down.
const inbox = readFileSync(new URL("../features/inbox.jsx", import.meta.url), "utf8").replace(/\r\n/g, "\n");

test("inbox stream: a message for a thread not in the list reloads it", () => {
  assert.match(
    inbox,
    /conversationsRef\.current\.some\(\(item\) => item\.id === conversationId\)/,
    "the handler must check whether the thread is already listed",
  );
  assert.match(
    inbox,
    /loadList\(\{ silent: true \}\)/,
    "an unknown thread must trigger a list reload so it appears on arrival",
  );
});

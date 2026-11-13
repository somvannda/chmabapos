import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real regression: when the escalation flow was replaced by the
// contact-support form, SupportChat kept a stale `setEscalation("")` call in
// send(). That threw "setEscalation is not defined" on every submit — before the
// user's turn was appended — so the assistant silently stopped replying while
// still accepting typing. `vite build` cannot see an undefined reference, and
// apiSurface.test.js only covers api.* names, so this static check does:
// every setXxx() call in the component must come from a useState pair or a
// local declaration.
const chat = readFileSync(
  new URL("../components/SupportChat.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");

const supportPage = readFileSync(
  new URL("../features/supportChat.jsx", import.meta.url),
  "utf8",
).replace(/\r\n/g, "\n");

const declaredSetters = new Set([
  ...[...chat.matchAll(/const\s*\[[^\]]*?,\s*([A-Za-z0-9_]+)\s*\]\s*=\s*useState/g)].map((match) => match[1]),
  ...[...chat.matchAll(/(?:const|let|var)\s+(set[A-Za-z0-9_]*)\s*=/g)].map((match) => match[1]),
]);

test("support chat: every setXxx() call is declared in the component", () => {
  // Bare calls only: `sessionStorage.setItem(...)` is a method, not a state setter.
  const called = [...new Set([...chat.matchAll(/(?<![.\w$])(set[A-Z][A-Za-z0-9_]*)\s*\(/g)].map((match) => match[1]))];
  assert.ok(called.length > 0, "expected SupportChat to call its state setters");
  for (const name of called) {
    assert.ok(declaredSetters.has(name), `SupportChat calls ${name}() but never declares it`);
  }
});

test("support chat: send() clears the composer before it awaits", () => {
  assert.match(chat, /setInput\(""\);/, "send() must clear the composer");
});

// The floating panel and the Support page must keep using one thread. If this
// ever drifts back to the old `support_conversations` store, the ops inbox stops
// seeing questions merchants ask from the launcher.
test("support chat: resumes the caller's own live thread", () => {
  assert.match(chat, /supportChatConversations\([^)]*\{[^}]*mine:\s*1/, "the panel must ask for the caller's own thread");
  assert.match(chat, /support\/chat\/conversations\/\$\{threadId\}\/ask/, "answers must stream into the live thread");
  assert.match(chat, /supportChatHandoff\(/, "Talk to a human must hand off the same thread");
  assert.doesNotMatch(chat, /api\.supportChat\(/, "the panel must not use the old one-shot assistant endpoint");
});

// The hand-off must be honest about availability and ask the merchant to try
// self-help first. This pins the two-step confirm plus the offline wording.
test("support page: composer starts at three lines and grows", () => {
  assert.match(supportPage, /min-h-\[72px\][^"]*max-h-\[200px\]/, "the composer must show three lines before scrolling");
  assert.match(supportPage, /scrollHeight/, "the composer must grow with its content");
});

test("support chat: asks for confirmation and reports availability", () => {
  assert.match(chat, /supportChatAvailability\(/, "the panel must load live availability");
  assert.match(chat, /Still need a human\?/, "the confirm step must be visible");
  assert.match(chat, /result\.online/, "the hand-off result must distinguish online from offline");
  assert.match(chat, /offline right now/, "the panel must tell the merchant when support is offline");
});

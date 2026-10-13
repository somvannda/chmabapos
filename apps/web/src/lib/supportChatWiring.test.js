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

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards the phone layout of the chat inbox. The screen used to be a fixed
// two-column desk layout: on a phone the composer fell below the browser chrome
// and the customer panel was only reachable above 1280px. Rendering is not
// available in this suite, so the wiring is pinned down statically.
const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8").replace(/\r\n/g, "\n");
const inbox = read("../features/inbox.jsx");
const workspace = read("../features/workspace.jsx");
const styles = read("../styles.css");
const html = read("../../index.html");

test("inbox on a phone: the view fills the app shell instead of subtracting a guessed header", () => {
  assert.doesNotMatch(inbox, /h-\[calc\(100vh-74px\)\]/, "browser chrome must not push the composer off screen");
  assert.match(inbox, /className="flex h-full min-h-0 flex-col overflow-hidden md:min-h-\[560px\] md:flex-row"/, "the inbox must fill the shell and only keep the minimum on desktop");
  assert.match(workspace, /className="app-viewport flex overflow-hidden/, "the workspace shell must use the dynamic viewport height");
  assert.match(styles, /\.app-viewport \{\n  height: 100vh;\n  height: 100dvh;\n\}/, "dvh must track the visible viewport with a vh fallback");
  assert.match(html, /interactive-widget=resizes-content/, "the keyboard should resize the page on supported mobiles");
});

test("inbox on a phone: the customer panel opens from the thread header", () => {
  assert.match(inbox, /onClick=\{\(\) => setMobileDetailsOpen\(true\)\}/, "the header needs a mobile details trigger");
  assert.match(inbox, /aria-label="Customer details"/, "the trigger must be labelled for assistive tech");
  assert.match(inbox, /role="dialog"/, "the mobile panel is a slide-over dialog");
  assert.match(inbox, /aria-label="Close thread details"/, "the slide-over needs its own close button");
  assert.match(inbox, /onClick=\{\(\) => setMobileDetailsOpen\(false\)\}/, "the slide-over must be dismissible");
  assert.match(inbox, /<ThreadDetailsBody/, "the phone and desktop panels share one body");
});

test("inbox on a phone: the composer keeps the reply box and send button on the first row", () => {
  assert.match(inbox, /className="order-1 max-h-28 min-h-9 min-w-0 flex-1 resize-none[^"]*text-base[^"]*md:order-none/, "the reply box must come first and stay at 16px on phones");
  assert.match(inbox, /className="order-2 flex h-9 w-9 shrink-0/, "the send button must sit beside the reply box");
  assert.match(inbox, /className="order-3 flex w-full items-center gap-0.5 overflow-x-auto[^"]*md:order-none/, "the tool buttons must wrap onto their own scrollable row");
  assert.match(inbox, /enterKeyHint="send"/, "the phone keyboard should offer Send");
});

test("inbox on a phone: the thread column is height-constrained so it scrolls", () => {
  assert.match(inbox, /<section className=\{`min-h-0 min-w-0 flex-1 flex-col overflow-hidden/, "the thread column must not grow with its messages");
  assert.match(inbox, /className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain/, "the message list must be the part that scrolls");
  assert.match(inbox, /className="shrink-0 border-t border-\[#e9e9ef\] bg-white/, "the composer must stay pinned to the bottom");
});

test("inbox on a phone: a thread opens at the newest message", () => {
  assert.match(inbox, /const messageListRef = useRef\(null\)/, "the message list needs a ref to follow the conversation");
  assert.match(inbox, /list\.scrollTop = list\.scrollHeight/, "opening or receiving a message must land on the newest reply");
  assert.match(inbox, /stickToBottomRef\.current = list\.scrollHeight - list\.scrollTop - list\.clientHeight < 80/, "new messages must not yank a reader who scrolled up");
});

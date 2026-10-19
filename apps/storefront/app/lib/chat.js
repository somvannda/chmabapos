// Storefront chat helpers: the browser's memory of a thread, the server-sent
// event parser, and the small formatters the thread view needs.
//
// Everything here is deliberately framework-free so it can be unit-tested with
// `node --test` alongside the other pure modules.

const STORAGE_PREFIX = "chmaba.chat.";

// The emoji worth putting one tap away. The server accepts any single emoji, so
// this is a convenience row, not a whitelist.
export const CHAT_EMOJIS = ["👍", "❤️", "😄", "😮", "😢", "🙏"];

export function chatKey(companySlug, storeSlug) {
  return `${STORAGE_PREFIX}${companySlug}/${storeSlug}`;
}

export function readChatRecord(companySlug, storeSlug) {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(chatKey(companySlug, storeSlug));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || !parsed.visitor_token) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeChatRecord(companySlug, storeSlug, record) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(chatKey(companySlug, storeSlug), JSON.stringify(record));
  } catch {
    // A browser with storage disabled still chats; it just forgets on reload.
  }
}

export function clearChatRecord(companySlug, storeSlug) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(chatKey(companySlug, storeSlug));
  } catch {
    // Nothing to do.
  }
}

// The store page offers a second chat entry point in the contact row, which has
// no access to the widget's state. Rather than lift that state into the route,
// the inline button announces "open" on the window and the mounted widget
// listens. A no-op on the server, so it is safe to import anywhere.
export const CHAT_OPEN_EVENT = "chmaba:open-store-chat";

export function openStoreChat() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(CHAT_OPEN_EVENT));
}

// A server-sent event frame ends at a blank line. One network chunk can carry
// several frames, or half of one, so the caller keeps the remainder and feeds it
// back on the next read.
export function parseSseChunk(buffer) {
  const events = [];
  let rest = buffer;
  let boundary = rest.indexOf("\n\n");
  while (boundary !== -1) {
    const frame = rest.slice(0, boundary);
    rest = rest.slice(boundary + 2);
    const parsed = parseSseFrame(frame);
    if (parsed) events.push(parsed);
    boundary = rest.indexOf("\n\n");
  }
  return { events, rest };
}

function parseSseFrame(frame) {
  const event = { event: "message", data: "", id: null };
  let sawField = false;
  for (const rawLine of frame.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") { event.event = value; sawField = true; }
    else if (field === "data") { event.data += (event.data ? "\n" : "") + value; sawField = true; }
    else if (field === "id") { event.id = value; sawField = true; }
  }
  return sawField ? event : null;
}

// Read an SSE endpoint with fetch (so auth headers survive) and hand each
// message event to the caller. Resolves when the server closes the stream, which
// the caller treats as a prompt to reconnect with its cursor.
export async function streamChatEvents({ url, headers, signal, onMessage, onReconnect }) {
  const response = await fetch(url, { headers, signal });
  if (!response.ok || !response.body) {
    throw new Response("Chat stream unavailable", { status: response.status || 502 });
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseChunk(buffer);
    buffer = rest;
    for (const event of events) {
      if (event.event === "message" && event.data) {
        try {
          onMessage?.(JSON.parse(event.data));
        } catch {
          // A malformed frame is dropped rather than killing the stream.
        }
      } else if (event.event === "reconnect") {
        onReconnect?.();
      }
    }
  }
}

// "0:07" - voice notes are short, so minutes are enough.
export function formatDuration(milliseconds) {
  const total = Math.max(0, Math.round((Number(milliseconds) || 0) / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

// The API's kind for a picked file. Voice notes are recorded in-app, so a file
// picker only ever yields an image or a document.
export function kindForFile(file) {
  const type = (file?.type || "").toLowerCase();
  if (type.startsWith("image/")) return "image";
  if (type.startsWith("video/")) return "video";
  return "file";
}

export function chatClock(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// A URL, a bare www host, or a run of digits long enough to be a phone number.
// The alternation is ordered so a URL is consumed whole before the phone branch
// can pick digits out of its path.
const LINKABLE = /https?:\/\/[^\s<>"'`]+|www\.[^\s<>"'`]+|\+?\d[\d\s().-]{5,}\d/gi;

// Punctuation that ends a sentence rather than a link: "see https://x.com." is a
// link to x.com, not to "x.com.".
const TRAILING = ".,;:!?)\u2019\u201d";

function hrefFor(token) {
  if (/^www\./i.test(token)) return `https://${token}`;
  if (/^https?:\/\//i.test(token)) return token;
  return `tel:${token.replace(/[^\d+]/g, "")}`;
}

/**
 * Split a message body into renderable runs: plain text, and links that a
 * client can turn into anchors. Pure and order-preserving, so it can be tested
 * without a DOM and used by both the thread and the composer preview.
 *
 * A phone number needs at least seven digits to count; anything shorter (an
 * order number, a price) stays text.
 */
export function linkify(text) {
  const source = String(text ?? "");
  const segments = [];
  let cursor = 0;
  for (const match of source.matchAll(LINKABLE)) {
    const token = match[0];
    const start = match.index;
    let end = token.length;
    while (end > 0 && TRAILING.includes(token[end - 1])) end -= 1;
    const link = token.slice(0, end);
    const trail = token.slice(end);
    const isUrl = /^(https?:\/\/|www\.)/i.test(link);
    if (!isUrl && link.replace(/[^\d]/g, "").length < 7) {
      continue;
    }
    if (start > cursor) segments.push({ type: "text", value: source.slice(cursor, start) });
    segments.push({ type: "link", value: link, href: hrefFor(link) });
    if (trail) segments.push({ type: "text", value: trail });
    cursor = start + token.length;
  }
  if (cursor < source.length) segments.push({ type: "text", value: source.slice(cursor) });
  return segments;
}

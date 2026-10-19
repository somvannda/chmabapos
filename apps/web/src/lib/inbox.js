// Pure helpers for the store chat inbox.
//
// Kept free of React and of the API client so they can be unit-tested with the
// node test runner, and so the inbox component stays about layout and state.

export function mergeMessages(existing, incoming) {
  const byId = new Map(existing.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return Array.from(byId.values()).sort((a, b) => a.seq - b.seq);
}

export function highestSeq(messages) {
  return (messages || []).reduce((max, message) => Math.max(max, message.seq), 0);
}

// A server-sent event frame ends at a blank line; a chunk may contain several
// frames or half of one, so the remainder is handed back to the caller.
export function parseSseChunk(buffer) {
  const events = [];
  let rest = buffer;
  let boundary = rest.indexOf("\n\n");
  while (boundary !== -1) {
    const frame = rest.slice(0, boundary);
    rest = rest.slice(boundary + 2);
    const parsed = parseFrame(frame);
    if (parsed) events.push(parsed);
    boundary = rest.indexOf("\n\n");
  }
  return { events, rest };
}

function parseFrame(frame) {
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

// Who the store is talking to, in the order the inbox shows it. A name the store
// gave the thread wins, so a list of anonymous visitors is readable.
export function conversationLabel(conversation) {
  if (!conversation) return "Customer";
  return conversation.seller_label || conversation.guest_name || conversation.shopper_name || "Guest";
}

export function isSignedInCustomer(conversation) {
  return Boolean(conversation?.shopper_name);
}

export function unreadTotal(conversations) {
  return (conversations || []).reduce((sum, conversation) => sum + (conversation.unread_count || 0), 0);
}

// The stores a user may switch between, as dropdown options for the inbox. The
// list is already scoped to their access by the API, so an owner sees every store
// and a cashier only the ones they are assigned to. A store waiting on unread
// customer messages carries the count, so the merchant can see which store needs
// them before switching. Unread defaults to zero, so a store whose count has not
// loaded yet still renders as a plain name rather than "undefined".
export function storeSwitcherOptions(stores, unreadByStore = {}) {
  return (stores || []).map((store) => {
    const unread = Number(unreadByStore?.[store.id]) || 0;
    const name = store.name || "Store";
    return { value: store.id, label: unread > 0 ? `${name} (${unread})` : name };
  });
}

// Contact rows for the open thread's details panel. Only what the customer
// actually gave is returned, so an anonymous visitor with no email or phone shows
// no empty rows rather than a pair of dashes.
export function contactRows(conversation) {
  const rows = [];
  if (conversation?.contact_email) {
    rows.push({ label: "Email", value: conversation.contact_email, href: `mailto:${conversation.contact_email}` });
  }
  if (conversation?.contact_phone) {
    rows.push({ label: "Phone", value: conversation.contact_phone, href: `tel:${conversation.contact_phone.replace(/[^\d+]/g, "")}` });
  }
  return rows;
}

// A short two-note chime for a new customer message, so a merchant at the
// counter notices without watching the badge. Best-effort: browsers block audio
// until the page has had a gesture, so this returns false rather than throwing
// when it cannot play.
export function playChatChime() {
  if (typeof window === "undefined") return false;
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return false;
  try {
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(660, now);
    osc.frequency.setValueAtTime(880, now + 0.12);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.28);
    osc.connect(gain).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.3);
    osc.onended = () => { try { ctx.close(); } catch { /* already closed */ } };
    return true;
  } catch {
    return false;
  }
}

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

export function kindForFile(file) {
  const type = (file?.type || "").toLowerCase();
  if (type.startsWith("image/")) return "image";
  return "file";
}

export function previewText(conversation) {
  if (!conversation?.last_message_preview) return "No messages yet";
  return conversation.last_message_preview;
}

// A URL, a bare www host, or a run of digits long enough to be a phone number.
// Ordered so a URL is consumed whole before the phone branch can pick digits out
// of its path.
const LINKABLE = /https?:\/\/[^\s<>"'`]+|www\.[^\s<>"'`]+|\+?\d[\d\s().-]{5,}\d/gi;
// Punctuation that ends a sentence rather than a link.
const TRAILING = ".,;:!?)\u2019\u201d";

function hrefFor(token) {
  if (/^www\./i.test(token)) return `https://${token}`;
  if (/^https?:\/\//i.test(token)) return token;
  return `tel:${token.replace(/[^\d+]/g, "")}`;
}

/**
 * Split a message body into renderable runs: plain text, and links a client can
 * turn into anchors. Pure and order-preserving, so it is unit-tested without a
 * DOM. A number needs at least seven digits to count as a phone number, so an
 * order id or a price stays text.
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
    if (!isUrl && link.replace(/[^\d]/g, "").length < 7) continue;
    if (start > cursor) segments.push({ type: "text", value: source.slice(cursor, start) });
    segments.push({ type: "link", value: link, href: hrefFor(link) });
    if (trail) segments.push({ type: "text", value: trail });
    cursor = start + token.length;
  }
  if (cursor < source.length) segments.push({ type: "text", value: source.slice(cursor) });
  return segments;
}

export function relativeTime(iso, now = Date.now()) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) return "now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(iso).toLocaleDateString();
}

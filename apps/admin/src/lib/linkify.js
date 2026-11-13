// Link rendering for the admin support thread. The web app has a richer helper
// that also handles bare domains and phone numbers; here the composer inserts
// full https:// links, so the admin view only needs those plus sentence
// punctuation trimming.
const LINKABLE = /https?:\/\/[^\s<>"'`]+/gi;
const TRAILING = ".,;:!?)\u2019\u201d";

export function linkify(text) {
  const source = String(text ?? "");
  const segments = [];
  let cursor = 0;
  for (const match of source.matchAll(LINKABLE)) {
    const token = match[0];
    const start = match.index;
    let end = token.length;
    while (end > 0 && TRAILING.includes(token[end - 1])) end -= 1;
    const href = token.slice(0, end);
    const trail = token.slice(end);
    if (start > cursor) segments.push({ type: "text", value: source.slice(cursor, start) });
    segments.push({ type: "link", value: href, href });
    if (trail) segments.push({ type: "text", value: trail });
    cursor = start + token.length;
  }
  if (cursor < source.length) segments.push({ type: "text", value: source.slice(cursor) });
  return segments;
}

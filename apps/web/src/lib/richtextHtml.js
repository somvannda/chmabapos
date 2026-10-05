// Pure helpers shared by the support rich-text editor. Kept framework-free so
// they can be unit-tested with the built-in node test runner.

const HTML_TAG_RE = /<[a-z][\s\S]*>/i;

export function looksLikeHtml(value) {
  return HTML_TAG_RE.test(value || "");
}

export function escapeHtml(value) {
  return (value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Turn plain text (e.g. from the AI) into simple HTML paragraphs.
export function plainTextToHtml(text) {
  const raw = (text || "").replace(/\r\n/g, "\n").trim();
  if (!raw) return "";
  return raw
    .split(/\n{2,}/)
    .map((block) => `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

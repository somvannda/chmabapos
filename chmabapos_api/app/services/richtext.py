"""Server-side sanitising for the rich-text support editor.

The merchant and admin reply boxes are now WYSIWYG, so the browser can send a
small subset of HTML. Nothing the browser sends is trusted: this module strips
anything outside a conservative allow-list (no scripts, styles, event handlers
or unknown tags) before the text is stored or rendered into an email. Plain
text is detected and escaped so a message like ``a < b`` can never be mistaken
for markup.
"""
from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

# Tags a support reply is allowed to use. ``span`` is kept (but stripped of all
# attributes) because some browsers wrap formatted runs in it.
ALLOWED_TAGS = {
    "p",
    "br",
    "div",
    "span",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "a",
}

VOID_TAGS = {"br"}

# Only links carry attributes, and only these three.
ALLOWED_ATTRS = {
    "a": {"href", "title"},
}

_SAFE_URL = re.compile(r"^(https?:|mailto:|/|#)", re.IGNORECASE)
# Only treat input as HTML when it contains one of the tags we actually allow.
# Plain prose like "2 < 3" or "the <world> tag" must stay plain text.
_KNOWN_TAG_NAMES = "|".join(sorted(ALLOWED_TAGS))
_TAG_RE = re.compile(rf"</?(?:{_KNOWN_TAG_NAMES})\b[^>]*>", re.IGNORECASE)
# Remove whole dangerous blocks before parsing so their text does not leak in.
_DROP_BLOCKS = re.compile(r"<(script|style|iframe|object|embed|template)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in ALLOWED_TAGS:
            return
        if tag in VOID_TAGS:
            self.parts.append("<br>")
            return
        cleaned: list[str] = []
        allowed = ALLOWED_ATTRS.get(tag, set())
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None:
                continue
            if name == "href" and not _SAFE_URL.match(value.strip()):
                continue
            cleaned.append(f'{name}="{escape(value, quote=True)}"')
        # Link safety: opening a link must not hand the page over to the target.
        if tag == "a" and cleaned:
            cleaned.append('target="_blank"')
            cleaned.append('rel="noopener noreferrer"')
        self.parts.append(f"<{tag}{(' ' + ' '.join(cleaned)) if cleaned else ''}>")
        self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS or tag not in self.stack:
            return
        # Close any tags left open inside this one so the output stays balanced.
        while self.stack:
            current = self.stack.pop()
            self.parts.append(f"</{current}>")
            if current == tag:
                break

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data))


def looks_like_html(value: str | None) -> bool:
    """True when ``value`` contains at least one recognised HTML tag."""
    return bool(value) and bool(_TAG_RE.search(value or ""))


def sanitize_html(value: str | None) -> str:
    """Return a safe HTML fragment for storage and display.

    Plain text (no tags) is escaped and its newlines become ``<br>`` so it keeps
    the line breaks the composer showed. Unknown tags are dropped but their text
    content is kept.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    if not looks_like_html(raw):
        return escape(raw).replace("\n", "<br>")
    raw = _DROP_BLOCKS.sub("", raw)
    parser = _Sanitizer()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:  # pragma: no cover - malformed markup must never 500
        return escape(raw)
    while parser.stack:
        parser.parts.append(f"</{parser.stack.pop()}>")
    return "".join(parser.parts).strip()

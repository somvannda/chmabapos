// One place to turn a directory facet value into a label and a link, so the header's
// Categories menu and the directory's own filter chips cannot drift apart.
//
// The value comes from the API as a bare key (for example "coffee-shop"), which is why
// separators are turned into spaces before the first letter is capitalised.

export function categoryLabel(value) {
  const text = String(value || "").replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export function categoryHref(value) {
  return `/stores?vertical=${encodeURIComponent(String(value || ""))}`;
}

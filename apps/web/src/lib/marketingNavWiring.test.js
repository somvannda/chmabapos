import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Guards a real regression: the marketing header's "Stores" item is an ordinary
// link to the storefront directory, but every nav click was handed to
// goMarketingSection(), which called event.preventDefault() first and only then
// looked for a section with that id. "Stores" has no section id, so the click was
// cancelled and the link never navigated - the item looked broken rather than
// missing, which is the worst way for a link to fail. Nothing here renders, so a
// static check is what catches it.
const read = (relative) =>
  readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const marketing = read("../features/marketing.jsx");
const app = read("../App.jsx");

test("marketing header: only section items are handed to the section scroller", () => {
  assert.ok(
    !/onSection\s*&&\s*onSection\(event, item\.id\)/.test(marketing),
    "onNavClick must not hand every item to the section scroller; an item with no id is a plain link",
  );
  assert.match(
    marketing,
    /onNavClick=\{\(event, item\) => \{ if \(item\.id\) onSection\?\.\(event, item\.id\); \}\}/,
    "onNavClick must skip items that have no section id",
  );
});

test("marketing header: the Stores item is an external link with no section id", () => {
  assert.match(
    marketing,
    /\{ label: "Stores", href: storesUrl, external: true \}/,
    "Stores must point at the storefront directory in a new tab, not at a page section",
  );
});

test("marketing sections: a click without an id is never prevented", () => {
  assert.match(
    app,
    /const goMarketingSection = \(event, id\) => \{ if \(!id\) return; event\.preventDefault\(\);/,
    "goMarketingSection must bail out before preventDefault() when there is no id",
  );
});

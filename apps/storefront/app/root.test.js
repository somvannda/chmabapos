import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

// Nothing imports the favicon, so no bundler drags it in and no page fails when
// it is missing: the document still renders, CI still passes, and the only
// symptom is a blank tab icon plus a generic thumbnail on every store link a
// merchant shares. These assertions are the notice that was missing when the
// storefront shipped without the mark the other two surfaces had.
const rootSource = readFileSync(new URL("./root.jsx", import.meta.url), "utf8");

const ICONS = ["favicon.svg", "favicon-dark.svg", "favicon.png"];

test("the root document declares the mark for the tab and for dark chrome", () => {
  assert.match(rootSource, /rel="icon"/, "root.jsx declares no favicon at all");
  assert.match(rootSource, /href="\/favicon\.svg"/, "root.jsx does not point at /favicon.svg");
  // Without the dark variant the mark renders as a glaring white square for a
  // shopper whose browser chrome prefers dark.
  assert.match(rootSource, /href="\/favicon-dark\.svg"/, "root.jsx has no dark favicon");
  assert.match(rootSource, /prefers-color-scheme: dark/, "the dark favicon has no media query, so it never applies");
});

test("the icons are really shipped, so /favicon.svg is not a 404", () => {
  for (const file of ICONS) {
    const url = new URL(`../public/${file}`, import.meta.url);
    assert.ok(existsSync(url), `${file} is not in apps/storefront/public`);
  }
  assert.match(
    readFileSync(new URL("../public/favicon.svg", import.meta.url), "utf8"),
    /^<svg/,
    "favicon.svg is not an svg",
  );
});

test("the storefront ships apps/web's bytes, so the three surfaces cannot drift", () => {
  for (const file of ICONS) {
    const here = new URL(`../public/${file}`, import.meta.url);
    const web = new URL(`../../web/public/${file}`, import.meta.url);
    assert.ok(existsSync(web), `apps/web/public/${file} is gone; the shared mark has one owner`);
    assert.deepEqual(readFileSync(here), readFileSync(web), `${file} differs from apps/web's copy`);
  }
});

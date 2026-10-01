import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8").replace(
  /\r\n/g,
  "\n",
);

// Pull the dedicated dark-mode rule for native form controls out of the sheet.
const ruleMatch = styles.match(
  /\/\* Dark mode: default native form controls[\s\S]*?\n\}\n/,
);
const rule = ruleMatch ? ruleMatch[0] : "";

test("dark mode: native form controls have a default background and text color", () => {
  assert.ok(rule, "expected the dark-mode native form-control rule to exist");
  assert.match(rule, /background-color:\s*#1a1b1f/, "fields need a dark default background");
  assert.match(rule, /color:\s*#e4e4e8/, "fields need a light default text color");
});

test("dark mode: the field default targets input, select and textarea", () => {
  assert.match(rule, /:where\(\.dark\)\s+input/, "input must be themed");
  assert.match(rule, /:where\(\.dark\)\s+select/, "select must be themed");
  assert.match(rule, /:where\(\.dark\)\s+textarea/, "textarea must be themed");
});

test("dark mode: the field default stays low-specificity so utilities still win", () => {
  // `:where(.dark)` rather than `.dark input:not(...)` keeps specificity at 0,0,1,
  // so bg-white / bg-transparent / text-[#...] / dark:* utilities keep overriding it.
  assert.match(rule, /:where\(\.dark\)/, "scope must use :where(.dark) for low specificity");
  assert.doesNotMatch(
    rule,
    /^\.dark\s+input/m,
    "must not raise specificity with a bare .dark input selector",
  );
});

test("dark mode: checkboxes, radios and file inputs are left to the browser", () => {
  assert.match(rule, /:not\(\[type="checkbox"\]\)/, "checkbox must be excluded");
  assert.match(rule, /:not\(\[type="radio"\]\)/, "radio must be excluded");
  assert.match(rule, /:not\(\[type="file"\]\)/, "file input must be excluded");
});

test("dark mode: printed receipts are excluded from the field default", () => {
  assert.match(rule, /receipt-print-area/, "receipt print area must be excluded");
});

test("dark mode: the on-screen receipt paper is excluded from the field default", () => {
  assert.match(rule, /receipt-paper/, "on-screen receipt paper must be excluded");
});

test("dark mode: receipt palette overrides skip the on-screen receipt paper", () => {
  assert.ok(
    styles.includes(".receipt-paper, .receipt-paper *"),
    "the receipt palette overrides must exclude .receipt-paper so the preview stays paper-white",
  );
});

test("dark mode: tinted panels, chips and table borders are mapped", () => {
  for (const token of ["bg-[#fff9f0]", "bg-[#f6fbf1]", "border-[#f5f5f7]", "text-[#7a4d12]"]) {
    assert.ok(styles.includes(`[class~="${token}"]`), `expected ${token} to be mapped in dark mode`);
  }
});

test("dark mode: hover utilities are themed at higher specificity", () => {
  assert.ok(styles.includes('.dark [class~="hover:bg-[#fafafd]"]'), "neutral hover must be themed");
  assert.ok(styles.includes('.dark [class~="hover:bg-[#f4f2ff]"]'), "violet hover must be themed");
});

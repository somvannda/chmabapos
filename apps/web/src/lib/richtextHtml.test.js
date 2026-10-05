import assert from "node:assert/strict";
import { test } from "node:test";

import { escapeHtml, looksLikeHtml, plainTextToHtml } from "./richtextHtml.js";

test("plainTextToHtml wraps paragraphs, escapes markup and keeps breaks", () => {
  assert.equal(plainTextToHtml("Hello <b>there</b>"), "<p>Hello &lt;b&gt;there&lt;/b&gt;</p>");
  assert.equal(plainTextToHtml("one\n\ntwo"), "<p>one</p><p>two</p>");
  assert.equal(plainTextToHtml("a\nb"), "<p>a<br>b</p>");
  assert.equal(plainTextToHtml("   "), "");
  assert.equal(plainTextToHtml(null), "");
});

test("escapeHtml neutralises angle brackets and ampersands", () => {
  assert.equal(escapeHtml("a & b < c > d"), "a &amp; b &lt; c &gt; d");
});

test("looksLikeHtml detects markup but not plain prose", () => {
  assert.equal(looksLikeHtml("<p>x</p>"), true);
  assert.equal(looksLikeHtml("plain text"), false);
  assert.equal(looksLikeHtml(""), false);
});

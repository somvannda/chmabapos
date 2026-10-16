import test from "node:test";
import assert from "node:assert/strict";

import { MAX_EDGE, MAX_UPLOAD_BYTES, outputNameFor, outputTypeFor, scaledDimensions, shouldShrink } from "./imageUpload.js";

test("scaledDimensions: clamps the longest side and keeps the aspect ratio", () => {
  assert.deepEqual(scaledDimensions(4000, 3000, 1600), { width: 1600, height: 1200 });
  assert.deepEqual(scaledDimensions(3000, 4000, 1600), { width: 1200, height: 1600 });
});

test("scaledDimensions: a wide banner is clamped on its width, not its height", () => {
  assert.deepEqual(scaledDimensions(6000, 900, 1600), { width: 1600, height: 240 });
});

test("scaledDimensions: never enlarges an image that is already small enough", () => {
  assert.deepEqual(scaledDimensions(320, 240, 1600), { width: 320, height: 240 });
  assert.deepEqual(scaledDimensions(512, 512, 512), { width: 512, height: 512 });
});

test("scaledDimensions: a very thin image still comes out at least one pixel tall", () => {
  assert.deepEqual(scaledDimensions(10000, 1, 100), { width: 100, height: 1 });
});

test("scaledDimensions: junk input yields zeroes rather than NaN", () => {
  assert.deepEqual(scaledDimensions(undefined, undefined, 1600), { width: 0, height: 0 });
  assert.deepEqual(scaledDimensions("", "", 1600), { width: 0, height: 0 });
});

test("shouldShrink: too many pixels is reason enough, even for a small file", () => {
  assert.equal(shouldShrink({ bytes: 200_000, width: 4000, height: 3000 }, MAX_EDGE.cover), true);
});

test("shouldShrink: too many bytes is reason enough, even at modest dimensions", () => {
  assert.equal(shouldShrink({ bytes: 4_000_000, width: 1200, height: 900 }, MAX_EDGE.cover), true);
});

test("shouldShrink: an already-small image is left alone so it is not re-encoded needlessly", () => {
  assert.equal(shouldShrink({ bytes: 120_000, width: 800, height: 600 }, MAX_EDGE.cover), false);
});

test("shouldShrink: a logo uses the tighter limit, so a cover-sized image is still shrunk", () => {
  assert.equal(shouldShrink({ bytes: 120_000, width: 1600, height: 600 }, MAX_EDGE.logo), true);
});

test("outputTypeFor: transparency survives for PNG and WebP, everything else becomes JPEG", () => {
  assert.equal(outputTypeFor("image/png"), "image/png");
  assert.equal(outputTypeFor("image/webp"), "image/webp");
  assert.equal(outputTypeFor("image/jpeg"), "image/jpeg");
  assert.equal(outputTypeFor("image/heic"), "image/jpeg");
  assert.equal(outputTypeFor(""), "image/jpeg");
});

test("outputNameFor: the name always describes the bytes, because the API checks the suffix", () => {
  assert.equal(outputNameFor("IMG_4821.HEIC", "image/jpeg"), "IMG_4821.jpg");
  assert.equal(outputNameFor("logo.png", "image/png"), "logo.png");
  assert.equal(outputNameFor("no-extension", "image/webp"), "no-extension.webp");
  assert.equal(outputNameFor("", "image/jpeg"), "image.jpg");
  assert.equal(outputNameFor(".hidden", "image/jpeg"), "image.jpg");
});

test("MAX_UPLOAD_BYTES mirrors the API's own limit, so the client cannot disagree with it", () => {
  assert.equal(MAX_UPLOAD_BYTES, 5_000_000);
});

import assert from "node:assert/strict";
import test from "node:test";

import { launcherBottom, visibleViewportBox } from "./viewport.js";

test("no visual viewport means no measurement", () => {
  assert.equal(visibleViewportBox(null, 800), null);
  assert.equal(visibleViewportBox(undefined, 800), null);
});

test("a viewport with no chrome reports no gap", () => {
  assert.deepEqual(visibleViewportBox({ offsetTop: 0, height: 800 }, 800), {
    top: 0,
    height: 800,
    bottomGap: 0,
  });
});

test("floating browser chrome becomes a bottom gap", () => {
  // The layout viewport is still 800 tall while only 720 of it is visible.
  assert.deepEqual(visibleViewportBox({ offsetTop: 0, height: 720 }, 800), {
    top: 0,
    height: 720,
    bottomGap: 80,
  });
});

test("a scrolled visual viewport keeps its offset", () => {
  // iOS scrolls the layout viewport to reveal a focused composer.
  assert.deepEqual(visibleViewportBox({ offsetTop: 120, height: 500 }, 800), {
    top: 120,
    height: 500,
    bottomGap: 180,
  });
});

test("a layout height below the box does not produce a negative gap", () => {
  assert.deepEqual(visibleViewportBox({ offsetTop: 0, height: 800 }, 400), {
    top: 0,
    height: 800,
    bottomGap: 0,
  });
});

test("the launcher clears the cart bar and any browser chrome", () => {
  // No chrome: the cart bar is the binding constraint.
  assert.equal(launcherBottom(0), 96);
  // A floating toolbar of 54px: 24px above it is still below the cart bar.
  assert.equal(launcherBottom(54), 96);
  // A taller toolbar wins, keeping 24px of air above the visible edge.
  assert.equal(launcherBottom(120), 144);
  // Garbage still yields the cart-bar clearance, never NaN.
  assert.equal(launcherBottom(undefined), 96);
  assert.equal(launcherBottom(-20), 96);
});

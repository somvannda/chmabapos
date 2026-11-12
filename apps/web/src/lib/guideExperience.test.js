import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Static guards for the public guide reader. Nothing here renders React, so
// these catch the regressions that matter most: losing the cross-guide timeline,
// losing browser progress, or slipping back to hand-drawn "screenshots".
const read = (relative) => readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const guides = read("../features/guides.jsx");
const screens = read("../features/guideScreens.jsx");

test("guide reader keeps a cross-guide timeline with completed/current/next states", () => {
  assert.match(guides, /function GuidePathTimeline\(/, "the path timeline must stay on the guide page");
  assert.match(guides, /guide\.series/, "the timeline is driven by the API series, not a hard-coded list");
  assert.match(guides, /You are here/, "the reader must be able to see their position");
  assert.match(guides, /Up next/, "the reader must be told what follows the current guide");
  assert.match(guides, /progressState\(row\) === "complete"/, "completed guides need their own state");
});

test("guide progress survives a reload in this browser", () => {
  assert.match(guides, /chmaba\.guide\.progress\.v1/, "progress must be stored under the documented key");
  assert.match(guides, /saveGuideProgress\(/, "step changes must persist progress");
  assert.match(guides, /onProgressChange/, "the timeline must refresh when a step is completed");
});

test("guide illustrations are real product captures, not drawings", () => {
  assert.match(screens, /\/guide-screens\/\$\{key\}\.jpg/, "steps must render the captured screenshot");
  assert.match(screens, /Real Chmaba screen/, "the reader must know the image is the real product");
  assert.ok(!screens.includes("function POSScreen"), "the old hand-drawn POS mock must not return");
});

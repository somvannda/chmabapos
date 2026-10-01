import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// Guards a real regression: SupportChat called `api.supportConversations`, but
// api.js only defined `supportConversation` (singular), so the help page threw
// "api.supportConversations is not a function" at runtime. `npm run build` and
// the unit tests did not catch it. This static check does: every `api.<name>(`
// used by a feature file must be defined as a key in api.js.
const here = dirname(fileURLToPath(import.meta.url));
const apiSource = readFileSync(join(here, "..", "api.js"), "utf8");

const FEATURE_FILES = ["components/SupportChat.jsx", "features/help.jsx", "features/support.jsx"];

test("every api.<method>() used by a feature is defined in api.js", () => {
  for (const relative of FEATURE_FILES) {
    const source = readFileSync(join(here, "..", relative), "utf8");
    const used = new Set([...source.matchAll(/api\.([a-zA-Z0-9_]+)\s*\(/g)].map((match) => match[1]));
    for (const name of used) {
      assert.match(apiSource, new RegExp(`(^|\\s)${name}\\s*:`), `${relative} calls api.${name} but api.js does not define it`);
    }
  }
});

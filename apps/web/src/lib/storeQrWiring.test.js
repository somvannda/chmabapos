import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// The QR poster is mostly canvas drawing, which these tests cannot render. What
// they can pin is the wiring that is easy to lose: the per-store button, the
// canonical link the code encodes, and the credit line inside the saved image.
const read = (relative) => readFileSync(new URL(relative, import.meta.url), "utf8").replace(/\r\n/g, "\n");

const settings = read("../features/settings.jsx");
const modal = read("../features/storeQr.jsx");

test("every store row offers its own QR code", () => {
  assert.match(settings, /import \{ StoreQrModal \} from "\.\/storeQr";/, "the modal must be imported");
  assert.match(settings, /const \[qrStore, setQrStore\] = useState\(null\);/, "the open modal must track one store");
  assert.match(settings, /onClick=\{\(\) => setQrStore\(store\)\}/, "the row button must open that store's QR");
  assert.match(settings, /<QrCode size=\{12\} \/> QR</, "the row needs a visible QR control next to Store link");
});

test("the code encodes the public store page, not a generic dashboard link", () => {
  assert.match(
    settings,
    /<StoreQrModal store=\{qrStore\} link=\{storefrontUrl\(workspace\?\.company\?\.slug, qrStore\.slug\)/,
    "the QR must point at the storefront URL",
  );
  assert.match(modal, /value=\{link\}/, "the QR canvas must encode the link it was given");
});

test("the saved image carries the shop identity and the Chmaba credit", () => {
  assert.match(modal, /STORE_QR_POWERED_BY/, "the saved poster must credit Chmaba");
  assert.match(modal, /STORE_QR_SCAN_LINE/, "the poster must tell the customer what to do");
  assert.match(modal, /canvas\.toBlob\(resolve, "image\/png"\)/, "the QR must be saveable as an image");
  assert.match(modal, /anchor\.download = storeQrFileName\(name\)/, "the download needs a per-store filename");
});

test("a missing logo falls back to the store initial instead of failing", () => {
  assert.match(modal, /const initial = Array\.from\(name\.trim\(\)\)\[0\]\?\.toUpperCase\(\) \|\| "S";/);
  assert.match(modal, /if \(!raw\) \{[\s\S]*?setLogoState\("none"\);/, "no logo URL must settle immediately");
  assert.match(modal, /drawLogoBox\(ctx, logo, initial, 464, 708, 152, 34\)/, "the saved card must draw the initial when no logo loaded");
});

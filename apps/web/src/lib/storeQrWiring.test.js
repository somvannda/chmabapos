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
  assert.match(modal, /drawLogoBox\(ctx, logo, initial, 452, 858, 175, 40\)/, "the card must draw the initial when no logo loaded");
});

test("the modal preview and the saved PNG are the same canvas", () => {
  // The preview used to be HTML while the download was drawn separately, so
  // the two could drift in font sizes and logo placement. One canvas now backs
  // both, and the download reads the visible preview node.
  assert.match(modal, /const previewRef = useRef\(null\);/, "the preview needs a canvas ref");
  assert.match(modal, /<canvas[\s\S]*?ref=\{previewRef\}/, "the preview must be that canvas");
  assert.match(modal, /const canvas = previewRef\.current;/, "the download must use the preview canvas");
  assert.match(modal, /canvas\.toBlob\(resolve, "image\/png"\)/, "the preview canvas is exported as the PNG");
  assert.match(modal, /sm:grid-cols-\[300px_minmax\(0,1fr\)\]/, "desktop gets the preview beside the actions");
});

test("the Chmaba credit stays quieter than the scan line", () => {
  assert.match(modal, /800 42px[\s\S]*?STORE_QR_SCAN_LINE/, "the scan instruction is the prominent line");
  assert.match(modal, /600 24px[\s\S]*?STORE_QR_POWERED_BY/, "the credit is smaller and lighter");
});

test("Khmer text uses the app's Niradei face, not the system fallback", () => {
  assert.match(modal, /Inter, "Niradei", "Noto Sans Khmer Web"/, "the canvas font stack must match the app");
  assert.match(modal, /document\.fonts\.load\(/, "the canvas must wait for the Khmer face before drawing");
});

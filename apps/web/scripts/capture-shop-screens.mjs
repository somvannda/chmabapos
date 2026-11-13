/**
 * Capture the real product screens behind the shared "Every shop" guides.
 *
 * Run against the seeded demo workspace (see
 * `chmabapos_api/scripts/seed_shop_guides_demo.py`):
 *   API :8001, web :5173, storefront :3000
 *
 * Everything is a real screenshot of the shipped UI: no mock-ups.
 */
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const APP = "http://127.0.0.1:5173";
const STORE = "http://127.0.0.1:3000";
const API = "http://127.0.0.1:8001/api/v1";
const SLUG = "chmaba-shop";
const COMPANY = "chmaba-shop-guide";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

mkdirSync(OUT, { recursive: true });

const session = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: "shop-guide-demo@example.com", password: "shop-guide-demo-password" }),
}).then((r) => r.json());

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await context.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), session.access_token);
const page = await context.newPage();

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (name) => {
  await sleep(600);
  await page.screenshot({ path: `${OUT}${name}.jpg`, type: "jpeg", quality: 86 });
  console.log("captured", name);
};
const attempt = async (label, action) => {
  try {
    await action();
  } catch (error) {
    console.warn(`skip ${label}: ${error.message.split("\n")[0]}`);
  }
};
const go = async (view) => {
  await page.goto(`${APP}/${SLUG}/${view}`, { waitUntil: "networkidle" });
  await sleep(1000);
};
const settingsTab = async (name) => {
  await go("settings");
  await page.getByRole("button", { name, exact: true }).first().click();
  await sleep(1000);
};

// --- 1. Online ordering -----------------------------------------------------
await settingsTab("Online ordering");
await shot("shop-online-settings");

await page.goto(`${STORE}/${COMPANY}/chmaba-shop`, { waitUntil: "networkidle" });
await sleep(1600);
await shot("shop-storefront");

await go("orders");
await shot("shop-online-orders");

// --- 2. Payments ------------------------------------------------------------
await settingsTab("Bank & KHQR");
await shot("shop-khqr-settings");

await attempt("store-level KHQR", async () => {
  await page.getByText("Store-level KHQR").first().scrollIntoViewIfNeeded();
  await sleep(600);
  await shot("shop-khqr-store");
});

await attempt("POS charge", async () => {
  await go("pos");
  await page.getByText("Potato Chips").first().click();
  await sleep(700);
  await page.getByRole("button", { name: /^Charge/ }).first().click();
  await sleep(1200);
  await shot("shop-pos-charge");
});

// --- 3. Staff access --------------------------------------------------------
await go("team");
await shot("shop-team");

await attempt("role section", async () => {
  await go("team");
  await page.getByText("Roles & permissions").first().evaluate((el) => el.scrollIntoView({ block: "start" }));
  await sleep(900);
  await shot("shop-roles");
});

await settingsTab("Approval policy");
await shot("shop-approval-policy");

// --- 4. Suppliers and purchase orders --------------------------------------
await go("suppliers");
await shot("shop-suppliers");

await attempt("new purchase order", async () => {
  await go("purchasing");
  await page.getByRole("button", { name: /New purchase order/i }).first().click();
  await sleep(1000);
  await page.getByText("Select product", { exact: true }).click();
  await sleep(600);
  await page.getByRole("option").first().click();
  await sleep(600);
  const quantity = page.getByLabel(/Quantity/i).first();
  if (await quantity.count()) await quantity.fill("24");
  await page.getByText("No supplier", { exact: true }).click();
  await sleep(600);
  await page.getByRole("option", { name: /Phnom Penh Wholesale/ }).first().click();
  await sleep(700);
  await page.getByPlaceholder(/What you pay per unit/i).first().fill("0.35");
  await sleep(600);
  await shot("shop-po-new");
  await page.keyboard.press("Escape");
  await sleep(500);
});

await attempt("receive purchase order", async () => {
  await go("purchasing");
  const receive = page.getByRole("button", { name: /Receive/i }).first();
  if (await receive.count()) {
    await receive.click();
    await sleep(1000);
    await shot("shop-po-receive");
    await page.keyboard.press("Escape");
  } else {
    await shot("shop-po-receive");
  }
});


await browser.close();

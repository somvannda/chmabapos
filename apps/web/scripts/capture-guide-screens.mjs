// Capture real product screens for the public User Guides.
//
// Run the local stack and the demo seed first:
//   python chmabapos_api/scripts/seed_guides_demo.py
//   node scripts/capture-guide-screens.mjs
//
// The script logs into the demo workspace, walks the real app and writes JPEGs
// to public/guide-screens. Those files are the guide illustrations, so they must
// come from the shipped UI rather than from hand-drawn mockups.

import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const APP = "http://localhost:5173";
const API = "http://127.0.0.1:8001/api/v1";
const USER = "guide-demo@example.com";
const PASSWORD = "guide-demo-password";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const login = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: USER, password: PASSWORD }),
}).then((response) => response.json());
if (!login.access_token) throw new Error(`Could not sign in: ${JSON.stringify(login)}`);
await fetch(`${API}/auth/me/preferences`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${login.access_token}` },
  body: JSON.stringify({ preferences: { setup_journey_dismissed: true } }),
});

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await context.addInitScript((token) => {
  window.localStorage.setItem("chmaba.access_token", token);
}, login.access_token);
const page = await context.newPage();
const problems = [];
page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function shot(target, name, { full = false } = {}) {
  await sleep(650);
  await target.screenshot({ path: `${OUT}${name}.jpg`, type: "jpeg", quality: 86, fullPage: full });
  console.log(`captured ${name}`);
}

async function go(view) {
  await page.goto(`${APP}/guide-demo/${view}`, { waitUntil: "networkidle" });
  await sleep(900);
}

async function attempt(label, action) {
  try {
    await action();
    return true;
  } catch (error) {
    console.warn(`skip ${label}: ${error.message.split("\n")[0]}`);
    return false;
  }
}

// Dashboard / setup checklist.
await go("dashboard");
await shot(page, "checklist");

// Point of sale, empty register.
await go("pos");
await shot(page, "pos");

// Product picker: size variants then modifiers.
await attempt("open product options", async () => {
  await page.getByText(/Iced Latte · 16 oz/).first().click();
  await sleep(600);
  const oat = page.getByText("Oat milk", { exact: true }).first();
  if (await oat.count()) await oat.click();
  await shot(page, "pick");
  await page.getByRole("button", { name: /Add item/i }).click();
  await sleep(500);
  await page.getByText("Butter Croissant", { exact: true }).first().click();
  await sleep(700);
  await shot(page, "pos-cart");
});

// Payment screen.
await attempt("open charge", async () => {
  await page.getByRole("button", { name: /Charge/i }).first().click();
  await sleep(700);
  await shot(page, "charge");
  await page.keyboard.press("Escape");
  await sleep(300);
});

// Hold modal.
await attempt("hold cart", async () => {
  await page.getByRole("button", { name: /Hold order/i }).first().click();
  await sleep(600);
  await shot(page, "hold");
  await page.keyboard.press("Escape");
});

// Orders and a refund.
await go("orders");
await shot(page, "orders");
await attempt("open order", async () => {
  await page.locator("tbody tr").first().click();
  await sleep(800);
  await shot(page, "order-detail");
  const refund = page.getByRole("button", { name: /Refund/i }).first();
  if (await refund.count()) {
    await refund.click();
    await sleep(700);
    await shot(page, "refund");
    await page.keyboard.press("Escape");
  }
});

// Inventory.
await go("inventory");
await shot(page, "inventory");

// Shift close (the seed opened a shift).
await go("pos");
await attempt("open shift modal", async () => {
  await page.locator('[data-coach="pos-open-shift"], button[aria-label="Open shift"], button[aria-label="Close shift"]').first().click();
  await sleep(800);
  await shot(page, "shift");
  await page.keyboard.press("Escape");
});

// Settings sub-pages.
await go("settings");
await shot(page, "settings");
for (const [label, name] of [["Bank & KHQR", "payments"], ["Receipts", "receipt"], ["POS preferences", "pos-preferences"]]) {
  await attempt(`settings ${label}`, async () => {
    await page.getByText(label, { exact: true }).first().click();
    await sleep(700);
    await shot(page, name);
  });
}

// Catalog and the add-product form.
await go("catalog");
await shot(page, "menu");
await attempt("add product form", async () => {
  await page.getByRole("button", { name: /Add product/i }).first().click();
  await sleep(900);
  await shot(page, "product");
  await page.keyboard.press("Escape");
});

// Product editor tabs (variants and modifiers).
await attempt("edit product", async () => {
  const row = page.locator("tbody tr").filter({ hasText: "Iced Latte" }).first();
  await row.getByRole("button", { name: "Edit product" }).click();
  await sleep(900);
  await shot(page, "product-edit");
  for (const [label, name] of [["Variants", "variants"], ["Modifiers", "modifiers"]]) {
    const tab = page.getByRole("button", { name: label, exact: true }).first();
    if (await tab.count()) {
      await tab.click();
      await sleep(700);
      await shot(page, name);
    }
  }
  await page.keyboard.press("Escape");
});

// Team, reports, purchasing.
await go("team");
await shot(page, "team");
await go("reports");
await shot(page, "reports");
await go("purchasing");
await shot(page, "purchase");

// Customer display opened from the register.
await go("pos");
await attempt("customer display", async () => {
  const popupPromise = context.waitForEvent("page", { timeout: 5000 });
  await page.getByRole("button", { name: /customer display/i }).first().click();
  const popup = await popupPromise;
  await popup.waitForLoadState("networkidle");
  await sleep(900);
  await shot(popup, "display");
  await popup.close();
});

console.log(JSON.stringify({ problems }, null, 2));
await browser.close();


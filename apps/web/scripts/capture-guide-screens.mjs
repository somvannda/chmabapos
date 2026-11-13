// Capture real product screens for the public User Guides.
//
// Requires the local stack plus the demo seed:
//   python chmabapos_api/scripts/seed_guides_demo.py
//   node scripts/capture-guide-screens.mjs
//
// The demo workspace must be on a plan that includes shifts for the shift
// screens; the script skips those two files when the feature is gated. The
// admin account is not used here.
//
// Output: apps/web/public/guide-screens/*.jpg. Re-run this when the UI changes
// instead of editing the guide component to imitate a screen.

import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const APP = "http://localhost:5173";
const API = "http://127.0.0.1:8001/api/v1";
const USER = "guide-demo@example.com";
const PASSWORD = "guide-demo-password";
const ONBOARD_USER = "guide-onboarding@example.com";
const ONBOARD_PASSWORD = "guide-onboarding-password";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function login(email, password) {
  return fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  }).then((response) => response.json());
}

const session = await login(USER, PASSWORD);
if (!session.access_token) throw new Error(`Could not sign in: ${JSON.stringify(session)}`);
const storeId = (await fetch(`${API}/workspaces/current`, { headers: { Authorization: `Bearer ${session.access_token}` } }).then((r) => r.json())).store.id;
const api = (path, init = {}) => fetch(`${API}${path}`, {
  ...init,
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
    "X-Store-ID": storeId,
    ...(init.headers || {}),
  },
});

await fetch(`${API}/auth/me/preferences`, {
  method: "PATCH",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` },
  body: JSON.stringify({ preferences: { setup_journey_dismissed: true } }),
});

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await context.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), session.access_token);
const page = await context.newPage();
const problems = [];
page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));

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

// Open a size's options, choose oat milk, then build a two-line cart.
await attempt("product options", async () => {
  await page.getByText(/Iced Latte\s*[·-]?\s*16 oz/).first().click();
  await sleep(600);
  await shot(page, "pick");
  const oat = page.getByText("Oat milk", { exact: true }).first();
  if (await oat.count()) await oat.click();
  await page.getByRole("button", { name: /Add item/i }).click();
  await sleep(500);
  await page.getByText("Butter Croissant", { exact: true }).first().click();
  await sleep(700);
  await shot(page, "pos-cart");
});

// Payment screen.
await attempt("charge", async () => {
  await page.getByRole("button", { name: /^Charge/ }).first().click();
  await sleep(700);
  await shot(page, "charge");
});

// Hold an order from a fresh cart.
await go("pos");
await attempt("hold", async () => {
  await page.getByText(/Iced Latte\s*[·-]?\s*16 oz/).first().click();
  await sleep(400);
  const add = page.getByRole("button", { name: /Add item/i }).first();
  if (await add.count()) await add.click();
  await page.locator('button[aria-label="Hold order"]').click();
  await sleep(700);
  await shot(page, "hold");
});

// Orders: list, receipt drawer, refund dialog.
await go("orders");
await shot(page, "orders");
await attempt("order detail", async () => {
  await page.locator("tbody tr").first().getByRole("button", { name: "View receipt" }).click();
  await sleep(800);
  await shot(page, "order-detail");
  await page.getByRole("button", { name: "Close" }).first().click();
});
await attempt("refund", async () => {
  await go("orders");
  await page.locator("tbody tr").first().getByRole("button", { name: "More actions" }).click();
  await sleep(400);
  await page.getByText("Refund", { exact: true }).first().click();
  await sleep(800);
  await shot(page, "refund");
});

// Inventory.
await go("inventory");
await shot(page, "inventory");

// Shifts. The seed opens one; close it through the API for the opening screen.
await attempt("shift close", async () => {
  await go("pos");
  await page.locator('button[aria-label="Close shift"]').click();
  await sleep(700);
  await shot(page, "shift-close");
});
await attempt("shift open", async () => {
  const current = await api("/shifts/open").then((r) => r.json());
  if (current) {
    await api(`/shifts/${current.id}/close`, { method: "POST", body: JSON.stringify({ counted_cash: "200.00", notes: "Capture run" }) });
  }
  await go("pos");
  await page.locator('button[aria-label="Open shift"]').click();
  await sleep(700);
  await shot(page, "shift");
  await api("/shifts/open", { method: "POST", body: JSON.stringify({ opening_float: "200.00", note: "Guide demo" }) });
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

// Catalog, add form, variants, modifier groups and the product editor.
await go("catalog");
await shot(page, "menu");
await attempt("add product", async () => {
  await page.getByRole("button", { name: /Add product/i }).first().click();
  await sleep(900);
  await shot(page, "product");
});
await go("catalog");
await attempt("variants", async () => {
  await page.locator("tbody tr").filter({ hasText: "Iced Latte" }).first().getByRole("button", { name: "Manage variants" }).click();
  await sleep(800);
  await shot(page, "variants");
});
await go("catalog");
await attempt("modifier groups", async () => {
  await page.getByRole("button", { name: /Modifier groups/i }).click();
  await sleep(800);
  await shot(page, "modifiers");
});
await go("catalog");
await attempt("edit product", async () => {
  await page.locator("tbody tr").filter({ hasText: "Iced Latte" }).first().getByRole("button", { name: "Edit product" }).click();
  await sleep(900);
  await shot(page, "product-edit");
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

// Onboarding (a second account that has not created a workspace yet).
try {
  let onboarding = await login(ONBOARD_USER, ONBOARD_PASSWORD);
  if (!onboarding.access_token) {
    const registered = await fetch(`${API}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: ONBOARD_USER, full_name: "Guide Onboarding", password: ONBOARD_PASSWORD }),
    }).then((r) => r.json());
    await fetch(`${API}/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: registered.dev_verification_token }),
    });
    onboarding = await login(ONBOARD_USER, ONBOARD_PASSWORD);
  }
  if (onboarding.access_token) {
    const onboardingContext = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await onboardingContext.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), onboarding.access_token);
    const onboardingPage = await onboardingContext.newPage();
    await onboardingPage.goto(`${APP}/guide-onboarding/setup/company`, { waitUntil: "networkidle" });
    await sleep(1200);
    await shot(onboardingPage, "workspace");
    await onboardingContext.close();
  }
} catch (error) {
  console.warn(`skip workspace: ${error.message.split("\n")[0]}`);
}

console.log(JSON.stringify({ problems }, null, 2));
await browser.close();

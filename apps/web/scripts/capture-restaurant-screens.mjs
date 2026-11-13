// Capture real restaurant screens for the public User Guides.
//
// Requires the dev API on :8001, the web app on :5173 and:
//   PYTHONPATH=chmabapos_api python chmabapos_api/scripts/seed_restaurant_guides_demo.py
//   node apps/web/scripts/capture-restaurant-screens.mjs

import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const APP = "http://localhost:5173";
const API = "http://127.0.0.1:8001/api/v1";
const USER = "restaurant-demo@example.com";
const PASSWORD = "restaurant-demo-password";
const ONBOARD_EMAIL = "guide-onboarding-restaurant@example.com";
const ONBOARD_PASSWORD = "guide-onboarding-password";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const login = (email, password) => fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
}).then((response) => response.json());

async function ensureOnboardingAccount() {
  let session = await login(ONBOARD_EMAIL, ONBOARD_PASSWORD);
  if (session.access_token) return session;
  const registered = await fetch(`${API}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ONBOARD_EMAIL, full_name: "Restaurant Onboarding", password: ONBOARD_PASSWORD }),
  }).then((response) => response.json());
  await fetch(`${API}/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: registered.dev_verification_token }),
  });
  session = await login(ONBOARD_EMAIL, ONBOARD_PASSWORD);
  return session;
}

const session = await login(USER, PASSWORD);
if (!session.access_token) throw new Error(`Could not sign in: ${JSON.stringify(session)}`);
const workspace = await fetch(`${API}/workspaces/current`, { headers: { Authorization: `Bearer ${session.access_token}` } }).then((r) => r.json());
const storeId = workspace.store.id;
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

async function shot(target, name) {
  await sleep(700);
  await target.screenshot({ path: `${OUT}${name}.jpg`, type: "jpeg", quality: 86 });
  console.log(`captured ${name}`);
}

async function go(view) {
  await page.goto(`${APP}/restaurant-demo/${view}`, { waitUntil: "networkidle" });
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

await go("dashboard");
await shot(page, "restaurant-checklist");

await go("catalog");
await shot(page, "restaurant-menu");
await attempt("add product", async () => {
  await page.getByRole("button", { name: /Add product/i }).first().click();
  await sleep(900);
  await shot(page, "restaurant-product");
});
await go("catalog");
await attempt("modifier groups", async () => {
  await page.getByRole("button", { name: /Modifier groups/i }).click();
  await sleep(800);
  await shot(page, "restaurant-modifiers");
});
await go("catalog");
await attempt("edit product", async () => {
  await page.locator("tbody tr").filter({ hasText: "Beef Lok Lak" }).first().getByRole("button", { name: "Edit product" }).click();
  await sleep(900);
  await shot(page, "restaurant-product-edit");
});

await go("settings");
await shot(page, "restaurant-settings");
for (const [label, name] of [["Tables", "tables"], ["Bank & KHQR", "restaurant-payments"], ["Receipts", "restaurant-receipt"]]) {
  await attempt(`settings ${label}`, async () => {
    await page.getByText(label, { exact: true }).first().click();
    await sleep(800);
    await shot(page, name);
  });
}

await go("floor");
await shot(page, "floor");

await go("kitchen");
await shot(page, "kitchen");

await go("deliveries");
await shot(page, "deliveries");

await go("pos");
await shot(page, "restaurant-pos");
await attempt("dine-in order", async () => {
  await page.getByRole("button", { name: /Takeaway/i }).first().click();
  await sleep(300);
  await page.getByText("Dine-in", { exact: true }).first().click();
  await sleep(400);
  await page.getByRole("button", { name: /No table/i }).first().click();
  await sleep(300);
  await page.getByText("T2", { exact: true }).first().click();
  await sleep(500);
  await page.getByText("Beef Lok Lak", { exact: true }).first().click();
  await sleep(500);
  const option = page.getByText("Medium", { exact: true }).first();
  if (await option.count()) await option.click();
  const add = page.getByRole("button", { name: /Add item/i }).first();
  if (await add.count()) await add.click();
  await sleep(500);
  await page.getByText("Iced Tea", { exact: true }).first().click();
  await sleep(700);
  await shot(page, "dine-in");
});
await attempt("charge", async () => {
  await page.getByRole("button", { name: /^Charge/ }).first().click();
  await sleep(700);
  await shot(page, "restaurant-charge");
});

await go("orders");
await shot(page, "restaurant-orders");
await attempt("receipt", async () => {
  await page.locator("tbody tr").first().getByRole("button", { name: "View receipt" }).click();
  await sleep(800);
  await shot(page, "restaurant-receipt-detail");
  await page.getByRole("button", { name: "Close" }).first().click();
});

await go("reports");
await shot(page, "restaurant-reports");
await go("team");
await shot(page, "restaurant-team");
await go("inventory");
await shot(page, "restaurant-inventory");

await attempt("shift close", async () => {
  await go("pos");
  await page.locator('button[aria-label="Close shift"]').click();
  await sleep(700);
  await shot(page, "restaurant-shift-close");
});

// Onboarding with the restaurant business type selected.
try {
  const onboarding = await ensureOnboardingAccount();
  if (onboarding.access_token) {
    const onboardingContext = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await onboardingContext.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), onboarding.access_token);
    const onboardingPage = await onboardingContext.newPage();
    await onboardingPage.goto(`${APP}/guide-onboarding-restaurant/setup/company`, { waitUntil: "networkidle" });
    await sleep(1200);
    await onboardingPage.getByPlaceholder("e.g. Cedar & Stone").fill("Chmaba Bistro");
    await onboardingPage.getByPlaceholder("e.g. Main store").fill("Chmaba Bistro");
    await onboardingPage.getByRole("button", { name: /Other \/ general/i }).click();
    await sleep(300);
    await onboardingPage.getByText("Restaurant / food service", { exact: true }).click();
    await sleep(500);
    await shot(onboardingPage, "restaurant-workspace");
    await onboardingContext.close();
  }
} catch (error) {
  console.warn(`skip restaurant-workspace: ${error.message.split("\n")[0]}`);
}

console.log(JSON.stringify({ problems }, null, 2));
await browser.close();

// Capture real mart screens for the public User Guides.
//
// Requires the dev API on :8001, web on :5173 and:
//   PYTHONPATH=chmabapos_api python chmabapos_api/scripts/seed_mart_guides_demo.py

import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const APP = "http://localhost:5173";
const API = "http://127.0.0.1:8001/api/v1";
const USER = "mart-demo@example.com";
const PASSWORD = "mart-demo-password";
const ONBOARD_EMAIL = "guide-onboarding-restaurant@example.com";
const ONBOARD_PASSWORD = "guide-onboarding-password";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const session = await fetch(`${API}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: USER, password: PASSWORD }),
}).then((response) => response.json());

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
  await page.goto(`${APP}/mart-demo/${view}`, { waitUntil: "networkidle" });
  await sleep(900);
}

async function attempt(label, action) {
  try {
    await action();
  } catch (error) {
    console.warn(`skip ${label}: ${error.message.split("\n")[0]}`);
  }
}

await go("dashboard");
await shot(page, "mart-checklist");

await go("catalog");
await shot(page, "mart-menu");
await attempt("add product", async () => {
  await page.getByRole("button", { name: /Add product/i }).first().click();
  await sleep(900);
  await shot(page, "mart-product");
});
await go("catalog");
await attempt("edit product", async () => {
  await page.locator("tbody tr").filter({ hasText: "Coca-Cola" }).first().getByRole("button", { name: "Edit product" }).click();
  await sleep(900);
  await shot(page, "mart-product-edit");
});

await go("inventory");
await shot(page, "mart-inventory");
await attempt("expiry card", async () => {
  const expiry = page.getByText("Expiring batches", { exact: false }).first();
  if (await expiry.count()) {
    await expiry.scrollIntoViewIfNeeded();
    await sleep(400);
    await shot(page, "mart-expiry");
  }
});

await go("purchasing");
await shot(page, "mart-purchasing");
await go("team");
await shot(page, "mart-team");
await go("settings");
await shot(page, "mart-settings");
await go("reports");
await shot(page, "mart-reports");

await go("pos");
await shot(page, "mart-pos");
await attempt("charge", async () => {
  await page.getByText("Coca-Cola 330ml", { exact: true }).first().click();
  await sleep(500);
  await page.getByRole("button", { name: /^Charge/ }).first().click();
  await sleep(700);
  await shot(page, "mart-charge");
});

// Onboarding with the mart business type selected.
try {
  const onboarding = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ONBOARD_EMAIL, password: ONBOARD_PASSWORD }),
  }).then((response) => response.json());
  if (onboarding.access_token) {
    const onboardingContext = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await onboardingContext.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), onboarding.access_token);
    const onboardingPage = await onboardingContext.newPage();
    await onboardingPage.goto(`${APP}/guide-onboarding-restaurant/setup/company`, { waitUntil: "networkidle" });
    await sleep(900);
    await onboardingPage.getByPlaceholder("e.g. Cedar & Stone").fill("Chmaba Mart");
    await onboardingPage.getByPlaceholder("e.g. Main store").fill("Chmaba Mart");
    await onboardingPage.getByText("Other / general", { exact: true }).click();
    await sleep(300);
    await onboardingPage.getByText("Mart / grocery", { exact: true }).click();
    await sleep(500);
    await shot(onboardingPage, "mart-workspace");
    await onboardingContext.close();
  }
} catch (error) {
  console.warn(`skip mart-workspace: ${error.message.split("\n")[0]}`);
}

console.log(JSON.stringify({ problems }, null, 2));
await browser.close();

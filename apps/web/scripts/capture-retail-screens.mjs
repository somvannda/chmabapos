import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
const APP = "http://localhost:5173";
const API = "http://127.0.0.1:8001/api/v1";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });
const session = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "retail-demo@example.com", password: "retail-demo-password" }) }).then((r) => r.json());
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await context.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), session.access_token);
const page = await context.newPage();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (name, target = page) => { await sleep(700); await target.screenshot({ path: `${OUT}${name}.jpg`, type: "jpeg", quality: 86 }); console.log("captured", name); };
const go = async (view) => { await page.goto(`${APP}/retail-demo/${view}`, { waitUntil: "networkidle" }); await sleep(900); };
const attempt = async (label, action) => { try { await action(); } catch (error) { console.warn(`skip ${label}: ${error.message.split("\n")[0]}`); } };
await go("dashboard"); await shot("retail-checklist");
await go("catalog"); await shot("retail-menu");
await attempt("add product", async () => { await page.getByRole("button", { name: /Add product/i }).first().click(); await sleep(900); await shot("retail-product"); });
await go("catalog");
await attempt("edit product", async () => { await page.locator("tbody tr").filter({ hasText: "Cotton T-Shirt" }).first().getByRole("button", { name: "Edit product" }).click(); await sleep(900); await shot("retail-product-edit"); });
await go("inventory"); await shot("retail-inventory");
await go("reports"); await shot("retail-reports");
await go("team"); await shot("retail-team");
await go("settings"); await shot("retail-settings");
await go("pos"); await shot("retail-pos");
await attempt("charge", async () => { await page.getByText(/Cotton T-Shirt/).first().click(); await sleep(600); const medium = page.getByText("Medium", { exact: true }).first(); if (await medium.count()) await medium.click(); await sleep(500); await page.getByRole("button", { name: /^Charge/ }).first().click(); await sleep(700); await shot("retail-charge"); });
try {
  const onboarding = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "guide-onboarding-restaurant@example.com", password: "guide-onboarding-password" }) }).then((r) => r.json());
  if (onboarding.access_token) {
    const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await ctx2.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), onboarding.access_token);
    const p2 = await ctx2.newPage();
    await p2.goto(`${APP}/guide-onboarding-restaurant/setup/company`, { waitUntil: "networkidle" });
    await sleep(900);
    await p2.getByPlaceholder("e.g. Cedar & Stone").fill("Chmaba Retail");
    await p2.getByPlaceholder("e.g. Main store").fill("Chmaba Retail");
    await p2.getByText("Other / general", { exact: true }).click();
    await sleep(300);
    await p2.getByText("General retail shop", { exact: true }).click();
    await sleep(500);
    await shot("retail-workspace", p2);
    await ctx2.close();
  }
} catch (error) { console.warn(`skip workspace: ${error.message.split("\n")[0]}`); }
await browser.close();

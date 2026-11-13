import { mkdirSync } from "node:fs";
import { chromium } from "playwright";
const APP = "http://localhost:5173";
const API = "http://127.0.0.1:8001/api/v1";
const OUT = new URL("../public/guide-screens/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
mkdirSync(OUT, { recursive: true });
const session = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "electronics-demo@example.com", password: "electronics-demo-password" }) }).then((r) => r.json());
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await context.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), session.access_token);
const page = await context.newPage();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (name, target = page) => { await sleep(700); await target.screenshot({ path: `${OUT}${name}.jpg`, type: "jpeg", quality: 86 }); console.log("captured", name); };
const go = async (view) => { await page.goto(`${APP}/electronics-demo/${view}`, { waitUntil: "networkidle" }); await sleep(900); };
const attempt = async (label, action) => { try { await action(); } catch (error) { console.warn(`skip ${label}: ${error.message.split("\n")[0]}`); } };

await go("dashboard"); await shot("electronics-checklist");
await go("catalog"); await shot("electronics-menu");
await attempt("add product", async () => { await page.getByRole("button", { name: /Add product/i }).first().click(); await sleep(900); await shot("electronics-product"); });
await go("catalog");
await attempt("edit product", async () => { await page.locator("tbody tr").filter({ hasText: "iPhone 15" }).first().getByRole("button", { name: "Edit product" }).click(); await sleep(900); await shot("electronics-product-edit"); });
await go("catalog");
await attempt("serials", async () => { await page.locator("tbody tr").filter({ hasText: "iPhone 15" }).first().getByRole("button", { name: "Manage serials" }).click(); await sleep(900); await shot("electronics-serials"); });
await go("reports"); await shot("electronics-reports");
await go("team"); await shot("electronics-team");
await go("settings"); await shot("electronics-settings");
await go("pos"); await shot("electronics-pos");
await attempt("serial picker", async () => { await page.getByText("iPhone 15 128GB", { exact: true }).first().click(); await sleep(800); await shot("electronics-serial-pick"); await page.keyboard.press("Escape"); });
await attempt("lookup", async () => { await page.locator('button[aria-label="Find a serial"]').click(); await sleep(700); await page.getByPlaceholder(/serial/i).first().fill("IP15-8F2K1"); await page.keyboard.press("Enter"); await sleep(900); await shot("electronics-lookup"); });

try {
  const onboarding = await fetch(`${API}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: "guide-onboarding-restaurant@example.com", password: "guide-onboarding-password" }) }).then((r) => r.json());
  if (onboarding.access_token) {
    const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
    await ctx2.addInitScript((token) => localStorage.setItem("chmaba.access_token", token), onboarding.access_token);
    const p2 = await ctx2.newPage();
    await p2.goto(`${APP}/guide-onboarding-restaurant/setup/company`, { waitUntil: "networkidle" });
    await sleep(900);
    await p2.getByPlaceholder("e.g. Cedar & Stone").fill("Chmaba Electronics");
    await p2.getByPlaceholder("e.g. Main store").fill("Chmaba Electronics");
    await p2.getByText("Other / general", { exact: true }).click();
    await sleep(300);
    await p2.getByText("Electronics store", { exact: true }).click();
    await sleep(500);
    await shot("electronics-workspace", p2);
    await ctx2.close();
  }
} catch (error) { console.warn(`skip workspace: ${error.message.split("\n")[0]}`); }
await browser.close();

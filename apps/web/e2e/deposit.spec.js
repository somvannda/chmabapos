import { test, expect } from "@playwright/test";

const API = "http://127.0.0.1:8001/api/v1";

function sanitizeUsername(email) {
  return (email.split("@")[0] || "user").toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "user";
}

async function call(request, method, path, { token, storeId, data } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (storeId) headers["X-Store-ID"] = storeId;
  const response = await request[method](`${API}${path}`, { headers, data });
  if (!response.ok()) throw new Error(`${method.toUpperCase()} ${path} -> ${response.status()} ${await response.text()}`);
  return response.status() === 204 ? null : response.json();
}

// A reservation deposit can be paid by KHQR. This drives the real POS: pick
// KHQR, reserve for later pickup, take the deposit, settle the mock QR, and
// confirm the order opened for pickup with the deposit recorded.
test.describe("POS: deposit paid by KHQR", () => {
  let token;
  let storeId;
  let username;
  const productName = "E2E Deposit Widget";

  test.beforeAll(async ({ request }) => {
    const email = `e2e-deposit-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", { data: { email, full_name: "E2E Deposit", password } });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;
    const workspace = await call(request, "post", "/workspaces/setup", { token, data: { company_name: "E2E Deposit Co", store_name: "Main Counter", country: "Cambodia", currency_code: "USD", plan_code: "starter" } });
    storeId = workspace.store.id;
    username = sanitizeUsername(email);
    if (workspace.billing_payment?.external_id) {
      await call(request, "post", `/mock/chamabapay/${workspace.billing_payment.external_id}/complete`);
    }
    // KHQR checkout needs an active merchant link on the company.
    await call(request, "patch", "/company", { token, data: { aba_payway_link: "https://link.payway.com.kh/ABAPAYe2edeposit" } });
    await call(request, "post", "/products", { token, storeId, data: { name: productName, sku: `E2E-DEP-${Date.now()}`, price: "100.00", opening_stock: 5 } });
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), ["chmaba.access_token", token]);
  });

  test("takes a KHQR deposit and opens the order for pickup", async ({ page, request }) => {
    await page.goto(`/${username}/pos`);
    await expect(page.getByRole("heading", { name: "Make a sale" })).toBeVisible();

    await page.getByText(productName, { exact: false }).first().click();
    await page.getByRole("button", { name: /Charge \$/ }).click();

    // Pay the deposit by KHQR: switch the first tender to KHQR and size it to 30.
    await page.getByRole("button", { name: "Cash" }).click();
    await page.getByRole("option", { name: "KHQR" }).click();
    const paymentModal = page.locator("h2", { hasText: "Complete payment" }).locator("xpath=../../..");
    await paymentModal.locator('input[type="number"]').fill("30");

    // Reserve for later pickup with a future pickup time.
    await page.getByLabel("Reserve for later pickup").check();
    const pickup = new Date(Date.now() + 24 * 60 * 60 * 1000);
    const pad = (value) => String(value).padStart(2, "0");
    const local = `${pickup.getFullYear()}-${pad(pickup.getMonth() + 1)}-${pad(pickup.getDate())}T${pad(pickup.getHours())}:${pad(pickup.getMinutes())}`;
    await page.locator('input[type="datetime-local"]').fill(local);

    await page.getByRole("button", { name: /Take deposit/ }).click();

    // The deposit QR is shown; settle it with the mock provider.
    await expect(page.getByText("Waiting for KHQR payment")).toBeVisible();
    await page.getByRole("button", { name: /Simulate paid/ }).click();
    await expect(page.getByText("Waiting for KHQR payment")).toBeHidden();

    // The order is now a pickup reservation with the deposit recorded.
    const orders = await call(request, "get", "/orders", { token, storeId });
    const order = orders.find((row) => (row.items || []).some((item) => item.product_name === productName));
    expect(order).toBeTruthy();
    expect(order.status).toBe("pending_pickup");
    expect(Number(order.deposit)).toBe(30);
    expect(Number(order.balance_due)).toBeGreaterThan(0);
  });
});

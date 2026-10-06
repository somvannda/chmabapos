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

// Guards a real regression: the collect-balance modal prefilled "Cash received"
// with the whole balance, so ticking "Collect the rest by KHQR" left no
// remainder. No QR was raised, the balance was taken as cash and the receipt
// auto-printed. This drives the real Orders screen and proves a QR is raised.
test.describe("POS: collect a pickup balance by KHQR", () => {
  let token;
  let storeId;
  let username;
  let orderId;
  let balance;
  const productName = "E2E Collect Widget";

  test.beforeAll(async ({ request }) => {
    const email = `e2e-collect-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", { data: { email, full_name: "E2E Collect", password } });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;
    const workspace = await call(request, "post", "/workspaces/setup", { token, data: { company_name: "E2E Collect Co", store_name: "Main Counter", country: "Cambodia", currency_code: "USD", plan_code: "starter" } });
    storeId = workspace.store.id;
    username = sanitizeUsername(email);
    if (workspace.billing_payment?.external_id) {
      await call(request, "post", `/mock/chamabapay/${workspace.billing_payment.external_id}/complete`);
    }
    // KHQR checkout needs an active merchant link on the company.
    await call(request, "patch", "/company", { token, data: { aba_payway_link: "https://link.payway.com.kh/ABAPAYe2ecollect" } });
    const product = await call(request, "post", "/products", { token, storeId, data: { name: productName, sku: `E2E-COL-${Date.now()}`, price: "100.00", opening_stock: 5 } });

    // A pickup reservation with a cash deposit: the balance is collected later.
    const pickup = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    const reservation = await call(request, "post", "/orders", {
      token,
      storeId,
      data: { items: [{ product_id: product.id, quantity: 1 }], tenders: [{ method: "cash", currency_code: "USD", amount: "30.00" }], pickup_at: pickup, hold_stock: true },
    });
    expect(reservation.status).toBe("pending_pickup");
    orderId = reservation.id;
    balance = Number(reservation.balance_due);
    expect(balance).toBeGreaterThan(0);
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), ["chmaba.access_token", token]);
  });

  test("switching the balance to KHQR raises a QR instead of collecting cash", async ({ page, request }) => {
    await page.goto(`/${username}/orders`);
    await expect(page.getByRole("heading", { name: "Orders", level: 2 })).toBeVisible();

    await page.getByRole("button", { name: "Collect balance" }).first().click();
    const modal = page.getByTestId("collect-balance");
    await expect(modal).toBeVisible();

    // The cash field starts prefilled with the whole balance.
    const cashInput = modal.locator('input[inputmode="decimal"]');
    await expect(cashInput).toHaveValue(balance.toFixed(2));

    // Switching to KHQR must clear that prefilled amount so a QR is raised.
    await modal.getByLabel("Collect the rest by KHQR").check();
    await expect(cashInput).toHaveValue("");
    await modal.getByRole("button", { name: /Collect \+ create KHQR/ }).click();

    // A QR is shown for the outstanding balance (not silently collected as cash).
    const qrModal = page.getByTestId("collect-balance-qr");
    await expect(qrModal).toBeVisible();

    // Settle the balance QR with the mock provider.
    const fresh = await call(request, "get", `/orders/${orderId}`, { token, storeId });
    const qr = fresh.payments.find((payment) => payment.external_id && payment.status !== "paid");
    expect(qr).toBeTruthy();
    expect(Number(qr.amount)).toBeCloseTo(balance, 2);
    await call(request, "post", `/mock/chamabapay/${qr.external_id}/complete`);

    // The collect modal closes once the balance settles.
    await expect(qrModal).toBeHidden();

    const paid = await call(request, "get", `/orders/${orderId}`, { token, storeId });
    expect(paid.status).toBe("paid");
    expect(Number(paid.balance_due)).toBe(0);
  });
});

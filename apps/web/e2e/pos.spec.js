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

test.describe("POS: serial sale and discount mode", () => {
  let token;
  let storeId;
  let username;
  const productName = "E2E MacBook";
  const serialNumbers = ["E2E-SN-1", "E2E-SN-2"];

  test.beforeAll(async ({ request }) => {
    const email = `e2e-${Date.now()}@example.com`;
    const password = "strong-password";
    const registered = await call(request, "post", "/auth/register", { data: { email, full_name: "E2E Cashier", password } });
    await call(request, "post", "/auth/verify-email", { data: { token: registered.dev_verification_token } });
    const login = await call(request, "post", "/auth/login", { data: { email, password } });
    token = login.access_token;
    const workspace = await call(request, "post", "/workspaces/setup", { token, data: { company_name: "E2E Store", store_name: "Main Counter", country: "Cambodia", currency_code: "USD", plan_code: "free" } });
    storeId = workspace.store.id;
    username = sanitizeUsername(email);
    const product = await call(request, "post", "/products", { token, storeId, data: { name: productName, sku: `E2E-${Date.now()}`, price: "600.00", track_serials: true } });
    await call(request, "post", `/products/${product.id}/serials`, { token, storeId, data: { serials: serialNumbers.map((serial_number) => ({ serial_number })) } });
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(([key, value]) => window.localStorage.setItem(key, value), ["chmaba.access_token", token]);
  });

  test("discount mode uses a flat amount, then sells a serial", async ({ page }) => {
    await page.goto(`/${username}/pos`);
    await expect(page.getByRole("heading", { name: "Make a sale" })).toBeVisible();

    // Add the serial-tracked product to the cart.
    await page.getByText(productName, { exact: false }).first().click();
    await expect(page.getByText(productName, { exact: false }).first()).toBeVisible();

    // Switch the discount unit to USD and enter a flat 30.
    await page.getByRole("button", { name: "%" }).click();
    await page.getByRole("option", { name: "USD" }).click();
    const discountInput = page.getByLabel(/Discount amount in USD/);
    await discountInput.fill("30");
    await expect(page.getByText("-$30.00")).toBeVisible();

    // Charge: complete payment, then pick a serial from the two available units.
    await page.getByRole("button", { name: /Charge \$/ }).click();
    await page.getByRole("button", { name: /Complete sale/ }).click();
    await expect(page.getByText("Choose serial numbers")).toBeVisible();
    await page.getByRole("button", { name: serialNumbers[0] }).click();
    await page.getByRole("button", { name: /Confirm/ }).click();
    await expect(page.getByText("Choose serial numbers")).toBeHidden();
  });

  test("search dropdown renders decimal-string prices without crashing", async ({ page }) => {
    await page.goto(`/${username}/pos`);
    await expect(page.getByRole("heading", { name: "Make a sale" })).toBeVisible();

    // The API serializes price as a decimal string (e.g. "600.00"). Rendering a
    // result used to call toFixed on that string and blank the whole page.
    const searchInput = page.getByPlaceholder("Search or scan name, SKU, barcode or serial...");
    await searchInput.fill("E2E Mac");

    const results = searchInput.locator("xpath=following-sibling::div[1]");
    await expect(results.getByText(productName, { exact: false })).toBeVisible();
    await expect(results.getByText("$600.00")).toBeVisible();
    await expect(page.getByText("Page could not render")).toHaveCount(0);
  });
});
